"""Builds the narrator system prompt from prompts/narrator.md (new chapters,
SPEC 5.1) and prompts/continue.md (continuing an open chapter — "book"
interface). Both templates' layer order MUST be preserved; this module only
fills placeholders, it never rewrites or reorders template text.
"""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path
from typing import Literal

from diary.core.story.characters import CharacterCard, WorldMeta, render_characters_brief
from diary.core.story.mood_input import TARGET_WORDS, MoodInput
from diary.core.style.chunking import Chunk
from diary.core.style.profile import AuthorProfile, render_style_card

NARRATOR_TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "prompts" / "narrator.md"
CONTINUE_TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "prompts" / "continue.md"

NO_RETRIEVAL_PLACEHOLDER = (
    "(no corpus index for this author — relying solely on the style description above)"
)

SafetyLevel = Literal["baseline", "reinforced"]

# Baseline safety rules (SPEC 6.4), always included.
DEFAULT_SAFETY_RULES = (
    "- You do not glorify or aestheticize harm. You do not describe methods of harm. "
    "You do not present leaving as a solution or as relief.\n"
    "- Difficult emotions may be fully experienced, without forced comfort or a moral."
)

# Reinforced variant (SPEC 6.4), used when the input detector (6.2) or the
# output filter's regeneration path (6.3) has triggered for this attempt.
# Adds to the baseline rather than replacing it — 6.1 calls this a fourth,
# soft layer that reinforces the other three, not a substitute for them.
REINFORCED_SAFETY_RULES = DEFAULT_SAFETY_RULES + (
    "\n- The protagonist may fully experience the darkness, without comfort and without a moral.\n"
    "- One character from the canon is present in the scene, simply being there — not moralizing, "
    "not advising, not offering comfort, but not leaving the protagonist alone.\n"
    "- No false optimism, but do not close the door."
)


_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_PROMPT_VERSION_RE = re.compile(r"^#\s*prompt_version:\s*(\d+)\s*$", re.MULTILINE)


def _load_template(path: Path) -> str:
    """Reads a template file, strips its own leading `#` header comments and
    any `<!-- -->` documentation blocks — those are for humans editing the
    template, not for the model."""
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines(keepends=True)
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue
        body_start = i
        break
    body = "".join(lines[body_start:])
    return _HTML_COMMENT_RE.sub("", body)


def _read_prompt_version(path: Path) -> int:
    raw = path.read_text(encoding="utf-8")
    match = _PROMPT_VERSION_RE.search(raw)
    if not match:
        raise ValueError(f"{path} has no '# prompt_version: N' header.")
    return int(match.group(1))


def get_prompt_version() -> int:
    """prompt_version of narrator.md (new chapters) — SPEC 5.5."""
    return _read_prompt_version(NARRATOR_TEMPLATE_PATH)


def get_continuation_prompt_version() -> int:
    """prompt_version of continue.md (continuing an open chapter)."""
    return _read_prompt_version(CONTINUE_TEMPLATE_PATH)


# Settings.story_language stores "auto" | "polsku" | "angielsku" (the drawer's
# internal option values, unrelated to prompt template language) — mapped here
# to the English language name the (now-English) prompt templates expect.
_STORY_LANGUAGE_NAMES = {"polsku": "Polish", "angielsku": "English"}


def resolve_story_language(story_language: str) -> str:
    if story_language == "auto":
        return "Polish"
    return _STORY_LANGUAGE_NAMES.get(story_language, story_language)


def render_retrieved_chunks(chunks: list[Chunk] | None) -> str:
    """Renders retrieved corpus chunks into the WZORCE STYLU layer (SPEC
    4.4). Simplified retrieval (see ASSUMPTIONS.md "M2.5") — plain excerpts,
    no reranking metadata shown to the model."""
    if not chunks:
        return NO_RETRIEVAL_PLACEHOLDER
    return "\n\n".join(f"### Fragment ({chunk.source_file})\n{chunk.text}" for chunk in chunks)


def _safety_rules_for(safety_level: SafetyLevel) -> str:
    return REINFORCED_SAFETY_RULES if safety_level == "reinforced" else DEFAULT_SAFETY_RULES


def build_prompt(
    *,
    profile: AuthorProfile,
    mood_input: MoodInput,
    story_language: str = "auto",
    characters: list[CharacterCard] | None = None,
    world_meta: WorldMeta | None = None,
    retrieved_chunks: list[Chunk] | None = None,
    safety_level: SafetyLevel = "baseline",
) -> str:
    """Returns the fully rendered system prompt for a NEW chapter (narrator.md)."""
    template = _load_template(NARRATOR_TEMPLATE_PATH)

    token = secrets.token_hex(4)
    delimiter = f"<<<DATA_{token}>>>"
    mood_input_json = json.dumps(mood_input.model_dump(), ensure_ascii=False, indent=2)

    return template.format(
        author_name=profile.name,
        story_lang=resolve_story_language(story_language),
        style_card=render_style_card(profile),
        retrieved_chunks=render_retrieved_chunks(retrieved_chunks),
        characters_brief=render_characters_brief(characters or [], world_meta or WorldMeta()),
        safety_rules=_safety_rules_for(safety_level),
        delimiter_open=delimiter,
        delimiter_close=delimiter,
        mood_input_json=mood_input_json,
        target_words=TARGET_WORDS[mood_input.length],
    )


def build_continuation_prompt(
    *,
    profile: AuthorProfile,
    mood_input: MoodInput,
    chapter_tail_text: str,
    story_language: str = "auto",
    characters: list[CharacterCard] | None = None,
    world_meta: WorldMeta | None = None,
    retrieved_chunks: list[Chunk] | None = None,
    safety_level: SafetyLevel = "baseline",
) -> str:
    """Returns the fully rendered system prompt to CONTINUE an open chapter
    (continue.md) — gets the chapter's literal prior text, not a summary."""
    template = _load_template(CONTINUE_TEMPLATE_PATH)

    chapter_token = secrets.token_hex(4)
    chapter_delimiter = f"<<<CHAPTER_{chapter_token}>>>"
    data_token = secrets.token_hex(4)
    data_delimiter = f"<<<DATA_{data_token}>>>"
    mood_input_json = json.dumps(mood_input.model_dump(), ensure_ascii=False, indent=2)

    return template.format(
        author_name=profile.name,
        story_lang=resolve_story_language(story_language),
        style_card=render_style_card(profile),
        retrieved_chunks=render_retrieved_chunks(retrieved_chunks),
        characters_brief=render_characters_brief(characters or [], world_meta or WorldMeta()),
        chapter_delimiter_open=chapter_delimiter,
        chapter_delimiter_close=chapter_delimiter,
        chapter_tail_text=chapter_tail_text,
        safety_rules=_safety_rules_for(safety_level),
        data_delimiter_open=data_delimiter,
        data_delimiter_close=data_delimiter,
        mood_input_json=mood_input_json,
        target_words=TARGET_WORDS[mood_input.length],
    )
