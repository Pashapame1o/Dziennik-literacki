"""Chapter continuity (SPEC 5.2 revised, "book" interface point 1) at the
real HTTP + SQLite layer — not just on directly-constructed domain objects,
per the lesson from M1 (SSE bytes) and M2 (world-state blob): continuity
features get tested against what actually persists and what actually gets
sent to the model on the next real request.

The core thing under test: the M2 world-state blob only ever stored short
recaps (`recent_threads`, capped strings), so it could never have supported
"Kontynuuj" — there was nowhere to keep the literal prior text a
continuation needs. `test_continue_prompt_contains_literal_prior_text_verbatim`
is the regression test that would have caught that gap directly; everything
here builds up to it through the real chapter/entry persistence path.
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

FIRST_METADATA = StoryMetadata(
    title="Pierwszy rozdział",
    mood_tag="niepokój",
    characters_used=["Arkadij", "Ludmiła Iwanowna"],
    character_delta={
        "new_characters": [
            {"name": "Arkadij", "is_alter_ego": True, "role": "student", "status": "żywy"},
            {"name": "Ludmiła Iwanowna", "role": "gospodyni", "status": "żywy"},
        ],
        "setting": "Petersburg, jesień",
    },
    summary="Arkadij poznaje swoją gospodynię Ludmiłę.",
    tone_flags=["none"],
)
CONTINUATION_METADATA = StoryMetadata(
    title="",
    mood_tag="ulga",
    characters_used=["Arkadij"],
    character_delta={"character_updates": [{"name": "Arkadij", "status": "zamyślony"}]},
    summary="Arkadij zostaje sam ze swoimi myślami.",
    tone_flags=["none"],
)
PASS_VERDICT = OutputFilterVerdict(verdict="pass")


def _payload(**overrides) -> dict:
    return {
        "author_slug": "dostoevsky",
        "mood_input": {
            "valence": -2, "energy": 3, "chips": ["smutek"],
            "answers": {"unusual_event": False, "people_or_solitude": False, "something_closed": True},
            "keywords": ["deszcz"], "length": "medium",
        },
        "overrides": {},
        **overrides,
    }


def _result_event(response_text: str) -> dict:
    for block in response_text.replace("\r\n", "\n").split("\n\n"):
        if block.startswith("event: result"):
            data_line = next(line for line in block.split("\n") if line.startswith("data:"))
            return json.loads(data_line[len("data:") :].strip())
    raise AssertionError(f"brak zdarzenia 'result' w odpowiedzi:\n{response_text}")


@pytest.fixture
def client_and_adapter(monkeypatch, tmp_path):
    adapter = MockAdapter(
        stream_chunks_by_call=[
            ["Rano padał deszcz, a Arkadij milczał przy oknie."],
            [" Ludmiła przyniosła mu herbatę, ale nic nie powiedziała."],
        ],
        structured_responses={
            StoryMetadata: [FIRST_METADATA, CONTINUATION_METADATA],
            OutputFilterVerdict: PASS_VERDICT,
        },
    )
    monkeypatch.setattr("diary.app.routes.build_adapter", lambda settings: adapter)
    test_settings = Settings(db_path=str(tmp_path / "book.db"))
    monkeypatch.setattr("diary.app.routes.get_settings", lambda: test_settings)
    return TestClient(create_app()), adapter


def test_new_chapter_creates_an_open_chapter_with_characters_persisted(client_and_adapter):
    client, _ = client_and_adapter

    response = client.post("/api/generate", json=_payload())
    result = _result_event(response.text)

    assert result["chapter_id"] is not None
    assert result["chapter_title"] == "Pierwszy rozdział"

    book = client.get("/api/authors/dostoevsky/book").json()
    assert len(book["chapters"]) == 1
    assert book["chapters"][0]["status"] == "open"
    assert book["chapters"][0]["title"] == "Pierwszy rozdział"
    assert len(book["chapters"][0]["entries"]) == 1


def test_continue_prompt_contains_literal_prior_text_verbatim(client_and_adapter):
    """This is THE regression test for why the M2 world-state blob couldn't
    support continuation: it never stored literal text, only short recaps.
    Here the second request's actual system prompt must contain the FIRST
    entry's story_text byte-for-byte."""
    client, adapter = client_and_adapter

    first_response = client.post("/api/generate", json=_payload())
    chapter_id = _result_event(first_response.text)["chapter_id"]
    first_story_text = "Rano padał deszcz, a Arkadij milczał przy oknie."

    second_response = client.post("/api/generate", json=_payload(continue_chapter_id=chapter_id))
    assert second_response.status_code == 200

    second_system_prompt = adapter.received_messages_history[-1][0]["content"]
    assert first_story_text in second_system_prompt  # verbatim, not a summary


