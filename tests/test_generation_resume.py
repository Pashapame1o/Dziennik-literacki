"""Server-side stream buffer + resume (SPEC 3.3, 5.6): a dropped connection
must be able to replay from where it left off instead of regenerating.

The HTTP-level tests replay from an offset against an already-finished
generation (deterministic: no need to race a live background task against a
simulated mid-stream disconnect). The lower-level test exercises the same
`_stream_from_buffer` offset logic directly against a buffer populated by
actually running `_run_generation`, which is the part that matters: does
reading from `after=k` reproduce exactly the tail of what a fresh read from
0 would have produced, and never re-invoke the adapter.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from diary.app.generation_registry import create as create_buffer
from diary.app.main import create_app
from diary.app.routes import _run_generation, _stream_from_buffer
from diary.core.llm.mock import MockAdapter
from diary.core.safety.output_filter import OutputFilterVerdict
from diary.core.settings import Settings
from diary.core.story.metadata import StoryMetadata
from diary.app.schemas import GenerateRequest

from tests.test_generate_endpoint import _passing_adapter, _payload


def _parse_sse_kinds(body: str) -> list[str]:
    kinds = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("event:"):
                kinds.append(line[len("event:"):].strip())
    return kinds


@pytest.fixture
def client_and_settings(monkeypatch, tmp_path):
    adapter = _passing_adapter(chunks=["Rano ", "padał ", "deszcz."])
    monkeypatch.setattr("diary.app.routes.build_adapter", lambda settings: adapter)
    test_settings = Settings(db_path=str(tmp_path / "resume.db"))
    monkeypatch.setattr("diary.app.routes.get_settings", lambda: test_settings)
    return TestClient(create_app()), adapter


def test_resume_unknown_generation_id_returns_404(client_and_settings):
    client, _ = client_and_settings
    response = client.get("/api/generate/not-a-real-id/resume")
    assert response.status_code == 404


def test_resume_after_full_completion_replays_only_the_tail(client_and_settings):
    client, adapter = client_and_settings

    first = client.post("/api/generate", json=_payload())
    all_kinds = _parse_sse_kinds(first.text)
    generation_id = json.loads(
        next(
            block.split("data:")[1].strip()
            for block in first.text.replace("\r\n", "\n").split("\n\n")
            if block.startswith("event: init")
        )
    )["generation_id"]

    total_events = len(all_kinds) - 1  # minus the one-off "init" event, not stored in the buffer

    resumed = client.get(f"/api/generate/{generation_id}/resume", params={"after": total_events - 2})
    assert resumed.status_code == 200
    resumed_kinds = _parse_sse_kinds(resumed.text)

    assert resumed_kinds == all_kinds[-2:]  # exactly the last two real events (e.g. result, done)
    assert len(adapter.received_messages_history) == 1  # resume did NOT trigger a second generation


def test_resume_from_zero_after_completion_replays_everything(client_and_settings):
    client, _ = client_and_settings

    first = client.post("/api/generate", json=_payload())
    all_kinds = _parse_sse_kinds(first.text)
    generation_id = json.loads(
        next(
            block.split("data:")[1].strip()
            for block in first.text.replace("\r\n", "\n").split("\n\n")
            if block.startswith("event: init")
        )
    )["generation_id"]

    resumed = client.get(f"/api/generate/{generation_id}/resume", params={"after": 0})
    resumed_kinds = _parse_sse_kinds(resumed.text)

    assert resumed_kinds == all_kinds[1:]  # everything except the one-off "init"


@pytest.mark.asyncio
async def test_stream_from_buffer_offset_matches_tail_of_full_replay(tmp_path, monkeypatch):
    """Runs the real background pipeline to completion, then checks that
    reading from an offset reproduces exactly the tail of a from-scratch read."""
    adapter = _passing_adapter(chunks=["Rano ", "padał ", "deszcz."])
    settings = Settings(db_path=str(tmp_path / "direct.db"))
    payload = GenerateRequest.model_validate(_payload())

    monkeypatch.setattr("diary.app.routes.build_adapter", lambda s: adapter)
    buffer = create_buffer("direct-test")
    await _run_generation("direct-test", payload, settings)

    full = [item async for item in _stream_from_buffer(buffer, after=0)]
    partial = [item async for item in _stream_from_buffer(buffer, after=len(full) - 3)]

    assert partial == full[-3:]
    assert full[-1]["event"] == "done"
    assert len(adapter.received_messages_history) == 1
