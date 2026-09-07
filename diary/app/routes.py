from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from diary.app.generation_registry import GenerationBuffer, create as create_buffer, get as get_buffer
from diary.app.schemas import (
    AuthorSummary,
    BookChapterOut,
    BookEntryOut,
    BookOut,
    ChapterOut,
    FormOptions,
    GenerateRequest,
    HelplinesOut,
    QuestionOption,
)
from diary.core.llm.factory import build_adapter
from diary.core.portfolio import storage
from diary.core.safety.helplines import load_helplines
from diary.core.safety.input_detector import detect
from diary.core.settings import Settings, get_settings
from diary.core.story.chapters import build_chapter_tail, summarize_chapter
from diary.core.story.characters import (
    CharacterCard,
    Relationship,
    WorldMeta,
    apply_character_delta,
    apply_world_meta_delta,
)
from diary.core.story.generation import (
    ContinuationContext,
    DoneEvent,
    ErrorEvent,
    FilterRejectedEvent,
    ResultEvent,
    StageEvent,
    TokenEvent,
    generate_story,
)
from diary.core.story.metadata import safe_parse_delta
from diary.core.story.mood_input import EMOTION_CHIPS, YES_NO_QUESTIONS
from diary.core.story.prompt_builder import (
    get_continuation_prompt_version,
    get_prompt_version,
    resolve_story_language,
)
from diary.core.style.corpus import has_corpus, load_corpus_chunks
from diary.core.style.profile import has_index, list_author_slugs, load_author_profile
from diary.core.style.retrieval import select_style_chunks

logger = logging.getLogger(__name__)

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
                has_corpus=has_corpus(slug),
            )
        )
    return summaries


@router.get("/form-options", response_model=FormOptions)
def get_form_options() -> FormOptions:
    return FormOptions(
        chips=EMOTION_CHIPS,
        questions=[QuestionOption(**q) for q in YES_NO_QUESTIONS],
    )


@router.get("/helplines", response_model=HelplinesOut)
def get_helplines() -> HelplinesOut:
    settings = get_settings()
    helplines = load_helplines(settings.helplines_locale)
    return HelplinesOut.model_validate(helplines.model_dump())


# --- domain <-> storage conversion ------------------------------------------


def _load_characters(conn, author_slug: str) -> list[CharacterCard]:
    cards = []
    for row in storage.list_characters(conn, author_slug):
        data = storage.character_row_to_dict(row)
        cards.append(
            CharacterCard(
                name=data["name"],
                is_alter_ego=data["is_alter_ego"],
                role=data["role"],
                traits=data["traits"],
                relationships=[Relationship(**r) for r in data["relationships"]],
                status=data["status"],
                locked=data["locked"],
            )
        )
    return cards


def _load_world_meta(conn, author_slug: str) -> WorldMeta:
    row = storage.get_world_meta(conn, author_slug)
    if row is None:
        return WorldMeta()
    return WorldMeta(setting=row["setting"], era=row["era"])


def _retrieve_chunks(profile, mood_input):
    """Simplified retrieval (SPEC 4.4, scoped down — see ASSUMPTIONS.md
    'M2.5'): word-overlap, not embeddings. Empty when the author has no
    corpus files, same graceful degradation as M1's placeholder."""
    if not has_corpus(profile.slug):
        return []
    chunks = load_corpus_chunks(profile)
    return select_style_chunks(chunks, mood_input, k=profile.retrieval.k)


