import json
import re

from diary.core.story.characters import CharacterCard, WorldMeta
from diary.core.story.mood_input import MoodInput
from diary.core.story.prompt_builder import build_continuation_prompt, build_prompt
from diary.core.style.chunking import Chunk
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

    role_idx = prompt.find("narrator writing in the style of")
    style_idx = prompt.find("## STYLE (")
    chunks_idx = prompt.find("## STYLE PATTERNS")
    world_idx = prompt.find("## THE WORLD OF THIS DIARY")
    narration_idx = prompt.find("## NARRATIVE RULES")
    safety_idx = prompt.find("## SAFETY RULES")
    data_idx = prompt.find("## TODAY'S INPUT")
    format_idx = prompt.find("## FORMAT")

    indices = (role_idx, style_idx, chunks_idx, world_idx, narration_idx, safety_idx, data_idx, format_idx)
    assert -1 not in indices
    assert list(indices) == sorted(indices)


def test_no_leftover_template_placeholders_or_comments():
    profile = load_author_profile("dostoevsky")
    prompt = build_prompt(profile=profile, mood_input=_sample_mood_input())

    unresolved_placeholders = [
        "{author_name}", "{story_lang}", "{style_card}", "{retrieved_chunks}",
        "{characters_brief}", "{safety_rules}", "{delimiter_open}",
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


def test_missing_index_and_characters_are_explicit_placeholders():
    profile = load_author_profile("dostoevsky")
    prompt = build_prompt(profile=profile, mood_input=_sample_mood_input())

    assert "no corpus index" in prompt
    assert "no saved world yet" in prompt


def test_existing_characters_are_rendered_into_the_prompt():
    profile = load_author_profile("dostoevsky")
    characters = [
        CharacterCard(name="Arkadij Władymirowicz", is_alter_ego=True),
        CharacterCard(name="Ludmiła Iwanowna", role="gospodyni"),
    ]
    prompt = build_prompt(
        profile=profile, mood_input=_sample_mood_input(),
        characters=characters, world_meta=WorldMeta(setting="Petersburg"),
    )

    assert "Arkadij Władymirowicz" in prompt
    assert "Ludmiła Iwanowna" in prompt
    assert "Petersburg" in prompt
    assert "no saved world yet" not in prompt


def test_reinforced_safety_level_adds_to_baseline_without_dropping_it():
    profile = load_author_profile("dostoevsky")
    baseline = build_prompt(profile=profile, mood_input=_sample_mood_input(), safety_level="baseline")
    reinforced = build_prompt(profile=profile, mood_input=_sample_mood_input(), safety_level="reinforced")

    assert "You do not glorify or aestheticize harm" in baseline
    assert "You do not glorify or aestheticize harm" in reinforced
    assert "not leaving the protagonist alone" not in baseline
    assert "not leaving the protagonist alone" in reinforced


def test_retrieved_chunks_are_rendered_when_present():
    profile = load_author_profile("dostoevsky")
    chunks = [Chunk(text="Fragment stylu autora.", source_file="ksiazka.txt", index=0)]
    prompt = build_prompt(profile=profile, mood_input=_sample_mood_input(), retrieved_chunks=chunks)

    assert "Fragment stylu autora." in prompt
    assert "ksiazka.txt" in prompt
    assert "no corpus index" not in prompt


# --- prompts/continue.md ---


def test_continuation_prompt_contains_literal_chapter_tail_verbatim():
    profile = load_author_profile("dostoevsky")
    tail_text = "...i wtedy Arkadij zamilkł, patrząc na deszcz za oknem."

    prompt = build_continuation_prompt(
        profile=profile, mood_input=_sample_mood_input(), chapter_tail_text=tail_text,
    )

    assert tail_text in prompt  # literal text, not a summary/paraphrase


def test_continuation_prompt_instructs_continuing_not_starting_new_scene():
    profile = load_author_profile("dostoevsky")
    prompt = build_continuation_prompt(
        profile=profile, mood_input=_sample_mood_input(), chapter_tail_text="Fragment.",
    )
    assert "NOT a new, independent story" in prompt
    assert "continue" in prompt.lower()


def test_continuation_prompt_uses_two_independent_delimiters():
    profile = load_author_profile("dostoevsky")
    prompt = build_continuation_prompt(
        profile=profile, mood_input=_sample_mood_input(), chapter_tail_text="Fragment.",
    )
    chapter_tokens = set(re.findall(r"<<<CHAPTER_[0-9a-f]+>>>", prompt))
    data_tokens = set(re.findall(r"<<<DATA_[0-9a-f]+>>>", prompt))
    assert len(chapter_tokens) == 1  # open == close
    assert len(data_tokens) == 1
    assert chapter_tokens != data_tokens


def test_continuation_prompt_has_no_leftover_placeholders():
    profile = load_author_profile("dostoevsky")
    prompt = build_continuation_prompt(
        profile=profile, mood_input=_sample_mood_input(), chapter_tail_text="Fragment.",
        characters=[CharacterCard(name="Arkadij")], world_meta=WorldMeta(setting="Petersburg"),
    )
    for placeholder in (
        "{author_name}", "{story_lang}", "{style_card}", "{retrieved_chunks}", "{characters_brief}",
        "{chapter_delimiter_open}", "{chapter_delimiter_close}", "{chapter_tail_text}",
        "{safety_rules}", "{data_delimiter_open}", "{data_delimiter_close}",
        "{mood_input_json}", "{target_words}",
    ):
        assert placeholder not in prompt
