"""In-memory LLM adapter for tests. No network calls."""

from __future__ import annotations

from typing import AsyncIterator

from pydantic import BaseModel

from diary.core.llm.base import LLMAdapter, LLMAuthError, Message


class MockAdapter(LLMAdapter):
    def __init__(
        self,
        chunks: list[str] | None = None,
        *,
        raise_auth_error: bool = False,
        structured_response: BaseModel | None = None,
        embedding: list[float] | None = None,
    ) -> None:
        self.chunks = chunks if chunks is not None else ["To był ", "zwyczajny ", "dzień."]
        self.raise_auth_error = raise_auth_error
        self.structured_response = structured_response
        self.embedding = embedding or [0.0] * 8
        self.received_messages: list[Message] | None = None

    async def generate_stream(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.9,
    ) -> AsyncIterator[str]:
        self.received_messages = messages
        if self.raise_auth_error:
            raise LLMAuthError("Nieprawidłowy klucz API — sprawdź ustawienia (ikona ⚙) i spróbuj ponownie.")
        for chunk in self.chunks:
            yield chunk

    async def generate_structured(
        self,
        messages: list[Message],
        *,
        model: str,
        schema: type[BaseModel],
        temperature: float = 0.2,
    ) -> BaseModel:
        if self.structured_response is not None:
            return self.structured_response
        raise NotImplementedError("MockAdapter.generate_structured requires structured_response")

    async def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        return [self.embedding for _ in texts]
