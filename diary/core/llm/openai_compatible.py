"""OpenAI-compatible implementation of the LLM adapter interface.

Works against the OpenAI API itself and any OpenAI-compatible endpoint
(e.g. a local proxy) by pointing `base_url` elsewhere.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

import httpx
from pydantic import BaseModel

from diary.core.llm.base import LLMAdapter, LLMAuthError, LLMRequestError, Message

logger = logging.getLogger(__name__)

# One entry costs up to 3 sequential calls (story, metadata, output filter) —
# a provider hiccup on any single one (rate limit, momentary overload) used to
# throw away an already-generated story. These are the status codes providers
# use for exactly that kind of transient condition; retried a couple of times
# with backoff before giving up, so one blip doesn't cost the whole entry.
_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_TRANSIENT_RETRIES = 2
_RETRY_BACKOFF_SECONDS = 1.5


def _is_transient(status_code: int, attempt: int) -> bool:
    return status_code in _TRANSIENT_STATUS_CODES and attempt < _MAX_TRANSIENT_RETRIES

# Some OpenAI-compatible backends (Gemini's compat layer is the known case)
# map `system` -> systemInstruction and everything else -> contents under the
# hood, then 400 ("contents is not specified") if a request has no non-system
# message at all. Real OpenAI tolerates a system-only message list, so this
# only surfaces on other providers — and it has now bitten three independent
# call sites (story generation, metadata, output filter) because each one
# built its own system-only prompt. Fixed once here instead of per-caller:
# this is a wire-protocol compatibility concern (this adapter's actual job),
# not something each caller's prompt-building code should have to know about.
_GENERIC_USER_TURN_TRIGGER = "Respond according to the instructions above."


def _ensure_non_system_turn(messages: list[Message]) -> list[Message]:
    if any(m.get("role") != "system" for m in messages):
        return messages
    return [*messages, {"role": "user", "content": _GENERIC_USER_TURN_TRIGGER}]


class OpenAICompatibleAdapter(LLMAdapter):
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport  # test seam; None uses httpx's real transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise LLMAuthError(
                "Brak klucza API. Ustaw go w panelu ustawień (ikona ⚙) i spróbuj ponownie."
            )
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise LLMAuthError(
                "Nieprawidłowy klucz API — sprawdź ustawienia (ikona ⚙) i spróbuj ponownie."
            )
        if response.status_code == 429:
            raise LLMRequestError("Limit zapytań u dostawcy modelu został przekroczony. Spróbuj za chwilę.")
        if response.is_error:
            # The response body only goes to the server log (it may contain
            # provider details, but never the key — that's in the header, not
            # the body) — the user gets a generic message in the UI, but
            # without this there was no way to diagnose a specific 400/500 remotely.
            logger.warning(
                "Model provider returned error %s for %s: %s",
                response.status_code,
                response.request.url,
                response.text[:2000],
            )
            raise LLMRequestError(f"Dostawca modelu zwrócił błąd ({response.status_code}).")

    async def generate_stream(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.9,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "messages": _ensure_non_system_turn(messages),
            "temperature": temperature,
            "stream": True,
        }
        attempt = 0
        while True:
            try:
                async with self._client() as client:
                    async with client.stream(
                        "POST",
                        f"{self._base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    ) as response:
                        if response.status_code != 200:
                            await response.aread()
                            if _is_transient(response.status_code, attempt):
                                attempt += 1
                                await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)
                                continue
                            self._raise_for_status(response)
                        async for line in response.aiter_lines():
                            line = line.rstrip("\r")
                            # some OpenAI-compatible gateways send "data:{...}" with no space
                            if not line.startswith("data:"):
                                continue
                            data = line[len("data:"):].lstrip()
                            if data == "[DONE]":
                                return
                            try:
                                chunk = json.loads(data)
                                delta = chunk["choices"][0].get("delta", {})
                                text = delta.get("content")
                            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                                # one unreadable chunk must not cut off the rest of the story
                                logger.warning("Skipping unreadable SSE chunk from the provider: %r", data[:200])
                                continue
                            if text:
                                yield text
                        return
            except httpx.HTTPError as exc:
                raise LLMRequestError(f"Nie udało się połączyć z dostawcą modelu: {exc}") from exc

    async def generate_structured(
        self,
        messages: list[Message],
        *,
        model: str,
        schema: type[BaseModel],
        temperature: float = 0.2,
    ) -> BaseModel:
        payload = {
            "model": model,
            "messages": _ensure_non_system_turn(messages),
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        attempt = 0
        while True:
            try:
                async with self._client() as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )
            except httpx.HTTPError as exc:
                raise LLMRequestError(f"Nie udało się połączyć z dostawcą modelu: {exc}") from exc
            if _is_transient(response.status_code, attempt):
                attempt += 1
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)
                continue
            self._raise_for_status(response)
            content = response.json()["choices"][0]["message"]["content"]
            return schema.model_validate_json(content)

    async def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        payload = {"model": model, "input": texts}
        try:
            async with self._client() as client:
                response = await client.post(
                    f"{self._base_url}/embeddings",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise LLMRequestError(f"Nie udało się połączyć z dostawcą modelu: {exc}") from exc
        self._raise_for_status(response)
        data = response.json()["data"]
        return [item["embedding"] for item in data]
