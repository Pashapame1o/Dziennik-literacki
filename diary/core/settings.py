"""Application settings, loaded from env, with per-run overrides via a context manager.

Mirrors the hr-breaker pattern (SPEC section 1 / 3.5): a single base Settings
instance loaded from env/.env, and a contextvar that request handlers can
temporarily override with drawer values (provider, model, key, temperature,
length) without touching the process environment or requiring a restart.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DIARY_", env_file=".env", extra="ignore")

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None

    # Three model slots per SPEC 3.5. Only model_story is used in M1;
    # model_helper (metadata calls) and model_embedding (RAG) are wired
    # starting M2/M3 but kept here so the settings shape doesn't change later.
    model_story: str = "gpt-4o-mini"
    model_helper: str = "gpt-4o-mini"
    model_embedding: str = "text-embedding-3-small"

    temperature: float = 0.9
    default_length: Literal["short", "medium", "long"] = "medium"

    # Language settings are split per SPEC 5.4; ui_language is not yet wired
    # to any translation mechanism in M1 (UI text is hardcoded Polish).
    story_language: str = "auto"
    ui_language: str = "auto"

    timezone: str | None = None

    # M2: SQLite storage (SPEC 7.1) and helpline locale (SPEC 6.5). *.db is
    # gitignored per SPEC 9.1; relative path resolves against the process cwd,
    # matching how `diary serve` is normally run from the repo root.
    db_path: str = "diary.db"
    helplines_locale: str = "pl"


_base_settings = Settings()
_current: ContextVar[Settings] = ContextVar("diary_settings", default=_base_settings)


def get_settings() -> Settings:
    return _current.get()


@contextmanager
def override_settings(**overrides: object) -> Iterator[Settings]:
    """Apply per-run overrides (e.g. from the settings drawer) for the duration of the block."""
    current = get_settings()
    updated = current.model_copy(update=overrides)
    token: Token[Settings] = _current.set(updated)
    try:
        yield updated
    finally:
        _current.reset(token)
