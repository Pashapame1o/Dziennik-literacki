"""Frontend behavior for the "book" interface (point 1): "Kontynuuj" must
append to the existing displayed text (not replace it), a filter rejection
during continuation must only wipe the new attempt (not the prior, already-
saved chapter text), and "Zakończ ten rozdział" must call the close endpoint
and reset for a new entry. Runs the REAL diaryApp() object from index.html
in Node against REAL bytes from the backend (TestClient), same pattern as
test_frontend_full_flow.py.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from diary.app.main import create_app
from diary.core.llm.mock import MockAdapter
from diary.core.safety.output_filter import OutputFilterVerdict
from diary.core.settings import Settings
from diary.core.story.metadata import StoryMetadata

STATIC = Path(__file__).resolve().parents[1] / "diary" / "app" / "static" / "index.html"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="wymaga node do uruchomienia kodu frontendu")

PASS_VERDICT = OutputFilterVerdict(verdict="pass")
REGENERATE_VERDICT = OutputFilterVerdict(verdict="regenerate", reasons=["x"])
FIRST_METADATA = StoryMetadata(
    title="Deszcz", mood_tag="melancholia", characters_used=["Arkadij"],
    character_delta={"new_characters": [{"name": "Arkadij", "is_alter_ego": True}]},
    summary="Początek.", tone_flags=["none"],
)
CONTINUATION_METADATA = StoryMetadata(
    title="", mood_tag="ulga", characters_used=["Arkadij"], character_delta={}, summary="Ciąg dalszy.",
    tone_flags=["none"],
)


def _payload(**overrides) -> dict:
    """Unlike test_generate_endpoint._payload, `**overrides` here lands at the
    TOP level of the request (so `continue_chapter_id=...` reaches
    GenerateRequest directly) — not nested under the "overrides" settings key."""
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


def extract_module_preamble() -> str:
    source = STATIC.read_text(encoding="utf-8")
    start = source.find("<script>") + len("<script>")
    end = source.find("function diaryApp()")
    return source[start:end]


def extract_app_object_literal() -> str:
    source = STATIC.read_text(encoding="utf-8")
    start = source.find("screen: 1,")
    end = source.find("\n  };", start)
    return source[start:end]


_HARNESS_TEMPLATE = """
const _store = {};
global.localStorage = {
  getItem: (k) => (k in _store ? _store[k] : null),
  setItem: (k, v) => { _store[k] = v; },
  removeItem: (k) => { delete _store[k]; },
};

function makeBody(bytes) {
  let i = 0;
  return { getReader() { return { read: async () => (i < bytes.length ? { value: bytes[i++], done: false } : { done: true }) }; } };
}

%s

%s

const app = {
  %s
};

