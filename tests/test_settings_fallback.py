"""model_helper fallback (bugfix): overriding model_story to a non-OpenAI
provider without also setting model_helper must not silently keep the
hardcoded OpenAI default — that 400s the metadata/output-filter calls the
moment they run against a provider that doesn't recognize "gpt-4o-mini"."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from diary.app.main import create_app
from diary.core.settings import Settings

from tests.test_generate_endpoint import _passing_adapter, _payload


@pytest.fixture
def client_and_capture(monkeypatch, tmp_path):
    captured = {}

    def _build_adapter(settings):
        captured["model_story"] = settings.model_story
        captured["model_helper"] = settings.model_helper
        return _passing_adapter(chunks=["Coś."])

    monkeypatch.setattr("diary.app.routes.build_adapter", _build_adapter)
    monkeypatch.setattr("diary.app.routes.get_settings", lambda: Settings(db_path=str(tmp_path / "t.db")))
    return TestClient(create_app()), captured


def test_model_helper_follows_model_story_when_not_explicitly_set(client_and_capture):
    client, captured = client_and_capture
    payload = _payload(model_story="gemini-2.5-flash")

    client.post("/api/generate", json=payload)

    assert captured["model_story"] == "gemini-2.5-flash"
    assert captured["model_helper"] == "gemini-2.5-flash"  # not the hardcoded OpenAI default


def test_explicit_model_helper_is_not_overridden(client_and_capture):
    client, captured = client_and_capture
    payload = _payload(model_story="gemini-2.5-flash", model_helper="gemini-2.5-flash-lite")

    client.post("/api/generate", json=payload)

    assert captured["model_helper"] == "gemini-2.5-flash-lite"


def test_no_overrides_at_all_keeps_base_settings_default(client_and_capture):
    client, captured = client_and_capture
    client.post("/api/generate", json=_payload())

    assert captured["model_story"] == "gpt-4o-mini"
    assert captured["model_helper"] == "gpt-4o-mini"
