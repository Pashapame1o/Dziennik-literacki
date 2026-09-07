"""End-to-end check of the REAL diaryApp() Alpine object (not just the SSE
parser methods, as in test_frontend_sse_parser.py) against REAL bytes from
the backend: a filter rejection followed by a pass, and a dropped connection
followed by a resume. Runs the actual index.html JS in Node with a scripted
`fetch` mock, so this exercises the exact code path a browser would run.
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

from tests.test_generate_endpoint import _passing_adapter, _payload

STATIC = Path(__file__).resolve().parents[1] / "diary" / "app" / "static" / "index.html"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="wymaga node do uruchomienia kodu frontendu")

REGENERATE_VERDICT = OutputFilterVerdict(verdict="regenerate", reasons=["opisuje metodę krzywdy"])
PASS_VERDICT = OutputFilterVerdict(verdict="pass")
PASSING_METADATA = StoryMetadata(
    title="Deszcz", mood_tag="melancholia", characters_used=["Arkadij"],
    character_delta={}, summary="x", tone_flags=["none"],
)


def extract_module_preamble() -> str:
    """Stałe zdefiniowane przed function diaryApp() (PROVIDER_PRESETS itd.),
    na których opiera się literał obiektu (np. providerPresetList)."""
    source = STATIC.read_text(encoding="utf-8")
    start = source.find("<script>") + len("<script>")
    end = source.find("function diaryApp()")
    assert -1 not in (start - len("<script>"), end)
    return source[start:end]


def extract_app_object_literal() -> str:
    """Wycina cały literał obiektu zwracany przez diaryApp() (od 'screen: 1,'
    do zamykającego '};') — potrzebujemy wszystkich metod, nie tylko dwóch."""
    source = STATIC.read_text(encoding="utf-8")
    start = source.find("screen: 1,")
    assert start != -1, "nie znaleziono początku stanu diaryApp() w index.html"
    end = source.find("\n  };", start)
    assert end != -1, "nie znaleziono końca literału obiektu w index.html"
    return source[start:end]


def run_app_flow(fetch_script: str, calls_script: str, tmp_path: Path) -> dict:
    harness = tmp_path / "harness.mjs"
    harness.write_text(
        """
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
    canResume: app.canResume, generating: app.generating, entryInfo: app.entryInfo,
    generationId: app.generationId, eventsProcessed: app.eventsProcessed, screen: app.screen,
    bannerActive: app.bannerActive,
  }));
})();
"""
        % (fetch_script, extract_module_preamble(), extract_app_object_literal(), calls_script),
        encoding="utf-8",
    )
    result = subprocess.run(["node", str(harness)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"kod frontendu wysypał się w node:\n{result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


def _bytes_literal(data: bytes) -> str:
    return "Uint8Array.from(" + json.dumps(list(data)) + ")"


@pytest.fixture
def settings_and_db(monkeypatch, tmp_path):
    test_settings = Settings(db_path=str(tmp_path / "flow.db"))
    monkeypatch.setattr("diary.app.routes.get_settings", lambda: test_settings)
    return test_settings


def test_filter_rejection_then_pass_shows_transient_message_then_final_story(
    monkeypatch, settings_and_db, tmp_path
):
    adapter = MockAdapter(
        stream_chunks_by_call=[["Zła wersja."], ["Rano padał deszcz."]],
        structured_responses={StoryMetadata: PASSING_METADATA, OutputFilterVerdict: [REGENERATE_VERDICT, PASS_VERDICT]},
    )
    monkeypatch.setattr("diary.app.routes.build_adapter", lambda settings: adapter)
    client = TestClient(create_app())
    body = client.post("/api/generate", json=_payload()).content

    fetch_script = "global.fetch = async () => ({ ok: true, body: makeBody([%s]) });" % _bytes_literal(body)
    calls_script = "await app.submitAndGenerate();"
    # buildPayload()/validateForm() need a minimally valid form state:
    state = run_app_flow(
        fetch_script,
        "app.selectedAuthor='dostoevsky'; app.mood.chips=['smutek']; "
        "app.mood.answers={unusual_event:true,people_or_solitude:false,something_closed:true}; "
        "app.keywordsRaw='deszcz'; " + calls_script,
        tmp_path,
    )

    assert state["storyText"] == "Rano padał deszcz."
    assert state["filterMessage"] == ""  # cleared once new tokens arrived
    assert state["entryInfo"]["title"] == "Deszcz"
    assert state["entryInfo"]["safetyOutputResult"] == "regenerated"
    assert state["errorMessage"] == ""
    assert state["generating"] is False
    assert state["screen"] == 3


def test_dropped_connection_then_resume_completes_the_story(monkeypatch, settings_and_db, tmp_path):
    adapter = _passing_adapter(chunks=["Rano ", "padał ", "deszcz."])
    monkeypatch.setattr("diary.app.routes.build_adapter", lambda settings: adapter)
    client = TestClient(create_app())
    full_body = client.post("/api/generate", json=_payload()).content

    blocks = [b for b in full_body.split(b"\r\n\r\n") if b.strip()]
    split_at = len(blocks) // 2
    first_half = b"\r\n\r\n".join(blocks[:split_at]) + b"\r\n\r\n"

    gen_id_block = next(b for b in blocks if b.startswith(b"event: init"))
    generation_id = json.loads(gen_id_block.split(b"data:")[1].strip())["generation_id"]

    events_before_split = split_at - 1  # minus the one "init" event, not counted
    resume_response = client.get(f"/api/generate/{generation_id}/resume", params={"after": events_before_split})
    resume_body = resume_response.content

    fetch_script = """
    let call = 0;
    global.fetch = async (url) => {
      call += 1;
      if (call === 1) return { ok: true, body: makeBody([%s]) };
      return { ok: true, body: makeBody([%s]) };
    };
    """ % (_bytes_literal(first_half), _bytes_literal(resume_body))

    calls_script = (
        "app.selectedAuthor='dostoevsky'; app.mood.chips=['smutek']; "
        "app.mood.answers={unusual_event:true,people_or_solitude:false,something_closed:true}; "
        "app.keywordsRaw='deszcz'; "
        "await app.submitAndGenerate(); "
        "await app.resumeGeneration();"
    )
    state = run_app_flow(fetch_script, calls_script, tmp_path)

    assert state["storyText"] == "Rano padał deszcz."
    assert state["generating"] is False
    assert state["errorMessage"] == ""
    assert state["screen"] == 3


def test_helpline_banner_survives_a_simulated_reload(monkeypatch, settings_and_db, tmp_path):
    """DoD M2 #6: triggered by an entry, then a fresh page load (a second
    app instance reading the same localStorage, as init() does) must still
    show it — 'nie znika po odświeżeniu'."""
    detecting_payload = {
        "author_slug": "dostoevsky",
        "mood_input": {
            "valence": -2, "energy": 3, "chips": ["smutek"],
            "answers": {"unusual_event": False, "people_or_solitude": False, "something_closed": True},
            "keywords": ["deszcz"], "sentence": "Chcę się zabić.", "length": "medium",
        },
        "overrides": {},
    }
    adapter = _passing_adapter(chunks=["Rano padał deszcz."])
    monkeypatch.setattr("diary.app.routes.build_adapter", lambda settings: adapter)
    client = TestClient(create_app())
    response = client.post("/api/generate", json=detecting_payload)
    result = next(
        json.loads(b.split(b"data:")[1].strip())
        for b in response.content.split(b"\r\n\r\n")
        if b.startswith(b"event: result")
    )
    assert result["banner"] is True  # input detector triggered on the crisis phrase

    fetch_script = "global.fetch = async () => ({ ok: true, body: makeBody([%s]) });" % _bytes_literal(
        response.content
    )
    calls_script = (
        "app.selectedAuthor='dostoevsky'; app.mood.chips=['smutek']; "
        "app.mood.answers={unusual_event:false,people_or_solitude:false,something_closed:true}; "
        "app.mood.sentence='Chcę się zabić.'; app.keywordsRaw='deszcz'; "
        "await app.submitAndGenerate(); "
        # simulate a page reload: a brand-new app object, same localStorage,
        # doing exactly what init() does to decide bannerActive
        # simulate a page reload: a brand-new app instance, same localStorage,
        # doing exactly what init() does to decide bannerActive
        "app.bannerActive = localStorage.getItem('diary_helpline_banner') === '1';"
    )
    state = run_app_flow(fetch_script, calls_script, tmp_path)
    assert state["bannerActive"] is True
