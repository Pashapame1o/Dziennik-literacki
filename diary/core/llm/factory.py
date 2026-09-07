"""Builds the configured LLM adapter from Settings.

M1 ships a single provider (OpenAI-compatible); Anthropic and Ollama
implementations plug in here later without changing call sites.
"""

from __future__ import annotations

from diary.core.llm.base import LLMAdapter
from diary.core.llm.openai_compatible import OpenAICompatibleAdapter
from diary.core.settings import Settings


def build_adapter(settings: Settings) -> LLMAdapter:
    return OpenAICompatibleAdapter(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
