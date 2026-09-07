"""Orchestrates one story generation call and the UI stages from SPEC 3.3.

Two modes: a NEW chapter (narrator.md — AI invents the opening) or
CONTINUING an open chapter (continue.md — literal prior text, same scene).
Pipeline per attempt either way: stream the story → metadata call (SPEC 5.3)
→ output filter (SPEC 6.3, a decision separate from metadata, allowed to use
the metadata call's tone_flags as a hint) → pass, or regenerate with a
reinforced prompt (SPEC 6.4), up to `MAX_REGENERATION_ATTEMPTS`, then a
fixed fallback text.

This module has no database access — it is pure event-yielding logic,
testable end-to-end on `MockAdapter`. The caller (routes.py) touches
storage: loading characters/world_meta/chapter text before the call, and
persisting the result and updated characters after.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import AsyncIterator, Literal

from diary.core.llm.base import LLMAdapter, LLMError
from diary.core.safety.output_filter import (
    MAX_REGENERATION_ATTEMPTS,
    REJECTION_UI_MESSAGE,
    fallback_story_text,
    run_output_filter,
)
from diary.core.story.characters import CharacterCard, WorldMeta
from diary.core.story.metadata import StoryMetadata, generate_metadata
from diary.core.story.mood_input import MoodInput
from diary.core.story.prompt_builder import build_continuation_prompt, build_prompt
from diary.core.style.chunking import Chunk
from diary.core.style.profile import AuthorProfile

logger = logging.getLogger(__name__)

# Generyczne, treściowo puste domykacze tury. Cała treść zadania żyje w system
# prompcie — te komunikaty tylko go wyzwalają. Bez tego niektóre bramki
# OpenAI-compatible (np. Gemini) odrzucają request kodem 400: pod spodem
# mapują system → systemInstruction, a resztę wiadomości → contents, i
# wymagają co najmniej jednej wiadomości spoza roli system.
USER_TURN_TRIGGER = "Napisz teraz opowiadanie zgodnie z powyższymi wytycznymi."
CONTINUATION_USER_TURN_TRIGGER = "Kontynuuj dokładnie od miejsca, w którym urwał się poprzedni fragment."

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

SafetyOutputResult = Literal["pass", "regenerated", "fallback"]


@dataclass(frozen=True)
class ContinuationContext:
    """Present only when the user clicked "Kontynuuj" — the literal end of
    the chapter's text so far (not a summary, SPEC point 1 of the book
    interface)."""

    chapter_tail_text: str


@dataclass(frozen=True)
class StageEvent:
    stage: Stage


@dataclass(frozen=True)
class TokenEvent:
    text: str


@dataclass(frozen=True)
class FilterRejectedEvent:
    """Output filter rejected the just-streamed text (SPEC 6.3): the UI
    replaces what it showed with `message`, then a new attempt streams."""

    message: str


@dataclass(frozen=True)
class ErrorEvent:
    message: str


@dataclass(frozen=True)
class ResultEvent:
    """The final, filter-passed (or fallback) story plus everything the
    caller needs to persist an entry and update character cards."""

    story_text: str
    metadata: StoryMetadata
    safety_output_result: SafetyOutputResult
    input_detected: bool


@dataclass(frozen=True)
class DoneEvent:
    pass


GenerationEvent = StageEvent | TokenEvent | FilterRejectedEvent | ErrorEvent | ResultEvent | DoneEvent


def _fallback_metadata(author_name: str) -> StoryMetadata:
    """Fixed fallback text (SPEC 6.3) is not model-generated, so it gets a
    small fixed metadata record instead of a real (and pointless) metadata
    call — there's nothing to extract from a static template."""
    return StoryMetadata(
        title="Krótki wpis",
        mood_tag="spokój",
        characters_used=[],
        character_delta={},
        summary="",
        tone_flags=["none"],
    )


def _build_system_prompt(
    *,
    profile: AuthorProfile,
    mood_input: MoodInput,
    story_language: str,
    characters: list[CharacterCard],
    world_meta: WorldMeta,
    retrieved_chunks: list[Chunk],
    safety_level: str,
    continuation: ContinuationContext | None,
) -> tuple[str, str]:
    """Returns (system_prompt, user_turn_trigger) for the current attempt."""
    if continuation is not None:
        prompt = build_continuation_prompt(
            profile=profile,
            mood_input=mood_input,
            chapter_tail_text=continuation.chapter_tail_text,
            story_language=story_language,
            characters=characters,
            world_meta=world_meta,
            retrieved_chunks=retrieved_chunks,
            safety_level=safety_level,
        )
        return prompt, CONTINUATION_USER_TURN_TRIGGER

    prompt = build_prompt(
        profile=profile,
        mood_input=mood_input,
        story_language=story_language,
        characters=characters,
        world_meta=world_meta,
        retrieved_chunks=retrieved_chunks,
        safety_level=safety_level,
    )
    return prompt, USER_TURN_TRIGGER


async def generate_story(
    *,
    adapter: LLMAdapter,
    profile: AuthorProfile,
    mood_input: MoodInput,
    model: str,
    model_helper: str,
    temperature: float,
    story_language: str,
    characters: list[CharacterCard],
    world_meta: WorldMeta,
    retrieved_chunks: list[Chunk],
    continuation: ContinuationContext | None,
    input_detected: bool,
) -> AsyncIterator[GenerationEvent]:
    yield StageEvent("dobieram fragmenty stylu")
    yield StageEvent("przypominam bohaterów")

    safety_level = "reinforced" if input_detected else "baseline"
    safety_output_result: SafetyOutputResult = "pass"
    attempt = 0

    while True:
        yield StageEvent("piszę")
        system_prompt, user_trigger = _build_system_prompt(
            profile=profile,
            mood_input=mood_input,
            story_language=story_language,
            characters=characters,
            world_meta=world_meta,
            retrieved_chunks=retrieved_chunks,
            safety_level=safety_level,
            continuation=continuation,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_trigger},
        ]

        story_text = ""
        try:
            async for chunk in adapter.generate_stream(messages, model=model, temperature=temperature):
                story_text += chunk
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
        try:
            metadata = await generate_metadata(
                adapter=adapter, model=model_helper, profile=profile, story_text=story_text,
                characters=characters, world_meta=world_meta,
            )
            verdict = await run_output_filter(
                adapter=adapter, model=model_helper, story_text=story_text, tone_flags=metadata.tone_flags
            )
        except LLMError as exc:
            yield ErrorEvent(str(exc))
            return

        if verdict.passed:
            break

        attempt += 1
        if attempt > MAX_REGENERATION_ATTEMPTS:
            story_text = fallback_story_text(profile.name)
            metadata = _fallback_metadata(profile.name)
            safety_output_result = "fallback"
            yield FilterRejectedEvent(REJECTION_UI_MESSAGE)
            yield TokenEvent(story_text)
            break

        safety_output_result = "regenerated"
        safety_level = "reinforced"  # SPEC 6.3: retry uses the reinforced prompt regardless of 6.2
        yield FilterRejectedEvent(REJECTION_UI_MESSAGE)

    yield StageEvent("zapisuję")
    yield ResultEvent(
        story_text=story_text,
        metadata=metadata,
        safety_output_result=safety_output_result,
        input_detected=input_detected,
    )
    yield DoneEvent()