def _persist_result(
    conn,
    *,
    payload: GenerateRequest,
    author_slug: str,
    settings: Settings,
    characters: list[CharacterCard],
    world_meta: WorldMeta,
    result: ResultEvent,
    chapter_id: int | None,
    parent_entry_id: int | None,
    is_continuation: bool,
    input_reasons: tuple[str, ...],
) -> tuple[int, bool, int, str | None]:
    """Applies the validated character delta, saves the entry, and updates
    (or creates) the chapter it belongs to. Runs inside the background
    generation task — the entry MUST be saved even if the client's
    connection already dropped (SPEC 3.3)."""
    delta = safe_parse_delta(result.metadata.character_delta)
    updated_characters = apply_character_delta(characters, delta)
    updated_world_meta = apply_world_meta_delta(world_meta, delta)

    storage.replace_characters(
        conn, author_slug, [c.model_dump(mode="json") for c in updated_characters]
    )
    storage.upsert_world_meta(
        conn, author_slug, setting=updated_world_meta.setting, era=updated_world_meta.era
    )

    if chapter_id is None:
        chapter_id = storage.insert_chapter(conn, author_slug)
    storage.set_chapter_title_if_unset(conn, chapter_id, result.metadata.title)

    prompt_version = get_continuation_prompt_version() if is_continuation else get_prompt_version()

    entry_id = storage.insert_entry(
        conn,
        type="story",
        author_slug=author_slug,
        chapter_id=chapter_id,
        parent_entry_id=parent_entry_id,
        mood_inputs=payload.mood_input.model_dump(),
        title=result.metadata.title,
        story_text=result.story_text,
        story_lang=resolve_story_language(settings.story_language),
        mood_tag=result.metadata.mood_tag,
        summary=result.metadata.summary,
        characters_used=result.metadata.characters_used,
        safety_input_flag=result.input_detected,
        safety_output_result=result.safety_output_result,
        model_used=settings.model_story,
        prompt_version=prompt_version,
        style_profile_version=load_author_profile(author_slug).version,
    )

    if result.input_detected:
        # reasons are rule/regex labels (e.g. "phrase_match:<pattern>"), never the
        # user's own text — safe to log for threshold tuning (mirrors 6.3's intent
        # for the output filter: events logged locally, without content).
        verdict = "triggered:" + ",".join(input_reasons)[:180] if input_reasons else "triggered"
        storage.insert_safety_event(conn, entry_id=entry_id, stage="input_detector", verdict=verdict)
    if result.safety_output_result != "pass":
        storage.insert_safety_event(
            conn, entry_id=entry_id, stage="output_filter", verdict=result.safety_output_result
        )

    banner = result.input_detected or result.safety_output_result != "pass"
    chapter_title = storage.get_chapter(conn, chapter_id)["title"]
    return entry_id, banner, chapter_id, chapter_title


async def _run_generation(generation_id: str, payload: GenerateRequest, settings: Settings) -> None:
    """Runs the full pipeline in the background, independent of the HTTP
    request that started it (SPEC 3.3's server-side stream buffer): a dropped
    client connection does not stop or restart generation."""
    buffer = get_buffer(generation_id)
    assert buffer is not None

    try:
        try:
            profile = load_author_profile(payload.author_slug)
        except FileNotFoundError as exc:
            buffer.append("error", json.dumps({"message": str(exc)}))
            return

        conn = storage.get_connection(settings.db_path)
        try:
            adapter = build_adapter(settings)
            detection = detect(payload.mood_input)
            characters = _load_characters(conn, payload.author_slug)
            world_meta = _load_world_meta(conn, payload.author_slug)
            retrieved_chunks = _retrieve_chunks(profile, payload.mood_input)

            continuation = None
            chapter_id = payload.continue_chapter_id
            parent_entry_id = None
            if chapter_id is not None:
                chapter_row = storage.get_chapter(conn, chapter_id)
                if (
                    chapter_row is None
                    or chapter_row["author_slug"] != profile.slug
                    or chapter_row["status"] != "open"
                ):
                    buffer.append(
                        "error",
                        json.dumps(
                            {"message": "Nie można kontynuować — rozdział nie istnieje lub jest zamknięty."}
                        ),
                    )
                    return
                entry_rows = storage.list_entries_for_chapter(conn, chapter_id)
                tail_text = build_chapter_tail([row["story_text"] for row in entry_rows])
                continuation = ContinuationContext(chapter_tail_text=tail_text)
                parent_entry_id = entry_rows[-1]["id"] if entry_rows else None

            async for event in generate_story(
                adapter=adapter,
                profile=profile,
                mood_input=payload.mood_input,
                model=settings.model_story,
                model_helper=settings.model_helper,
                temperature=settings.temperature,
                story_language=settings.story_language,
                characters=characters,
                world_meta=world_meta,
                retrieved_chunks=retrieved_chunks,
                continuation=continuation,
                input_detected=detection.triggered,
            ):
                if isinstance(event, StageEvent):
                    buffer.append("stage", json.dumps({"stage": event.stage}))
                elif isinstance(event, TokenEvent):
                    buffer.append("token", json.dumps({"text": event.text}))
                elif isinstance(event, FilterRejectedEvent):
                    buffer.append("filter_rejected", json.dumps({"message": event.message}))
                elif isinstance(event, ErrorEvent):
                    buffer.append("error", json.dumps({"message": event.message}))
                elif isinstance(event, ResultEvent):
                    entry_id, banner, result_chapter_id, chapter_title = _persist_result(
                        conn,
                        payload=payload,
                        author_slug=profile.slug,
                        settings=settings,
                        characters=characters,
                        world_meta=world_meta,
                        result=event,
                        chapter_id=chapter_id,
                        parent_entry_id=parent_entry_id,
                        is_continuation=continuation is not None,
                        input_reasons=detection.reasons,
                    )
                    buffer.append(
                        "result",
                        json.dumps(
                            {
                                "entry_id": entry_id,
                                "chapter_id": result_chapter_id,
                                "chapter_title": chapter_title,
                                "title": event.metadata.title,
                                "mood_tag": event.metadata.mood_tag,
                                "characters_used": event.metadata.characters_used,
                                "safety_output_result": event.safety_output_result,
                                "banner": banner,
                                "prompt_version": (
                                    get_continuation_prompt_version()
                                    if continuation is not None
                                    else get_prompt_version()
                                ),
                                "style_profile_version": profile.version,
                            }
                        ),
                    )
                elif isinstance(event, DoneEvent):
                    buffer.append("done", "{}")
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        logger.exception("Nieoczekiwany błąd generacji w tle (generation_id=%s)", generation_id)
        buffer.append("error", json.dumps({"message": "Nieoczekiwany błąd serwera. Szczegóły w logach."}))
    finally:
        buffer.mark_finished()


