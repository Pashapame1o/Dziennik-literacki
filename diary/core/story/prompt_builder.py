"""Builds the narrator system prompt from prompts/narrator.md (SPEC 5.1).

The template's layer order MUST be preserved; this module only fills
placeholders, it never rewrites or reorders the template text. In M1 there
is no RAG, world state, or input detector yet, so their layers render as
explicit "not available" placeholders instead of being skipped — SPEC 4.4
and 5.2 both call for that kind of graceful degradation to be visible.
"""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path

from diary.core.story.mood_input import TARGET_WORDS, MoodInput
from diary.core.style.profile import AuthorProfile, render_style_card

TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "prompts" / "narrator.md"

NO_RETRIEVAL_PLACEHOLDER = (
    "(brak indeksu korpusu dla tego autora — opieram się wyłącznie na opisie stylu powyżej)"
)
NO_WORLD_STATE_PLACEHOLDER = (
    "(brak zapisanego świata — to pierwszy wpis z tym autorem, wymyśl alter ego, "
    "postaci poboczne i scenerię od zera)"
)

# Baseline safety rules (SPEC 6.4), always included regardless of detector/streak
# state, since neither is implemented yet in M1. The detector- and streak-triggered
# reinforcements documented in prompts/narrator.md are added starting M2/M4.
DEFAULT_SAFETY_RULES = (
    "- Nie gloryfikujesz ani nie estetyzujesz krzywdy. Nie opisujesz metod krzywdy. "
    "Nie przedstawiasz odejścia jako rozwiązania ani ulgi.\n"
    "- Trudne emocje mogą być przeżyte w pełni, bez pocieszenia i morału na siłę."
)


_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _load_template() -> str:
    """Reads narrator.md, strips the file's own leading `#` header comments
    and any `<!-- -->` documentation blocks (e.g. the streak/detector safety
    rule examples) — those are for humans editing the template, not for the
    model, and reference placeholders like {streak_shift} that M1 never fills."""
    raw = TEMPLATE_PATH.read_text(encoding="utf-8")
    lines = raw.splitlines(keepends=True)
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue
        body_start = i
        break
    body = "".join(lines[body_start:])
    return _HTML_COMMENT_RE.sub("", body)


def _resolve_story_language(story_language: str) -> str:
    if story_language == "auto":
        return "polsku"
    return story_language


def build_prompt(
    *,
    profile: AuthorProfile,
    mood_input: MoodInput,
    story_language: str = "auto",
) -> str:
    """Returns the fully rendered system prompt for the narrator call."""
    template = _load_template()

    token = secrets.token_hex(4)
    delimiter = f"<<<DATA_{token}>>>"

    mood_input_json = json.dumps(mood_input.model_dump(), ensure_ascii=False, indent=2)

    return template.format(
        author_name=profile.name,
        story_lang=_resolve_story_language(story_language),
        style_card=render_style_card(profile),
        retrieved_chunks=NO_RETRIEVAL_PLACEHOLDER,
        world_state_brief=NO_WORLD_STATE_PLACEHOLDER,
        safety_rules=DEFAULT_SAFETY_RULES,
        delimiter_open=delimiter,
        delimiter_close=delimiter,
        mood_input_json=mood_input_json,
        target_words=TARGET_WORDS[mood_input.length],
    )
