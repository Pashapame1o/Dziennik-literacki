"""Test regresyjny parsera SSE z index.html — uruchamiany w Node.

Sedno błędu z M1: backend wysyłał poprawny, pełny strumień (co potwierdzały
testy pythonowe i curl), ale parser w przeglądarce ciął bufor na '\\n\\n',
podczas gdy sse-starlette rozdziela zdarzenia przez '\\r\\n\\r\\n'. Żaden event
nigdy się nie sparsował, ekran 3 zostawał pusty i nic tego nie zgłaszało.

Ten test bierze PRAWDZIWY kod consumeSse/handleSseEvent z index.html i puszcza
go na PRAWDZIWYCH bajtach z endpointu, dzieląc je na chunki w złośliwych
miejscach — m.in. dokładnie pomiędzy \\r a \\n.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_generate_endpoint import _passing_adapter, _payload  # noqa: PLC2701

STATIC = Path(__file__).resolve().parents[1] / "diary" / "app" / "static" / "index.html"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="wymaga node do uruchomienia kodu frontendu")


def extract_sse_methods() -> str:
    """Wycina finishAfterStream, readSseStream i handleSseEvent z index.html —
    contiguous w tej kolejności, kończąc na zamknięciu literału obiektu."""
    source = STATIC.read_text(encoding="utf-8")
    start_marker = "finishAfterStream() {"
    end_marker = "handleSseEvent(rawEvent) {"

    start = source.find(start_marker)
    assert start != -1, "nie znaleziono finishAfterStream w index.html — test wymaga aktualizacji markerów"
    handler_start = source.find(end_marker, start)
    assert handler_start != -1, "nie znaleziono handleSseEvent w index.html"

    # handleSseEvent jest ostatnią metodą przed zamknięciem literału obiektu
    end = source.find("\n  };", handler_start)
    assert end != -1, "nie znaleziono końca literału obiektu w index.html"
    return source[start:end]


def run_parser(sse_bytes: bytes, chunk_plan: list[bytes], tmp_path: Path) -> dict:
    harness = tmp_path / "harness.mjs"
    chunks_file = tmp_path / "chunks.json"
    chunks_file.write_text(json.dumps([list(c) for c in chunk_plan]), encoding="utf-8")

    harness.write_text(
        """
import { readFileSync } from 'fs';
const chunks = JSON.parse(readFileSync(process.argv[2], 'utf8')).map(a => Uint8Array.from(a));

const methods = {
%s
};

const app = {
  storyText: '', currentStage: '', errorMessage: '', generating: true, screen: 3,
  filterMessage: '', entryInfo: null, eventsProcessed: 0, generationId: null,
  streamEndedCleanly: false, canResume: false,
  readSseStream: methods.readSseStream, handleSseEvent: methods.handleSseEvent,
  finishAfterStream: methods.finishAfterStream,
};

const body = {
  getReader() {
    let i = 0;
    return { read: async () => (i < chunks.length ? { value: chunks[i++], done: false } : { done: true }) };
  },
};

await app.readSseStream(body);
app.finishAfterStream();
console.log(JSON.stringify({
  storyText: app.storyText, currentStage: app.currentStage,
  errorMessage: app.errorMessage, generating: app.generating, screen: app.screen,
}));
"""
        % extract_sse_methods(),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["node", str(harness), str(chunks_file)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"kod frontendu wysypał się w node:\n{result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


def _patch_settings(monkeypatch, tmp_path_factory) -> None:
    from diary.core.settings import Settings

    test_settings = Settings(db_path=str(tmp_path_factory.mktemp("db") / "test.db"))
    monkeypatch.setattr("diary.app.routes.get_settings", lambda: test_settings)


def _real_sse_body(monkeypatch, chunks: list[str], tmp_path_factory) -> bytes:
    from fastapi.testclient import TestClient

    from diary.app.main import create_app

    monkeypatch.setattr("diary.app.routes.build_adapter", lambda settings: _passing_adapter(chunks=chunks))
    _patch_settings(monkeypatch, tmp_path_factory)
    client = TestClient(create_app())
    return client.post("/api/generate", json=_payload()).content


STORY_CHUNKS = ["Rano ", "padał ", "deszcz, ", "a on ", "milczał."] * 40
STORY_TEXT = "".join(STORY_CHUNKS)


def test_browser_parser_renders_the_whole_story(monkeypatch, tmp_path, tmp_path_factory):
    body = _real_sse_body(monkeypatch, STORY_CHUNKS, tmp_path_factory)
    chunks = [body[i : i + 1024] for i in range(0, len(body), 1024)]

    state = run_parser(body, chunks, tmp_path)

    assert state["storyText"] == STORY_TEXT, "ekran 3 nie dostał pełnej prozy"
    assert state["errorMessage"] == ""
    assert state["generating"] is False
    assert state["screen"] == 3


def test_parser_survives_chunk_split_between_cr_and_lf(monkeypatch, tmp_path, tmp_path_factory):
    """Granica pakietu TCP potrafi wypaść w środku CRLF — to nie może gubić eventów."""
    body = _real_sse_body(monkeypatch, STORY_CHUNKS, tmp_path_factory)

    chunks: list[bytes] = []
    cursor = 0
    while cursor < len(body):
        nxt = body.find(b"\r\n", cursor)
        if nxt == -1:
            chunks.append(body[cursor:])
            break
        chunks.append(body[cursor : nxt + 1])  # kończy się na \r
        cursor = nxt + 1  # kolejny chunk zaczyna się od \n

    state = run_parser(body, chunks, tmp_path)
    assert state["storyText"] == STORY_TEXT


def test_parser_handles_one_byte_at_a_time(monkeypatch, tmp_path, tmp_path_factory):
    body = _real_sse_body(monkeypatch, ["Rano ", "padał ", "deszcz."], tmp_path_factory)
    chunks = [body[i : i + 1] for i in range(len(body))]

    state = run_parser(body, chunks, tmp_path)
    assert state["storyText"] == "Rano padał deszcz."


def test_error_event_is_shown_and_sends_user_back_to_the_form(monkeypatch, tmp_path, tmp_path_factory):
    from fastapi.testclient import TestClient

    from diary.app.main import create_app
    from diary.core.llm.mock import MockAdapter

    monkeypatch.setattr("diary.app.routes.build_adapter", lambda settings: MockAdapter(raise_auth_error=True))
    _patch_settings(monkeypatch, tmp_path_factory)
    body = TestClient(create_app()).post("/api/generate", json=_payload()).content

    state = run_parser(body, [body], tmp_path)

    assert "klucz" in state["errorMessage"].lower()
    assert state["screen"] == 2
    assert state["generating"] is False


def test_empty_stream_reports_an_error_instead_of_a_blank_screen(monkeypatch, tmp_path, tmp_path_factory):
    """200 OK bez ani jednego tokenu ma dać komunikat, a nie puste ekran 3."""
    body = _real_sse_body(monkeypatch, [], tmp_path_factory)

    state = run_parser(body, [body], tmp_path)

    assert state["storyText"] == ""
    assert state["errorMessage"] != "", "cicha porażka: pusty ekran bez komunikatu"
    assert state["screen"] == 2
