"""Testy regresyjne dla POST /api/generate na poziomie odpowiedzi HTTP.

Testy w test_generation.py sprawdzały obiekty zdarzeń zwracane przez
generate_story, więc nie widziały, co faktycznie ląduje w ciele odpowiedzi SSE.
Tutaj asercje idą na surowe bajty, które dostaje przeglądarka.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from diary.app.main import create_app
from diary.core.llm.mock import MockAdapter

LONG_STORY_CHUNKS = [f"zdanie-{i} " for i in range(400)]


def _payload(**overrides: object) -> dict:
    return {
        "author_slug": "dostoevsky",
        "mood_input": {
            "valence": -2,
            "energy": 3,
            "chips": ["smutek"],
            "answers": {
                "unusual_event": False,
                "people_or_solitude": False,
                "something_closed": True,
            },
            "keywords": ["deszcz"],
            "length": "medium",
        },
        "overrides": overrides,
    }


@pytest.fixture
def client_with_mock(monkeypatch):
    """Podmienia adapter na MockAdapter, żeby nie wychodzić do sieci."""

    def _make(adapter: MockAdapter) -> TestClient:
        monkeypatch.setattr("diary.app.routes.build_adapter", lambda settings: adapter)
        return TestClient(create_app())

    return _make


def parse_sse(body: str) -> list[tuple[str, str]]:
    """Parsuje ciało SSE tak, jak wymaga tego spec: CRLF/LF/CR, pola event i data."""
    normalized = body.replace("\r\n", "\n").replace("\r", "\n")
    events: list[tuple[str, str]] = []
    for block in normalized.split("\n\n"):
        if not block.strip():
            continue
        event_type = "message"
        data_lines: list[str] = []
        for line in block.split("\n"):
            if not line or line.startswith(":"):
                continue
            field, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if field == "event":
                event_type = value
            elif field == "data":
                data_lines.append(value)
        if data_lines:
            events.append((event_type, "\n".join(data_lines)))
    return events


def test_full_story_reaches_sse_body_not_just_first_chunk(client_with_mock):
    """Regresja: całe opowiadanie musi trafić do odpowiedzi, nie tylko pierwszy fragment."""
    adapter = MockAdapter(chunks=LONG_STORY_CHUNKS)
    client = client_with_mock(adapter)

    response = client.post("/api/generate", json=_payload())
    assert response.status_code == 200

    events = parse_sse(response.text)
    tokens = [json.loads(data)["text"] for kind, data in events if kind == "token"]

    # co do jednego fragmentu — urwanie po pierwszym chunku wywali ten test
    assert len(tokens) == len(LONG_STORY_CHUNKS)
    assert "".join(tokens) == "".join(LONG_STORY_CHUNKS)
    assert "zdanie-399 " in tokens[-1]
    assert [kind for kind, _ in events][-1] == "done"


def test_sse_body_is_well_formed_and_events_are_separated(client_with_mock):
    """Każdy event musi być domknięty pustą linią, inaczej klient nie ma po czym ciąć."""
    adapter = MockAdapter(chunks=["Rano ", "padał ", "deszcz."])
    client = client_with_mock(adapter)

    body = client.post("/api/generate", json=_payload()).text

    # separator jest CRLF-owy (sse-starlette) — klient MUSI to obsłużyć
    assert "\r\n\r\n" in body
    for block in body.replace("\r\n", "\n").split("\n\n"):
        if block.strip():
            assert block.startswith("event: "), f"blok bez pola event: {block!r}"

    events = parse_sse(body)
    kinds = [kind for kind, _ in events]
    assert kinds.count("stage") == 5
    assert kinds.count("token") == 3
    assert kinds[-1] == "done"


def test_tokens_keep_their_whitespace_exactly(client_with_mock):
    """Spacje na brzegach fragmentów są znaczące — bez nich proza się sklei."""
    adapter = MockAdapter(chunks=["Rano ", " padał  ", "\n\ndeszcz."])
    client = client_with_mock(adapter)

    events = parse_sse(client.post("/api/generate", json=_payload()).text)
    tokens = [json.loads(data)["text"] for kind, data in events if kind == "token"]

    assert tokens == ["Rano ", " padał  ", "\n\ndeszcz."]


def test_auth_error_is_delivered_as_sse_error_event_not_a_dead_stream(client_with_mock):
    adapter = MockAdapter(raise_auth_error=True)
    client = client_with_mock(adapter)

    response = client.post("/api/generate", json=_payload())
    assert response.status_code == 200

    events = parse_sse(response.text)
    errors = [json.loads(data)["message"] for kind, data in events if kind == "error"]
    assert len(errors) == 1
    assert "klucz" in errors[0].lower()
    assert "done" not in [kind for kind, _ in events]


def test_unexpected_adapter_crash_still_produces_an_error_event(client_with_mock):
    """Wyjątek inny niż LLMError nie może po cichu uciąć strumienia."""

    class ExplodingAdapter(MockAdapter):
        async def generate_stream(self, messages, *, model, temperature=0.9):
            yield "Rano "
            raise RuntimeError("nagły zgon dostawcy")

    client = client_with_mock(ExplodingAdapter())

    events = parse_sse(client.post("/api/generate", json=_payload()).text)
    kinds = [kind for kind, _ in events]

    assert "error" in kinds, "strumień umarł bez żadnego komunikatu dla użytkownika"
    assert "done" not in kinds
