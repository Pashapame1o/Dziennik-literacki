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
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    story_language: str | None = None


class GenerateRequest(BaseModel):
    author_slug: str
    mood_input: MoodInput
    overrides: SettingsOverride = Field(default_factory=SettingsOverride)


class AuthorSummary(BaseModel):
    slug: str
    name: str
    era: str
    expect: str
    has_index: bool


class QuestionOption(BaseModel):
    question_id: str
    text: str


class FormOptions(BaseModel):
    chips: list[str]
    questions: list[QuestionOption]
