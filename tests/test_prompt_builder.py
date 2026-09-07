import json
import re

from diary.core.story.mood_input import MoodInput
from diary.core.story.prompt_builder import build_prompt
from diary.core.style.profile import load_author_profile


def _sample_mood_input() -> MoodInput:
    return MoodInput(
        valence=-2,
        energy=4,
        chips=["smutek", "znużenie"],
        answers={
            "unusual_event": False,
            "people_or_solitude": True,
            "afraid_tomorrow": True,
        },
        keywords=["deszcz", "cisza"],
        sentence="Nic się dziś nie wydarzyło, a mimo to jestem zmęczony.",
        length="short",
    )


def test_layer_order_matches_narrator_template():
    # narrator.md's own header says "Kolejność warstw MUST pozostać" — the
    # template's physical section order is the source of truth, not a
    # re-derivation of SPEC 5.1's conceptual layer numbering.
    profile = load_author_profile("dostoevsky")
    prompt = build_prompt(profile=profile, mood_input=_sample_mood_input())

    role_idx = prompt.find("narratorem piszącym w stylu")
    style_idx = prompt.find("## STYL")
    chunks_idx = prompt.find("## WZORCE STYLU")
    world_idx = prompt.find("## ŚWIAT TEGO DZIENNIKA")
    narration_idx = prompt.find("## ZASADY NARRACJI")
    safety_idx = prompt.find("## ZASADY BEZPIECZEŃSTWA")
    data_idx = prompt.find("## DANE WEJŚCIOWE")
    format_idx = prompt.find("## FORMAT")

    indices = (role_idx, style_idx, chunks_idx, world_idx, narration_idx, safety_idx, data_idx, format_idx)
    assert -1 not in indices
    assert list(indices) == sorted(indices)


def test_no_leftover_template_placeholders_or_comments():
    profile = load_author_profile("dostoevsky")
    prompt = build_prompt(profile=profile, mood_input=_sample_mood_input())

    unresolved_placeholders = [
        "{author_name}", "{story_lang}", "{style_card}", "{retrieved_chunks}",
        "{world_state_brief}", "{safety_rules}", "{delimiter_open}",
        "{delimiter_close}", "{mood_input_json}", "{target_words}",
    ]
    for placeholder in unresolved_placeholders:
        assert placeholder not in prompt
    assert "<!--" not in prompt
    assert "streak_shift" not in prompt


def test_input_is_json_wrapped_in_random_per_request_delimiter():
    profile = load_author_profile("dostoevsky")
    mood_input = _sample_mood_input()

    prompt_a = build_prompt(profile=profile, mood_input=mood_input)
    prompt_b = build_prompt(profile=profile, mood_input=mood_input)

    match = re.search(r"(<<<DATA_[0-9a-f]+>>>)\n(.*?)\n(<<<DATA_[0-9a-f]+>>>)", prompt_a, re.DOTALL)
    assert match is not None
    open_token, json_blob, close_token = match.groups()
    assert open_token == close_token  # same random token wraps both sides

    parsed = json.loads(json_blob)
    assert parsed["valence"] == -2
    assert parsed["chips"] == ["smutek", "znużenie"]

    # random per request: two builds for the same input must not share a token
    token_a = re.search(r"<<<DATA_([0-9a-f]+)>>>", prompt_a).group(1)
    token_b = re.search(r"<<<DATA_([0-9a-f]+)>>>", prompt_b).group(1)
    assert token_a != token_b


def test_missing_index_and_world_state_are_explicit_placeholders():
    profile = load_author_profile("dostoevsky")
    prompt = build_prompt(profile=profile, mood_input=_sample_mood_input())

    assert "brak indeksu korpusu" in prompt
    assert "brak zapisanego świata" in prompt
