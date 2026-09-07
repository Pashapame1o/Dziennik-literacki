"""Request/response shapes for the FastAPI routes."""

from __future__ import annotations

from pydantic import BaseModel, Field

from diary.core.story.mood_input import MoodInput


class SettingsOverride(BaseModel):
    """Per-run overrides from the settings drawer (SPEC 3.5). All optional —
    unset fields fall back to the base Settings loaded from env."""

    llm_base_url: str | None = None
    llm_api_key: str | None = None
    model_story: str | None = None
    model_helper: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    story_language: str | None = None


class GenerateRequest(BaseModel):
    author_slug: str
    mood_input: MoodInput
    overrides: SettingsOverride = Field(default_factory=SettingsOverride)
    # "Kontynuuj" (book interface, point 1): appends to an existing OPEN
    # chapter instead of starting a new, independent one. None = new chapter.
    # The server looks up the chapter's own author/last entry — the client
    # only needs to remember this one id, not individual entry ids.
    continue_chapter_id: int | None = None


class ChapterOut(BaseModel):
    id: int
    status: str
    title: str | None
    summary: str | None


class BookEntryOut(BaseModel):
    id: int
    story_text: str
    created_at: str


class BookChapterOut(BaseModel):
    id: int
    status: str
    title: str | None
    summary: str | None
    created_at: str
    closed_at: str | None
    entries: list[BookEntryOut]


class BookOut(BaseModel):
    author_slug: str
    chapters: list[BookChapterOut]


class HelplineNumberOut(BaseModel):
    label: str
    phone: str


class HelplinesOut(BaseModel):
    locale: str
    footer_text: str
    banner_intro: str
    numbers: list[HelplineNumberOut]


class AuthorSummary(BaseModel):
    slug: str
    name: str
    era: str
    expect: str
    has_index: bool  # M3: persisted, embedding-backed index
    has_corpus: bool  # M2.5: raw corpus files present, used via simplified retrieval


class QuestionOption(BaseModel):
    question_id: str
    text: str


class FormOptions(BaseModel):
    chips: list[str]
    questions: list[QuestionOption]