async def _stream_from_buffer(buffer: GenerationBuffer, *, after: int) -> AsyncIterator[dict[str, str]]:
    index = after
    while True:
        while index < len(buffer.events):
            item = buffer.events[index]
            yield {"event": item.event, "data": item.data}
            index += 1
        if buffer.finished:
            return
        await buffer.wait_for_more()


async def _initial_stream(generation_id: str, buffer: GenerationBuffer) -> AsyncIterator[dict[str, str]]:
    yield {"event": "init", "data": json.dumps({"generation_id": generation_id})}
    async for item in _stream_from_buffer(buffer, after=0):
        yield item


@router.post("/generate")
async def generate(payload: GenerateRequest) -> EventSourceResponse:
    if payload.author_slug not in list_author_slugs():
        raise HTTPException(status_code=404, detail=f"Nieznany autor: {payload.author_slug}")

    overrides = payload.overrides.model_dump(exclude_none=True)
    if "model_story" in overrides and "model_helper" not in overrides:
        # Bez tego, zmiana samego "Model (opowiadanie)" na innego dostawcę
        # (np. Gemini) zostawiała model_helper na domyślnym "gpt-4o-mini" z
        # bazowych Settings — metadane/filtr wyjścia (oba na model_helper)
        # leciałyby pod ten sam base_url z nazwą modelu z zupełnie innego
        # providera i dostawałyby 400. Domyślnie: ten sam model co opowiadanie,
        # użytkownik może to nadpisać osobno w drawerze, jeśli chce taniej.
        overrides["model_helper"] = overrides["model_story"]
    effective_settings = get_settings().model_copy(update=overrides)

    generation_id = uuid.uuid4().hex
    buffer = create_buffer(generation_id)
    asyncio.create_task(_run_generation(generation_id, payload, effective_settings))

    return EventSourceResponse(_initial_stream(generation_id, buffer))


@router.get("/generate/{generation_id}/resume")
async def resume_generate(generation_id: str, after: int = 0) -> EventSourceResponse:
    buffer = get_buffer(generation_id)
    if buffer is None:
        raise HTTPException(status_code=404, detail="Nieznane lub wygasłe generowanie — wygeneruj od nowa.")
    return EventSourceResponse(_stream_from_buffer(buffer, after=after))


# --- book interface ("Zakończ ten rozdział" / "Twoja książka") -------------


@router.post("/chapters/{chapter_id}/close", response_model=ChapterOut)
def close_chapter(chapter_id: int) -> ChapterOut:
    settings = get_settings()
    conn = storage.get_connection(settings.db_path)
    try:
        chapter = storage.get_chapter(conn, chapter_id)
        if chapter is None:
            raise HTTPException(status_code=404, detail="Nieznany rozdział.")
        if chapter["status"] == "open":
            entries = storage.list_entries_for_chapter(conn, chapter_id)
            summary = summarize_chapter([row["summary"] or "" for row in entries])
            storage.close_chapter(conn, chapter_id, summary=summary)
            chapter = storage.get_chapter(conn, chapter_id)
        return ChapterOut(
            id=chapter["id"],
            status=chapter["status"],
            title=chapter["title"],
            summary=chapter["summary"],
        )
    finally:
        conn.close()


@router.get("/authors/{slug}/book", response_model=BookOut)
def get_book(slug: str) -> BookOut:
    if slug not in list_author_slugs():
        raise HTTPException(status_code=404, detail=f"Nieznany autor: {slug}")

    settings = get_settings()
    conn = storage.get_connection(settings.db_path)
    try:
        chapters_out = []
        for chapter in storage.list_chapters_for_author(conn, slug):
            entries = storage.list_entries_for_chapter(conn, chapter["id"])
            chapters_out.append(
                BookChapterOut(
                    id=chapter["id"],
                    status=chapter["status"],
                    title=chapter["title"],
                    summary=chapter["summary"],
                    created_at=chapter["created_at"],
                    closed_at=chapter["closed_at"],
                    entries=[
                        BookEntryOut(id=row["id"], story_text=row["story_text"], created_at=row["created_at"])
                        for row in entries
                    ],
                )
            )
        return BookOut(author_slug=slug, chapters=chapters_out)
    finally:
        conn.close()
