"""Second call per entry (SPEC 5.3): cheap-model structured metadata —
title, mood_tag, characters_used, character_delta, summary, tone_flags.

`character_delta` comes back from the model as a raw dict, not typed
directly as `CharacterCardDelta`, so a validation failure on that one
nested field doesn't blow up parsing of the rest of the metadata (SPEC 5.2:
an invalid delta is *rejected*, not treated as a fatal error for the whole
call) — `safe_parse_delta` does that validation as a separate step.
"""

from __future__ import annotations

import logging
import secrets
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from diary.core.llm.base import LLMAdapter, Message
from diary.core.story.characters import (
    CharacterCard,
    CharacterCardDelta,
    WorldMeta,
    check_safe_text,
    render_characters_brief,
)
from diary.core.style.profile import AuthorProfile

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "prompts" / "metadata.md"

ALLOWED_TONE_FLAGS = {"harm_method", "glorification", "relief_framing", "none"}


class StoryMetadata(BaseModel):
    title: str = Field(default="", max_length=120)
    mood_tag: str = Field(default="", max_length=40)
    characters_used: list[str] = Field(default_factory=list, max_length=8)
    character_delta: dict = Field(default_factory=dict)
    summary: str = Field(default="", max_length=300)
    tone_flags: list[str] = Field(default_factory=list, max_length=10)


def safe_parse_delta(raw: dict) -> CharacterCardDelta:
    """Validates the model's proposed character_delta (SPEC 5.2). An invalid
    delta (instruction phrase, oversized field, bad shape) is rejected and
    replaced with a no-op delta rather than failing the whole metadata call —
    the story and its other metadata are still good even if this one field
    tried something it shouldn't have."""
    try:
        return CharacterCardDelta.model_validate(raw)
    except ValidationError:
        logger.warning("Rejected character_delta: failed validation (SPEC 5.2).")
        return CharacterCardDelta()


def _sanitize_tone_flags(raw_flags: list[str]) -> list[str]:
    """tone_flags feed into the output filter's own prompt (SPEC 6.3), so
    they get the same injection check as character-card text, plus a soft
    allow-list — unknown labels are dropped rather than rejected outright,
    since the model drifting on label wording shouldn't break the pipeline."""
    flags = []
    for flag in raw_flags:
        try:
            checked = check_safe_text(flag, max_length=30)
        except ValueError:
            continue
        if checked in ALLOWED_TONE_FLAGS:
            flags.append(checked)
    return flags


def build_metadata_messages(
    *, profile: AuthorProfile, story_text: str, characters: list[CharacterCard], world_meta: WorldMeta
) -> list[Message]:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    lines = template.splitlines(keepends=True)
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue
        body_start = i
        break
    body = "".join(lines[body_start:])

    token = secrets.token_hex(4)
    delimiter = f"<<<DATA_{token}>>>"

    prompt = body.format(
        author_name=profile.name,
        delimiter_open=delimiter,
        story_text=story_text,
        delimiter_close=delimiter,
        characters_brief=render_characters_brief(characters, world_meta),
    )
    return [{"role": "system", "content": prompt}]


async def generate_metadata(
    *,
    adapter: LLMAdapter,
    model: str,
    profile: AuthorProfile,
    story_text: str,
    characters: list[CharacterCard],
    world_meta: WorldMeta,
) -> StoryMetadata:
    messages = build_metadata_messages(
        profile=profile, story_text=story_text, characters=characters, world_meta=world_meta
    )
    metadata = await adapter.generate_structured(messages, model=model, schema=StoryMetadata, temperature=0.2)
    metadata.tone_flags = _sanitize_tone_flags(metadata.tone_flags)
    return metadata
