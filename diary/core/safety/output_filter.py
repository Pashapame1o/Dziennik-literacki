"""Output safety filter (SPEC 6.3): a separate decision from the metadata
call, made after generation and before the story is saved or shown in full.
May take `tone_flags` from the metadata call as a hint, but always re-judges
the text itself — that separation is a MUST in SPEC 6.3, not a style choice.

Rejected text triggers regeneration with a reinforced prompt (SPEC 6.4), up
to `MAX_REGENERATION_ATTEMPTS` times, then falls back to a short, fixed,
risk-free template (never model-generated, so it cannot fail the filter).
"""

from __future__ import annotations

import secrets
from pathlib import Path

from pydantic import BaseModel, Field

from diary.core.llm.base import LLMAdapter, Message

TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "prompts" / "output_filter.md"

MAX_REGENERATION_ATTEMPTS = 2

# Shown in the UI in place of the rejected text while a retry is generated
# (SPEC 6.3's literal wording).
REJECTION_UI_MESSAGE = "Ta wersja nie przeszła sprawdzenia, piszę ponownie."


class OutputFilterVerdict(BaseModel):
    verdict: str = Field(pattern="^(pass|regenerate)$")
    reasons: list[str] = Field(default_factory=list, max_length=5)

    @property
    def passed(self) -> bool:
        return self.verdict == "pass"


def build_output_filter_messages(*, story_text: str, tone_flags: list[str]) -> list[Message]:
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
        delimiter_open=delimiter,
        story_text=story_text,
        delimiter_close=delimiter,
        tone_flags=", ".join(tone_flags) if tone_flags else "(brak)",
    )
    return [{"role": "system", "content": prompt}]


async def run_output_filter(
    *, adapter: LLMAdapter, model: str, story_text: str, tone_flags: list[str]
) -> OutputFilterVerdict:
    messages = build_output_filter_messages(story_text=story_text, tone_flags=tone_flags)
    return await adapter.generate_structured(
        messages, model=model, schema=OutputFilterVerdict, temperature=0.0
    )


def fallback_story_text(author_name: str) -> str:
    """A short, calm, fixed template (SPEC 6.3) — never model-generated, so
    it cannot itself fail the filter. Deliberately generic: no risk themes,
    no attempt at the author's voice beyond a passing mention."""
    return (
        f"Dzień dobiegł końca bez wielkich wydarzeń. Ktoś, kto mógłby być bohaterem "
        f"opowiadania w stylu {author_name}, usiadł przy oknie i patrzył, jak zapada zmrok. "
        "Nie musiał niczego rozstrzygać tego wieczoru. Herbata stygła powoli, "
        "a dom wokół niego oddychał swoim zwykłym, cichym rytmem. Jutro miało nadejść "
        "samo, bez pośpiechu."
    )
