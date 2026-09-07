"""OpenAI-compatible implementation of the LLM adapter interface.

Works against the OpenAI API itself and any OpenAI-compatible endpoint
(e.g. a local proxy) by pointing `base_url` elsewhere.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

import httpx
from pydantic import BaseModel

from diary.core.llm.base import LLMAdapter, LLMAuthError, LLMRequestError, Message


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
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
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
                        self._raise_for_status(response)
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data = line[len("data: "):]
                        if data == "[DONE]":
                            return
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        text = delta.get("content")
                        if text:
                            yield text
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
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        try:
            async with self._client() as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise LLMRequestError(f"Nie udało się połączyć z dostawcą modelu: {exc}") from exc
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
