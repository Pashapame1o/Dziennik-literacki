"""Orchestrates one story generation call and the UI stages from SPEC 3.3.

M1 has no RAG, world state, output filter, or storage yet, so "dobieram
fragmenty stylu", "przypominam bohaterów", "sprawdzam" and "zapisuję" are
placeholder stages that pass through instantly — they exist so the UI's
stage indicator is stable across milestones and doesn't need reshaping
once M2/M3 fill them in. Only "piszę" does real work in M1.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import AsyncIterator, Literal

from diary.core.llm.base import LLMAdapter, LLMError
from diary.core.story.mood_input import MoodInput
from diary.core.story.prompt_builder import build_prompt
from diary.core.style.profile import AuthorProfile

logger = logging.getLogger(__name__)

# Generyczny, treściowo pusty domykacz tury. Cała treść zadania (styl, świat,
# nastrój, format) żyje w system prompcie — ten komunikat tylko go wyzwala.
# Bez niego niektóre bramki OpenAI-compatible (np. Gemini) odrzucają request
# kodem 400: pod spodem mapują system → systemInstruction, a resztę wiadomości
# → contents, i wymagają co najmniej jednej wiadomości spoza roli system.
# Prawdziwy OpenAI był tu wyjątkowo tolerancyjny, więc lukę widać dopiero na
# innym dostawcy — patrz też SPEC 3.5 (jeden adapter, wiele providerów).
USER_TURN_TRIGGER = "Napisz teraz opowiadanie zgodnie z powyższymi wytycznymi."

Stage = Literal[
    "dobieram fragmenty stylu",
    "przypominam bohaterów",
    "piszę",
    "sprawdzam",
    "zapisuję",
]

STAGES: tuple[Stage, ...] = (
    "dobieram fragmenty stylu",
    "przypominam bohaterów",
    "piszę",
    "sprawdzam",
    "zapisuję",
)


@dataclass(frozen=True)
class StageEvent:
    stage: Stage


@dataclass(frozen=True)
class TokenEvent:
    text: str


@dataclass(frozen=True)
class ErrorEvent:
    message: str


@dataclass(frozen=True)
class DoneEvent:
    pass


GenerationEvent = StageEvent | TokenEvent | ErrorEvent | DoneEvent


async def generate_story(
    *,
    adapter: LLMAdapter,
    profile: AuthorProfile,
    mood_input: MoodInput,
    model: str,
    temperature: float,
    story_language: str,
) -> AsyncIterator[GenerationEvent]:
    yield StageEvent("dobieram fragmenty stylu")
    yield StageEvent("przypominam bohaterów")

    system_prompt = build_prompt(profile=profile, mood_input=mood_input, story_language=story_language)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": USER_TURN_TRIGGER},
    ]

    yield StageEvent("piszę")
    try:
        async for chunk in adapter.generate_stream(messages, model=model, temperature=temperature):
            yield TokenEvent(chunk)
    except LLMError as exc:
        yield ErrorEvent(str(exc))
        return
    except Exception:  # noqa: BLE001
        # Nic nie może zniknąć po cichu w środku strumienia: bez tego wyjątek
        # inny niż LLMError ubijał odpowiedź SSE w połowie, a przeglądarka
        # widziała tylko urwany tekst bez żadnego komunikatu.
        logger.exception("Nieoczekiwany błąd podczas generowania opowiadania")
        yield ErrorEvent("Nieoczekiwany błąd podczas generowania. Szczegóły w logach serwera.")
        return

    yield StageEvent("sprawdzam")
    yield StageEvent("zapisuję")
    yield DoneEvent()
