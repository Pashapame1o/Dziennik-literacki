"""Compact per-character memory (SPEC 5.2, revised).

Replaces the M2 world-state blob (`canon` + `recent_threads` as one growing
JSON object) with small, structured records: one row per character, plus a
tiny per-author `world_meta` row for scenery/era. See ASSUMPTIONS.md "M2.5"
for why the blob didn't scale to chapter continuation — in short, it only
ever stored short recaps, never the literal text a continuation needs, and
its flat `facts` list had no way to *update* a fact about a specific
character (e.g. a death) without just appending a possibly-contradicting
string.

`CharacterCardDelta` is what the metadata call (SPEC 5.3) proposes to add —
model-generated text flowing back into a future prompt, so every free-text
field goes through the same injection check as the old world-state delta.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

MAX_ACTIVE_CHARACTERS = 8
MAX_TRAITS_PER_CHARACTER = 6

FIELD_MAX_LEN = 200
NAME_MAX_LEN = 80
STATUS_MAX_LEN = 60

# Same blunt, offline injection check the M2 world-state delta used — the
# random per-request delimiter (SPEC 5.1 layer 7) is the primary defense,
# this is defense in depth for model-generated text re-entering a future
# prompt. See diary/core/story/world_state.py in M2 history for the original.
_INSTRUCTION_PATTERNS = [
    re.compile(r"ignoruj", re.IGNORECASE),
    re.compile(r"od\s+teraz", re.IGNORECASE),
    re.compile(r"system\s*:", re.IGNORECASE),
    re.compile(r"zasady\s*:", re.IGNORECASE),
    re.compile(r"jeste[śs]\s+(teraz|odt[ąa]d)", re.IGNORECASE),
    re.compile(r"disregard", re.IGNORECASE),
    re.compile(r"ignore\s+(all|previous|above)", re.IGNORECASE),
    re.compile(r"you\s+are\s+(now|no\s+longer)", re.IGNORECASE),
    re.compile(r"new\s+instructions", re.IGNORECASE),
]
_DELIMITER_MARKERS = ("<<<", ">>>", "```")


class CharacterValidationError(ValueError):
    """Raised when a character-card field fails injection/length checks."""


def check_safe_text(value: str, *, max_length: int = FIELD_MAX_LEN) -> str:
    if len(value) > max_length:
        raise CharacterValidationError(f"Field exceeds the {max_length}-character limit.")
    if any(p.search(value) for p in _INSTRUCTION_PATTERNS):
        raise CharacterValidationError("Field contains an instruction-like phrase — rejected.")
    if any(marker in value for marker in _DELIMITER_MARKERS):
        raise CharacterValidationError("Field contains delimiter characters — rejected.")
    return value


class Relationship(BaseModel):
    name: str = Field(max_length=NAME_MAX_LEN)
    relation: str = Field(max_length=FIELD_MAX_LEN)

    @field_validator("name")
    @classmethod
    def _name_safe(cls, value: str) -> str:
        return check_safe_text(value, max_length=NAME_MAX_LEN)

    @field_validator("relation")
    @classmethod
    def _relation_safe(cls, value: str) -> str:
        return check_safe_text(value)


class CharacterCard(BaseModel):
    name: str = Field(max_length=NAME_MAX_LEN)
    is_alter_ego: bool = False
    role: str = Field(default="", max_length=FIELD_MAX_LEN)
    traits: list[str] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    status: str = Field(default="", max_length=STATUS_MAX_LEN)
    locked: bool = False

    @field_validator("name")
    @classmethod
    def _name_safe(cls, value: str) -> str:
        return check_safe_text(value, max_length=NAME_MAX_LEN)

    @field_validator("role")
    @classmethod
    def _role_safe(cls, value: str) -> str:
        return check_safe_text(value) if value else value

    @field_validator("status")
    @classmethod
    def _status_safe(cls, value: str) -> str:
        return check_safe_text(value, max_length=STATUS_MAX_LEN) if value else value

    @field_validator("traits")
    @classmethod
    def _traits_safe_and_capped(cls, value: list[str]) -> list[str]:
        checked = [check_safe_text(t, max_length=60) for t in value]
        if len(checked) > MAX_TRAITS_PER_CHARACTER:
            raise CharacterValidationError(f"At most {MAX_TRAITS_PER_CHARACTER} traits per character.")
        return checked


class WorldMeta(BaseModel):
    setting: str = Field(default="", max_length=FIELD_MAX_LEN)
    era: str = Field(default="", max_length=120)

    @field_validator("setting")
    @classmethod
    def _setting_safe(cls, value: str) -> str:
        return check_safe_text(value) if value else value

    @field_validator("era")
    @classmethod
    def _era_safe(cls, value: str) -> str:
        return check_safe_text(value, max_length=120) if value else value

    @property
    def is_empty(self) -> bool:
        return not self.setting and not self.era


class CharacterUpdate(BaseModel):
    """Partial update to an existing character, matched by name (SPEC 5.2:
    'nowszy fakt wygrywa, chyba że pole jest locked' — enforced by the
    caller, which skips updates to cards with `locked=True`)."""

    name: str = Field(max_length=NAME_MAX_LEN)
    status: str | None = Field(default=None, max_length=STATUS_MAX_LEN)
    add_traits: list[str] = Field(default_factory=list)
    add_relationships: list[Relationship] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name_safe(cls, value: str) -> str:
        return check_safe_text(value, max_length=NAME_MAX_LEN)

    @field_validator("status")
    @classmethod
    def _status_safe(cls, value: str | None) -> str | None:
        return check_safe_text(value, max_length=STATUS_MAX_LEN) if value else value

    @field_validator("add_traits")
    @classmethod
    def _add_traits_safe(cls, value: list[str]) -> list[str]:
        return [check_safe_text(t, max_length=60) for t in value]


class CharacterCardDelta(BaseModel):
    """What the metadata call proposes to add/change (SPEC 5.3)."""

    new_characters: list[CharacterCard] = Field(default_factory=list)
    character_updates: list[CharacterUpdate] = Field(default_factory=list)
    setting: str | None = Field(default=None, max_length=FIELD_MAX_LEN)  # only used if world_meta.setting is empty

    @field_validator("setting")
    @classmethod
    def _setting_safe(cls, value: str | None) -> str | None:
        return check_safe_text(value) if value else value


def apply_character_delta(
    existing: list[CharacterCard], delta: CharacterCardDelta
) -> list[CharacterCard]:
    """Merges a validated delta into the character list, enforcing the
    8-character cap (SPEC 5.2) by simple capping — no compaction/archival,
    that's M4. Updates to `locked` characters are skipped, per SPEC 5.2's
    conflict rule ("nowszy fakt wygrywa, chyba że pole jest locked")."""
    updated = [c.model_copy(deep=True) for c in existing]
    by_name = {c.name: c for c in updated}

    for change in delta.character_updates:
        card = by_name.get(change.name)
        if card is None or card.locked:
            continue  # unknown name, or user has locked this card against model edits
        if change.status is not None:
            card.status = change.status
        for trait in change.add_traits:
            if trait not in card.traits and len(card.traits) < MAX_TRAITS_PER_CHARACTER:
                card.traits.append(trait)
        for rel in change.add_relationships:
            if rel.name not in {r.name for r in card.relationships}:
                card.relationships.append(rel)

    for new_card in delta.new_characters:
        if new_card.name in by_name:
            continue
        if len(updated) >= MAX_ACTIVE_CHARACTERS:
            break
        updated.append(new_card)
        by_name[new_card.name] = new_card

    return updated


def apply_world_meta_delta(meta: WorldMeta, delta: CharacterCardDelta) -> WorldMeta:
    if meta.setting or not delta.setting:
        return meta
    return WorldMeta(setting=delta.setting, era=meta.era)


def render_characters_brief(characters: list[CharacterCard], world_meta: WorldMeta) -> str:
    """Renders characters + world_meta into the prompt's world/character
    layer — compact, structured, predictable size (unlike the old blob)."""
    if not characters and world_meta.is_empty:
        return (
            "(no saved world yet — this is the first entry with this author, invent an alter ego, "
            "supporting characters, and a setting from scratch)"
        )

    lines: list[str] = []
    if world_meta.setting:
        lines.append(f"Setting: {world_meta.setting}")
    if world_meta.era:
        lines.append(f"Era: {world_meta.era}")

    for card in characters:
        tag = " (alter ego)" if card.is_alter_ego else ""
        lock = " [locked]" if card.locked else ""
        details = []
        if card.role:
            details.append(card.role)
        if card.status:
            details.append(f"status: {card.status}")
        if card.traits:
            details.append("traits: " + ", ".join(card.traits))
        if card.relationships:
            details.append("relationships: " + "; ".join(f"{r.name} ({r.relation})" for r in card.relationships))
        suffix = f": {'; '.join(details)}" if details else ""
        lines.append(f"- {card.name}{tag}{lock}{suffix}")

    return "\n".join(lines)
