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
        structured_responses: dict[type[BaseModel], list[BaseModel] | BaseModel] | None = None,
        stream_chunks_by_call: list[list[str]] | None = None,
        embedding: list[float] | None = None,
    ) -> None:
        self.chunks = chunks if chunks is not None else ["To był ", "zwyczajny ", "dzień."]
        self.raise_auth_error = raise_auth_error
        self.structured_response = structured_response
        # Keyed by schema class so generate_story's two different calls in one
        # attempt (metadata: StoryMetadata, filter: OutputFilterVerdict) can
        # each get their own canned response. A list is popped in call order
        # (useful for "regenerate, then pass" sequences); a bare instance
        # repeats for every call.
        self._structured_responses: dict[type[BaseModel], list[BaseModel]] = {
            schema: (list(value) if isinstance(value, list) else [value])
            for schema, value in (structured_responses or {}).items()
        }
        # Different chunks per successive generate_stream call, for tests that
        # exercise the regeneration loop (each attempt streams different text).
        # None means every call streams `chunks`.
        self._stream_chunks_by_call = list(stream_chunks_by_call) if stream_chunks_by_call is not None else None
        self._stream_call_count = 0
        self.embedding = embedding or [0.0] * 8
        self.received_messages: list[Message] | None = None
        self.received_messages_history: list[list[Message]] = []

    async def generate_stream(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.9,
    ) -> AsyncIterator[str]:
        self.received_messages = messages
        self.received_messages_history.append(messages)
        if self.raise_auth_error:
            raise LLMAuthError("Nieprawidłowy klucz API — sprawdź ustawienia (ikona ⚙) i spróbuj ponownie.")

        if self._stream_chunks_by_call is not None:
            index = min(self._stream_call_count, len(self._stream_chunks_by_call) - 1)
            chunks = self._stream_chunks_by_call[index]
        else:
            chunks = self.chunks
        self._stream_call_count += 1

        for chunk in chunks:
            yield chunk

    async def generate_structured(
        self,
        messages: list[Message],
        *,
        model: str,
        schema: type[BaseModel],
        temperature: float = 0.2,
    ) -> BaseModel:
        queued = self._structured_responses.get(schema)
        if queued:
            return queued.pop(0) if len(queued) > 1 else queued[0]
        if self.structured_response is not None:
            return self.structured_response
        raise NotImplementedError(f"MockAdapter.generate_structured requires a response for {schema}")

    async def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        return [self.embedding for _ in texts]
