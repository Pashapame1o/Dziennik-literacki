import httpx
import pytest

from diary.core.llm.base import LLMAuthError, LLMRequestError
from diary.core.llm.openai_compatible import OpenAICompatibleAdapter


def _adapter(handler, api_key: str | None = "sk-test") -> OpenAICompatibleAdapter:
    transport = httpx.MockTransport(handler)
    return OpenAICompatibleAdapter(base_url="https://example.invalid/v1", api_key=api_key, transport=transport)


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
