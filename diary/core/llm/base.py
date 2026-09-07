"""Own LLM adapter interface (SPEC 3.5): generate_stream, generate_structured, embed.

Providers (OpenAI-compatible, Anthropic, Ollama) each implement this interface;
callers never talk to a provider SDK directly. `litellm` MAY sit underneath a
future implementation, but the interface itself MUST stay ours.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from pydantic import BaseModel

Message = dict[str, str]  # {"role": "system" | "user" | "assistant", "content": "..."}


class LLMError(Exception):
    """Base class for adapter errors. Message MUST be safe to show directly in the UI."""


class LLMAuthError(LLMError):
    """Invalid or missing API key."""


class LLMRequestError(LLMError):
    """Any other request failure (timeout, rate limit, bad model name, network)."""


class LLMAdapter(ABC):
    @abstractmethod
    def generate_stream(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.9,
    ) -> AsyncIterator[str]:
        """Yield text chunks as they arrive."""

    @abstractmethod
    async def generate_structured(
        self,
        messages: list[Message],
        *,
        model: str,
        schema: type[BaseModel],
        temperature: float = 0.2,
    ) -> BaseModel:
        """Return a single validated instance of `schema`. Used from M2 onward (metadata calls)."""

    @abstractmethod
    async def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        """Return one embedding vector per input text. Used from M3 onward (RAG)."""
