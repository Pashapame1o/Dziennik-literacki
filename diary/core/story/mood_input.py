"""Structured mood input for screen 2 (SPEC 3.2). No free-text field beyond the
capped optional sentence — this is a MUST, see SPEC section 2.1 and 10."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

EMOTION_CHIPS: list[str] = [
    "smutek",
    "lęk",
    "złość",
    "spokój",
    "radość",
    "pustka",
    "wdzięczność",
    "znużenie",
]

# Fixed question_id per question (SPEC 3.2): stable ids so answers stay
# comparable across entries over time.
YES_NO_QUESTIONS: list[dict[str, str]] = [
    {"question_id": "unusual_event", "text": "Wydarzyło się coś nietypowego?"},
    {"question_id": "people_or_solitude", "text": "Więcej ludzi czy samotności?"},
    {"question_id": "afraid_tomorrow", "text": "Jest coś, czego boisz się jutro?"},
    {"question_id": "something_closed", "text": "Czy coś się dziś domknęło?"},
]
_VALID_QUESTION_IDS = {q["question_id"] for q in YES_NO_QUESTIONS}

LengthChoice = Literal["short", "medium", "long"]
TARGET_WORDS: dict[LengthChoice, int] = {"short": 500, "medium": 900, "long": 1500}


class MoodInput(BaseModel):
    valence: int = Field(ge=-5, le=5)
    energy: int = Field(ge=0, le=10)
    chips: list[str] = Field(min_length=1, max_length=3)
    answers: dict[str, bool] = Field(min_length=3, max_length=4)
    keywords: list[str] = Field(min_length=1, max_length=3)
    sentence: str | None = Field(default=None, max_length=200)
    length: LengthChoice = "medium"

    @field_validator("chips")
    @classmethod
    def _chips_known(cls, value: list[str]) -> list[str]:
        unknown = set(value) - set(EMOTION_CHIPS)
        if unknown:
            raise ValueError(f"Nieznane chipy emocji: {sorted(unknown)}")
        return value

    @field_validator("answers")
    @classmethod
    def _answers_known(cls, value: dict[str, bool]) -> dict[str, bool]:
        unknown = set(value) - _VALID_QUESTION_IDS
        if unknown:
            raise ValueError(f"Nieznane question_id: {sorted(unknown)}")
        return value

    @field_validator("keywords")
    @classmethod
    def _keywords_total_length(cls, value: list[str]) -> list[str]:
        total = sum(len(k) for k in value)
        if total > 60:
            raise ValueError("Słowa kluczowe: limit 60 znaków łącznie.")
        return value
