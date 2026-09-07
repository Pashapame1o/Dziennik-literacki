from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from diary.app.schemas import AuthorSummary, FormOptions, GenerateRequest, QuestionOption
from diary.core.llm.factory import build_adapter
from diary.core.settings import override_settings
from diary.core.story.generation import DoneEvent, ErrorEvent, StageEvent, TokenEvent, generate_story
from diary.core.story.mood_input import EMOTION_CHIPS, YES_NO_QUESTIONS
from diary.core.style.profile import has_index, list_author_slugs, load_author_profile

router = APIRouter(prefix="/api")


@router.get("/authors", response_model=list[AuthorSummary])
def get_authors() -> list[AuthorSummary]:
    summaries = []
    for slug in list_author_slugs():
        profile = load_author_profile(slug)
        summaries.append(
            AuthorSummary(
                slug=profile.slug,
                name=profile.name,
                era=profile.era,
                expect=profile.teaser,
                has_index=has_index(slug),
            )
        )
    return summaries


@router.get("/form-options", response_model=FormOptions)
def get_form_options() -> FormOptions:
    return FormOptions(
        chips=EMOTION_CHIPS,
        questions=[QuestionOption(**q) for q in YES_NO_QUESTIONS],
    )


async def _event_stream(payload: GenerateRequest) -> AsyncIterator[dict[str, str]]:
    overrides = payload.overrides.model_dump(exclude_none=True)
    with override_settings(**overrides) as settings:
        try:
            profile = load_author_profile(payload.author_slug)
        except FileNotFoundError as exc:
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}
            return

        adapter = build_adapter(settings)
        async for event in generate_story(
            adapter=adapter,
            profile=profile,
            mood_input=payload.mood_input,
            model=settings.model_story,
            temperature=settings.temperature,
            story_language=settings.story_language,
        ):
            if isinstance(event, StageEvent):
                yield {"event": "stage", "data": json.dumps({"stage": event.stage})}
            elif isinstance(event, TokenEvent):
                yield {"event": "token", "data": json.dumps({"text": event.text})}
            elif isinstance(event, ErrorEvent):
                yield {"event": "error", "data": json.dumps({"message": event.message})}
            elif isinstance(event, DoneEvent):
                yield {"event": "done", "data": "{}"}


@router.post("/generate")
async def generate(payload: GenerateRequest) -> EventSourceResponse:
    if payload.author_slug not in list_author_slugs():
        raise HTTPException(status_code=404, detail=f"Nieznany autor: {payload.author_slug}")
    return EventSourceResponse(_event_stream(payload))
