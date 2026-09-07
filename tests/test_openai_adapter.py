import json

import httpx
import pytest

from diary.core.llm.base import LLMAuthError, LLMRequestError
from diary.core.llm.openai_compatible import OpenAICompatibleAdapter


def _adapter(
    handler, api_key: str | None = "sk-test", base_url: str = "https://example.invalid/v1"
) -> OpenAICompatibleAdapter:
    transport = httpx.MockTransport(handler)
    return OpenAICompatibleAdapter(base_url=base_url, api_key=api_key, transport=transport)


def _empty_stream_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=b"data: [DONE]\n\n", headers={"content-type": "text/event-stream"})


@pytest.mark.asyncio
async def test_bad_key_raises_readable_auth_error_on_stream():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    adapter = _adapter(handler)
    with pytest.raises(LLMAuthError) as excinfo:
        async for _ in adapter.generate_stream([{"role": "user", "content": "hi"}], model="gpt-4o-mini"):
            pass
    assert "klucz" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_missing_key_raises_before_any_request():
    adapter = _adapter(handler=lambda request: httpx.Response(200), api_key=None)
    with pytest.raises(LLMAuthError):
        async for _ in adapter.generate_stream([{"role": "user", "content": "hi"}], model="gpt-4o-mini"):
            pass


@pytest.mark.asyncio
async def test_rate_limit_raises_request_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    adapter = _adapter(handler)
    with pytest.raises(LLMRequestError):
        async for _ in adapter.generate_stream([{"role": "user", "content": "hi"}], model="gpt-4o-mini"):
            pass


@pytest.mark.asyncio
async def test_successful_stream_yields_text_chunks():
    body = (
        b'data: {"choices":[{"delta":{"content":"Cze"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"sc"}}]}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    adapter = _adapter(handler)
    chunks = [c async for c in adapter.generate_stream([{"role": "user", "content": "hi"}], model="gpt-4o-mini")]
    assert "".join(chunks) == "Czesc"


# --- Regresja: konfiguracja z drawera na dostawcę OpenAI-compatible innego niż
# OpenAI (np. Gemini pod https://generativelanguage.googleapis.com/v1beta/openai/)
# musi trafić pod poprawny URL, z poprawnym payloadem i nagłówkiem. Poprzednie
# testy w tym pliku sprawdzały tylko parsowanie odpowiedzi — nigdy nie
# asertowały, co adapter faktycznie wysyła.


@pytest.mark.parametrize(
    "base_url",
    [
        "https://generativelanguage.googleapis.com/v1beta/openai/",  # ze slashem — jak w docach Google
        "https://generativelanguage.googleapis.com/v1beta/openai",  # bez slasha — jak w docach OpenAI
    ],
)
@pytest.mark.asyncio
async def test_chat_completions_url_has_no_duplicated_or_missing_slash(base_url):
    seen_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return _empty_stream_response(request)

    adapter = _adapter(handler, base_url=base_url)
    async for _ in adapter.generate_stream([{"role": "user", "content": "hi"}], model="gemini-2.5-flash"):
        pass

    assert seen_urls == ["https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"]


@pytest.mark.asyncio
async def test_request_payload_has_only_the_universally_supported_fields():
    """Pola specyficzne dla OpenAI (n, logprobs, stream_options, ...), których nie
    wysyłamy, nie mogą się tu pojawić — część bramek OpenAI-compatible odrzuca
    nieznane pola zamiast je ignorować."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _empty_stream_response(request)

    adapter = _adapter(handler)
    async for _ in adapter.generate_stream(
        [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
        model="gemini-2.5-flash",
        temperature=0.7,
    ):
        pass

    assert captured["body"] == {
        "model": "gemini-2.5-flash",
        "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
        "temperature": 0.7,
        "stream": True,
    }


@pytest.mark.asyncio
async def test_authorization_header_is_bearer_scheme():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return _empty_stream_response(request)

    adapter = _adapter(handler, api_key="AQ.some-google-ai-studio-key")
    async for _ in adapter.generate_stream([{"role": "user", "content": "hi"}], model="gemini-2.5-flash"):
        pass

    assert captured["auth"] == "Bearer AQ.some-google-ai-studio-key"


@pytest.mark.asyncio
async def test_generate_structured_url_also_has_no_duplicated_or_missing_slash():
    from pydantic import BaseModel

    class Dummy(BaseModel):
        ok: bool

    seen_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    adapter = _adapter(handler, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    result = await adapter.generate_structured(
        [{"role": "user", "content": "hi"}], model="gemini-2.5-flash", schema=Dummy
    )

    assert seen_urls == ["https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"]
    assert result.ok is True
