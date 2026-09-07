"""Loads authors/<slug>/profile.yaml (SPEC 4.1-4.2) and renders the style card
that goes into the narrator prompt's STYL layer.

The authors list is data-driven: adding an author is adding a directory,
no code changes (SPEC 3.1).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

AUTHORS_DIR = Path(__file__).resolve().parents[3] / "authors"


class Voice(BaseModel):
    syntax: str = ""
    rhythm: str = ""
    sentence_length: str = ""
    inner_monologue: str = ""
    narrator_irony: str = ""
    nature_as_mirror: str = ""


class RetrievalPrefs(BaseModel):
    k: int = 6
    chunk_size_tokens: int = 450
    chunk_overlap_tokens: int = 60
    tone_tag_preferences: dict[str, list[str]] = Field(default_factory=dict)


class AuthorProfile(BaseModel):
    name: str
    slug: str
    languages: list[str] = Field(default_factory=list)
    era: str = ""
    teaser: str = ""
    default_setting_hints: list[str] = Field(default_factory=list)
    voice: Voice = Field(default_factory=Voice)
    devices: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    character_archetypes: list[str] = Field(default_factory=list)
    lexicon_hints: dict[str, list[str]] = Field(default_factory=dict)
    avoid: list[str] = Field(default_factory=list)
    retrieval: RetrievalPrefs = Field(default_factory=RetrievalPrefs)
    version: int = 1


def list_author_slugs() -> list[str]:
    if not AUTHORS_DIR.is_dir():
        return []
    return sorted(
        p.name for p in AUTHORS_DIR.iterdir() if p.is_dir() and (p / "profile.yaml").is_file()
    )


def load_author_profile(slug: str) -> AuthorProfile:
    path = AUTHORS_DIR / slug / "profile.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Brak profilu autora: {slug}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return AuthorProfile.model_validate(raw)


def has_index(slug: str) -> bool:
    index_dir = AUTHORS_DIR / slug / "index"
    return index_dir.is_dir() and any(index_dir.iterdir())


def render_style_card(profile: AuthorProfile) -> str:
    """Renders profile.yaml fields into the readable style-card text used as
    the STYLE (skeleton) layer of the prompt (SPEC 5.1 layer 2). The labels
    here are ours (English); the values come from profile.yaml and stay in
    whatever language that author's voice was written in (Polish for now)."""
    lines = [
        f"Era and setting: {profile.era}",
        f"Syntax: {profile.voice.syntax}",
        f"Rhythm: {profile.voice.rhythm}",
        f"Sentence length: {profile.voice.sentence_length}",
        f"Inner monologue: {profile.voice.inner_monologue}",
        f"Narrator's irony: {profile.voice.narrator_irony}",
        f"Nature as a mirror of state: {profile.voice.nature_as_mirror}",
    ]
    if profile.default_setting_hints:
        lines.append("Typical setting: " + "; ".join(profile.default_setting_hints))
    if profile.devices:
        lines.append("Stylistic devices: " + "; ".join(profile.devices))
    if profile.themes:
        lines.append("Themes: " + "; ".join(profile.themes))
    if profile.character_archetypes:
        lines.append("Character archetypes: " + "; ".join(profile.character_archetypes))
    if profile.lexicon_hints:
        for lang, words in profile.lexicon_hints.items():
            lines.append(f"Vocabulary ({lang}): " + "; ".join(words))
    if profile.avoid:
        lines.append("Avoid: " + "; ".join(profile.avoid))
    return "\n".join(lines)