def test_continue_appends_to_the_same_open_chapter_not_a_new_one(client_and_adapter):
    client, _ = client_and_adapter

    first = _result_event(client.post("/api/generate", json=_payload()).text)
    second = _result_event(
        client.post("/api/generate", json=_payload(continue_chapter_id=first["chapter_id"])).text
    )

    assert second["chapter_id"] == first["chapter_id"]
    assert second["entry_id"] != first["entry_id"]

    book = client.get("/api/authors/dostoevsky/book").json()
    assert len(book["chapters"]) == 1  # not two
    assert len(book["chapters"][0]["entries"]) == 2


def test_continue_carries_forward_existing_characters_and_applies_updates(client_and_adapter):
    client, adapter = client_and_adapter

    first = _result_event(client.post("/api/generate", json=_payload()).text)
    client.post("/api/generate", json=_payload(continue_chapter_id=first["chapter_id"]))

    second_prompt = adapter.received_messages_history[-1][0]["content"]
    assert "Ludmiła Iwanowna" in second_prompt  # carried forward, not re-invented
    assert "Petersburg, jesień" in second_prompt


def test_continue_to_unknown_chapter_id_is_a_clean_error_not_a_crash(client_and_adapter):
    client, _ = client_and_adapter
    response = client.post("/api/generate", json=_payload(continue_chapter_id=999999))

    events = [
        line[len("event:") :].strip()
        for block in response.text.replace("\r\n", "\n").split("\n\n")
        for line in block.split("\n")
        if line.startswith("event:")
    ]
    assert "error" in events
    assert "result" not in events


def test_close_chapter_computes_summary_from_entry_summaries(client_and_adapter):
    client, _ = client_and_adapter
    first = _result_event(client.post("/api/generate", json=_payload()).text)
    client.post("/api/generate", json=_payload(continue_chapter_id=first["chapter_id"]))

    response = client.post(f"/api/chapters/{first['chapter_id']}/close")
    assert response.status_code == 200
    chapter = response.json()

    assert chapter["status"] == "closed"
    assert "Arkadij poznaje swoją gospodynię Ludmiłę." in chapter["summary"]
    assert "Arkadij zostaje sam ze swoimi myślami." in chapter["summary"]


def test_closing_an_already_closed_chapter_does_not_change_its_summary(client_and_adapter):
    client, _ = client_and_adapter
    first = _result_event(client.post("/api/generate", json=_payload()).text)

    client.post(f"/api/chapters/{first['chapter_id']}/close")
    second_close = client.post(f"/api/chapters/{first['chapter_id']}/close")

    assert second_close.json()["summary"] == "Arkadij poznaje swoją gospodynię Ludmiłę."


def test_close_unknown_chapter_returns_404(client_and_adapter):
    client, _ = client_and_adapter
    response = client.post("/api/chapters/999999/close")
    assert response.status_code == 404


def test_book_endpoint_orders_chapters_chronologically_with_entries(client_and_adapter):
    client, _ = client_and_adapter
    first = _result_event(client.post("/api/generate", json=_payload()).text)
    client.post(f"/api/chapters/{first['chapter_id']}/close")
    client.post("/api/generate", json=_payload())  # a second, independent chapter

    book = client.get("/api/authors/dostoevsky/book").json()
    assert len(book["chapters"]) == 2
    assert book["chapters"][0]["status"] == "closed"
    assert book["chapters"][1]["status"] == "open"
    assert book["chapters"][0]["entries"][0]["story_text"].startswith("Rano padał deszcz")


def test_book_endpoint_unknown_author_returns_404(client_and_adapter):
    client, _ = client_and_adapter
    response = client.get("/api/authors/nie-ma-takiego/book")
    assert response.status_code == 404