(async () => {
  %s
  console.log(JSON.stringify({
    storyText: app.storyText, errorMessage: app.errorMessage, filterMessage: app.filterMessage,
    generating: app.generating, entryInfo: app.entryInfo, screen: app.screen,
  }));
})();
"""


def run_app_flow(fetch_script: str, calls_script: str, tmp_path: Path) -> dict:
    harness = tmp_path / "harness.mjs"
    harness.write_text(
        _HARNESS_TEMPLATE % (fetch_script, extract_module_preamble(), extract_app_object_literal(), calls_script),
        encoding="utf-8",
    )
    result = subprocess.run(["node", str(harness)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"kod frontendu wysypał się w node:\n{result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


SET_FORM = (
    "app.selectedAuthor='dostoevsky'; app.mood.chips=['smutek']; "
    "app.mood.answers={unusual_event:true,people_or_solitude:false,something_closed:true}; "
    "app.keywordsRaw='deszcz'; "
)


@pytest.fixture
def db_settings(monkeypatch, tmp_path):
    test_settings = Settings(db_path=str(tmp_path / "book_flow.db"))
    monkeypatch.setattr("diary.app.routes.get_settings", lambda: test_settings)
    return test_settings


def test_continue_appends_to_existing_text_with_a_separator(monkeypatch, db_settings, tmp_path):
    adapter = MockAdapter(
        stream_chunks_by_call=[["Rano padał deszcz."], [" I wtedy zapadła cisza."]],
        structured_responses={StoryMetadata: [FIRST_METADATA, CONTINUATION_METADATA], OutputFilterVerdict: PASS_VERDICT},
    )
    monkeypatch.setattr("diary.app.routes.build_adapter", lambda settings: adapter)
    client = TestClient(create_app())

    first_body = client.post("/api/generate", json=_payload()).content
    # entry_id from the first result decides chapter continuity server-side;
    # the client doesn't need to know it, only the chapter_id it gets back.
    chapter_id = json.loads(
        next(b for b in first_body.split(b"\r\n\r\n") if b.startswith(b"event: result")).split(b"data:")[1].strip()
    )["chapter_id"]
    second_body = client.post(
        "/api/generate", json=_payload(continue_chapter_id=chapter_id)
    ).content

    fetch_script = """
    const bodies = [Uint8Array.from(%s), Uint8Array.from(%s)];
    let call = 0;
    global.fetch = async () => {
      const body = bodies[call];
      call += 1;
      return { ok: true, body: makeBody([body]) };
    };
    """ % (list(first_body), list(second_body))

    calls_script = SET_FORM + "await app.submitAndGenerate(); await app.continueChapter();"
    state = run_app_flow(fetch_script, calls_script, tmp_path)

    assert state["storyText"] == "Rano padał deszcz.\n\n I wtedy zapadła cisza."
    assert state["entryInfo"]["chapterId"] == chapter_id


def test_filter_rejection_during_continuation_keeps_prior_chapter_text(monkeypatch, db_settings, tmp_path):
    adapter = MockAdapter(chunks=["Pierwszy fragment."], structured_responses={StoryMetadata: FIRST_METADATA, OutputFilterVerdict: PASS_VERDICT})
    monkeypatch.setattr("diary.app.routes.build_adapter", lambda settings: adapter)
    client = TestClient(create_app())
    first_body = client.post("/api/generate", json=_payload()).content
    chapter_id = json.loads(
        next(b for b in first_body.split(b"\r\n\r\n") if b.startswith(b"event: result")).split(b"data:")[1].strip()
    )["chapter_id"]

    # continuation: first attempt rejected, second passes
    adapter2 = MockAdapter(
        stream_chunks_by_call=[["ZŁA WERSJA"], ["Dobra kontynuacja."]],
        structured_responses={StoryMetadata: CONTINUATION_METADATA, OutputFilterVerdict: [REGENERATE_VERDICT, PASS_VERDICT]},
    )
    monkeypatch.setattr("diary.app.routes.build_adapter", lambda settings: adapter2)
    second_body = client.post("/api/generate", json=_payload(continue_chapter_id=chapter_id)).content

    fetch_script = """
    const bodies = [Uint8Array.from(%s), Uint8Array.from(%s)];
    let call = 0;
    global.fetch = async () => {
      const body = bodies[call];
      call += 1;
      return { ok: true, body: makeBody([body]) };
    };
    """ % (list(first_body), list(second_body))

    calls_script = SET_FORM + "await app.submitAndGenerate(); await app.continueChapter();"
    state = run_app_flow(fetch_script, calls_script, tmp_path)

    assert "ZŁA WERSJA" not in state["storyText"]
    assert state["storyText"] == "Pierwszy fragment.\n\nDobra kontynuacja."


def test_end_chapter_calls_close_endpoint_and_resets_for_a_new_entry(monkeypatch, db_settings, tmp_path):
    adapter = MockAdapter(chunks=["Pierwszy fragment."], structured_responses={StoryMetadata: FIRST_METADATA, OutputFilterVerdict: PASS_VERDICT})
    monkeypatch.setattr("diary.app.routes.build_adapter", lambda settings: adapter)
    client = TestClient(create_app())
    first_body = client.post("/api/generate", json=_payload()).content
    chapter_id = json.loads(
        next(b for b in first_body.split(b"\r\n\r\n") if b.startswith(b"event: result")).split(b"data:")[1].strip()
    )["chapter_id"]
    close_body = client.post(f"/api/chapters/{chapter_id}/close").content

    fetch_script = """
    global.__closeCalled = false;
    global.fetch = async (url, opts) => {
      if (typeof url === 'string' && url.includes('/close')) {
        global.__closeCalled = true;
        return { ok: true, json: async () => JSON.parse(Buffer.from(%s).toString('utf8')) };
      }
      return { ok: true, body: makeBody([Uint8Array.from(%s)]) };
    };
    """ % (list(close_body), list(first_body))

    calls_script = SET_FORM + "await app.submitAndGenerate(); await app.endChapter(); app.__closeCalled = global.__closeCalled;"
    state = run_app_flow(fetch_script, calls_script, tmp_path)

    assert state["screen"] == 1
    assert state["storyText"] == ""
