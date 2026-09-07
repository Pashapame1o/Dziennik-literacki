"""Testy regresyjne dla POST /api/generate na poziomie odpowiedzi HTTP.

Testy w test_generation.py sprawdzały obiekty zdarzeń zwracane przez
generate_story, więc nie widziały, co faktycznie ląduje w ciele odpowiedzi SSE.
Tutaj asercje idą na surowe bajty, które dostaje przeglądarka — w tym na
zapis do bazy, który teraz dzieje się w tle po stronie serwera (SPEC 3.3).
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from diary.app.main import create_app
from diary.core.llm.mock import MockAdapter
from diary.core.safety.output_filter import OutputFilterVerdict
from diary.core.settings import Settings
from diary.core.story.metadata import StoryMetadata

LONG_STORY_CHUNKS = [f"zdanie-{i} " for i in range(400)]

PASSING_METADATA = StoryMetadata(
    title="Deszcz", mood_tag="melancholia", characters_used=["Arkadij"],
    character_delta={}, summary="Krótkie streszczenie.", tone_flags=["none"],
)
PASS_VERDICT = OutputFilterVerdict(verdict="pass")


def _passing_adapter(chunks=None, **structured_overrides) -> MockAdapter:
    structured = {StoryMetadata: PASSING_METADATA, OutputFilterVerdict: PASS_VERDICT}
    structured.update(structured_overrides)
    return MockAdapter(chunks=chunks, structured_responses=structured)


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
def client_with_mock(monkeypatch, tmp_path):
    """Podmienia adapter na MockAdapter i bazę na plik tymczasowy, żeby testy
    nie wychodziły do sieci ani nie dotykały prawdziwego diary.db."""

    def _make(adapter: MockAdapter) -> TestClient:
        monkeypatch.setattr("diary.app.routes.build_adapter", lambda settings: adapter)
        test_settings = Settings(db_path=str(tmp_path / "test.db"))
        monkeypatch.setattr("diary.app.routes.get_settings", lambda: test_settings)
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
    adapter = _passing_adapter(chunks=LONG_STORY_CHUNKS)
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
    adapter = _passing_adapter(chunks=["Rano ", "padał ", "deszcz."])
    client = client_with_mock(adapter)

    body = client.post("/api/generate", json=_payload()).text

    # separator jest CRLF-owy (sse-starlette) — klient MUSI to obsłużyć
    assert "\r\n\r\n" in body
    for block in body.replace("\r\n", "\n").split("\n\n"):
        if block.strip():
            assert block.startswith("event: "), f"blok bez pola event: {block!r}"

    events = parse_sse(body)
    kinds = [kind for kind, _ in events]
    assert kinds[0] == "init"  # generation_id, do wznowienia po zerwanym połączeniu
    assert kinds.count("stage") == 5
    assert kinds.count("token") == 3
    assert "result" in kinds
    assert kinds[-1] == "done"


def test_result_event_carries_entry_id_and_metadata(client_with_mock):
    adapter = _passing_adapter(chunks=["Rano ", "padał ", "deszcz."])
    client = client_with_mock(adapter)

    events = parse_sse(client.post("/api/generate", json=_payload()).text)
    result = json.loads(next(data for kind, data in events if kind == "result"))

    assert isinstance(result["entry_id"], int)
    assert result["title"] == "Deszcz"
    assert result["characters_used"] == ["Arkadij"]
    assert result["safety_output_result"] == "pass"
    assert result["banner"] is False
    assert result["prompt_version"] >= 1
    assert result["style_profile_version"] == 1


def test_input_detection_logs_a_safety_event_without_user_content(client_with_mock, tmp_path):
    """safety_events MUST NOT contain the user's own text (SPEC 6.3/7.1) —
    only rule labels (e.g. which regex matched), useful for tuning thresholds."""
    adapter = _passing_adapter(chunks=["Rano padał deszcz."])
    client = client_with_mock(adapter)

    payload = _payload()
    payload["mood_input"]["sentence"] = "Chcę się zabić."
    response = client.post("/api/generate", json=payload)
    result = json.loads(next(data for kind, data in parse_sse(response.text) if kind == "result"))
    assert result["banner"] is True

    from diary.core.portfolio import storage

    conn = storage.get_connection(str(tmp_path / "test.db"))
    row = conn.execute(
        "SELECT * FROM safety_events WHERE entry_id = ? AND stage = 'input_detector'", (result["entry_id"],)
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["verdict"].startswith("triggered:")
    assert "Chcę się zabić" not in row["verdict"]  # rule label, not the user's sentence


def test_tokens_keep_their_whitespace_exactly(client_with_mock):
    """Spacje na brzegach fragmentów są znaczące — bez nich proza się sklei."""
    adapter = _passing_adapter(chunks=["Rano ", " padał  ", "\n\ndeszcz."])
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


def test_unknown_author_returns_404_before_starting_any_generation(client_with_mock):
    client = client_with_mock(MockAdapter())
    payload = _payload()
    payload["author_slug"] = "nie-ma-takiego-autora"

    response = client.post("/api/generate", json=payload)
    assert response.status_code == 404
