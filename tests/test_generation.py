import pytest

from diary.core.llm.mock import MockAdapter
from diary.core.safety.output_filter import OutputFilterVerdict
from diary.core.story.characters import CharacterCard, WorldMeta
from diary.core.story.generation import (
    ContinuationContext,
    DoneEvent,
    ErrorEvent,
    FilterRejectedEvent,
    ResultEvent,
    StageEvent,
    TokenEvent,
    generate_story,
)
from diary.core.story.metadata import StoryMetadata
from diary.core.story.mood_input import MoodInput
from diary.core.style.chunking import Chunk
from diary.core.style.profile import load_author_profile

PASSING_METADATA = StoryMetadata(
    title="Deszcz",
    mood_tag="melancholia",
    characters_used=["Arkadij"],
    character_delta={},
    summary="Krótkie streszczenie.",
    tone_flags=["none"],
)
PASS_VERDICT = OutputFilterVerdict(verdict="pass")
REGENERATE_VERDICT = OutputFilterVerdict(verdict="regenerate", reasons=["opisuje metodę krzywdy"])


def _sample_mood_input(**overrides) -> MoodInput:
    kwargs = dict(
        valence=1,
        energy=6,
        chips=["radość"],
        answers={"unusual_event": True, "people_or_solitude": True, "something_closed": False},
        keywords=["ogród"],
        length="medium",
    )
    kwargs.update(overrides)
    return MoodInput(**kwargs)


def _adapter_that_passes(chunks=None, **structured_overrides):
    structured = {StoryMetadata: PASSING_METADATA, OutputFilterVerdict: PASS_VERDICT}
    structured.update(structured_overrides)
    return MockAdapter(chunks=chunks, structured_responses=structured)


async def _collect(
    profile, adapter, mood_input=None, characters=None, world_meta=None,
    retrieved_chunks=None, continuation=None, input_detected=False,
):
    events = []
    async for event in generate_story(
        adapter=adapter,
        profile=profile,
        mood_input=mood_input or _sample_mood_input(),
        model="gpt-4o-mini",
        model_helper="gpt-4o-mini",
        temperature=0.9,
        story_language="auto",
        characters=characters or [],
        world_meta=world_meta or WorldMeta(),
        retrieved_chunks=retrieved_chunks or [],
        continuation=continuation,
        input_detected=input_detected,
    ):
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_output_is_prose_only_no_title_or_headers():
    profile = load_author_profile("dostoevsky")
    adapter = _adapter_that_passes(chunks=["Rano ", "padał ", "deszcz, ", "a on milczał."])

    events = await _collect(profile, adapter)

    story_text = "".join(e.text for e in events if isinstance(e, TokenEvent))
    assert story_text == "Rano padał deszcz, a on milczał."
    assert not story_text.lstrip().startswith("#")
    assert "\n#" not in story_text
    assert "Tytuł" not in story_text
    assert isinstance(events[-1], DoneEvent)


@pytest.mark.asyncio
async def test_all_five_stages_emitted_in_order_on_a_passing_attempt():
    profile = load_author_profile("dostoevsky")
    adapter = _adapter_that_passes(chunks=["Coś."])

    events = await _collect(profile, adapter)
    stages = [e.stage for e in events if isinstance(e, StageEvent)]
    assert stages == [
        "dobieram fragmenty stylu",
        "przypominam bohaterów",
        "piszę",
        "sprawdzam",
        "zapisuję",
    ]


@pytest.mark.asyncio
async def test_result_event_carries_metadata_and_pass_result():
    profile = load_author_profile("dostoevsky")
    adapter = _adapter_that_passes(chunks=["Coś."])

    events = await _collect(profile, adapter)
    result = next(e for e in events if isinstance(e, ResultEvent))
    assert result.story_text == "Coś."
    assert result.metadata.title == "Deszcz"
    assert result.safety_output_result == "pass"
    assert result.input_detected is False


@pytest.mark.asyncio
async def test_messages_include_a_non_system_turn():
    """Regresja: same-system messages (bez tury user/assistant) łamią dostawców,
    których warstwa OpenAI-compatible pod spodem mapuje system -> systemInstruction
    i wymaga niepustego 'contents' (np. Gemini zwraca wtedy 400 'contents is not
    specified'). Prawdziwy OpenAI to toleruje, więc lukę widać dopiero na innym
    dostawcy — ten test pilnuje kształtu payloadu niezależnie od providera."""
    profile = load_author_profile("dostoevsky")
    adapter = _adapter_that_passes(chunks=["Coś."])

    await _collect(profile, adapter)

    assert adapter.received_messages is not None
    roles = [m["role"] for m in adapter.received_messages]
    assert roles[0] == "system"
    assert any(role != "system" for role in roles), (
        "messages zawiera wyłącznie rolę system — Gemini i podobne bramki odrzucą to jako 400"
    )


@pytest.mark.asyncio
async def test_bad_api_key_yields_readable_error_event_not_an_exception():
    profile = load_author_profile("dostoevsky")
    adapter = MockAdapter(raise_auth_error=True)

    events = await _collect(profile, adapter)

    error_events = [e for e in events if isinstance(e, ErrorEvent)]
    assert len(error_events) == 1
    assert "klucz" in error_events[0].message.lower()
    assert not any(isinstance(e, DoneEvent) for e in events)


@pytest.mark.asyncio
async def test_input_detected_uses_reinforced_safety_rules_from_the_first_attempt():
    profile = load_author_profile("dostoevsky")
    adapter = _adapter_that_passes(chunks=["Coś."])

    await _collect(profile, adapter, input_detected=True)

    system_prompt = adapter.received_messages[0]["content"]
    assert "nie zostawia bohatera samego" in system_prompt  # reinforced-only text


@pytest.mark.asyncio
async def test_existing_characters_appear_in_a_new_chapter_prompt():
    """DoD M2 #2, now via character cards instead of a world-state blob: a
    second entry with the same author uses characters from the first —
    simulated here by passing pre-built cards directly, since generate_story
    doesn't read/write storage itself."""
    profile = load_author_profile("dostoevsky")
    adapter = _adapter_that_passes(chunks=["Coś."])
    characters = [
        CharacterCard(name="Arkadij Władymirowicz", is_alter_ego=True),
        CharacterCard(name="Ludmiła Iwanowna", role="gospodyni"),
    ]

    await _collect(profile, adapter, characters=characters)

    system_prompt = adapter.received_messages[0]["content"]
    assert "Arkadij Władymirowicz" in system_prompt
    assert "Ludmiła Iwanowna" in system_prompt


@pytest.mark.asyncio
async def test_retrieved_chunks_appear_in_the_prompt():
    profile = load_author_profile("dostoevsky")
    adapter = _adapter_that_passes(chunks=["Coś."])
    chunks = [Chunk(text="Fragment prawdziwego tekstu.", source_file="ksiazka.txt", index=0)]

    await _collect(profile, adapter, retrieved_chunks=chunks)

    system_prompt = adapter.received_messages[0]["content"]
    assert "Fragment prawdziwego tekstu." in system_prompt


@pytest.mark.asyncio
async def test_output_filter_regenerate_then_pass():
    """DoD M2 #5, happy path: rejected once, passes on retry."""
    profile = load_author_profile("dostoevsky")
    adapter = MockAdapter(
        stream_chunks_by_call=[["Zła wersja."], ["Dobra wersja."]],
        structured_responses={
            StoryMetadata: PASSING_METADATA,
            OutputFilterVerdict: [REGENERATE_VERDICT, PASS_VERDICT],
        },
    )

    events = await _collect(profile, adapter)

    rejected = [e for e in events if isinstance(e, FilterRejectedEvent)]
    assert len(rejected) == 1
    result = next(e for e in events if isinstance(e, ResultEvent))
    assert result.story_text == "Dobra wersja."
    assert result.safety_output_result == "regenerated"
    assert isinstance(events[-1], DoneEvent)


@pytest.mark.asyncio
async def test_output_filter_rejects_twice_then_falls_back():
    """DoD M2 #5: after MAX_REGENERATION_ATTEMPTS (2) rejections, fallback text is used."""
    profile = load_author_profile("dostoevsky")
    adapter = MockAdapter(
        chunks=["Zawsze zła wersja."],
        structured_responses={
            StoryMetadata: PASSING_METADATA,
            OutputFilterVerdict: REGENERATE_VERDICT,  # every attempt gets rejected
        },
    )

    events = await _collect(profile, adapter)

    # "maks. 2 próby" (SPEC 6.3) = 2 regenerations beyond the original attempt:
    # original (rejected) -> retry 1 (rejected) -> retry 2 (rejected) -> fallback.
    # That's 3 generations total and 3 FilterRejectedEvents, not 2.
    rejected = [e for e in events if isinstance(e, FilterRejectedEvent)]
    assert len(rejected) == 3
    result = next(e for e in events if isinstance(e, ResultEvent))
    assert result.safety_output_result == "fallback"
    assert "Zawsze zła wersja." not in result.story_text
    assert profile.name in result.story_text
    assert isinstance(events[-1], DoneEvent)


@pytest.mark.asyncio
async def test_regeneration_escalates_to_reinforced_safety_rules():
    profile = load_author_profile("dostoevsky")
    adapter = MockAdapter(
        stream_chunks_by_call=[["Zła."], ["Dobra."]],
        structured_responses={
            StoryMetadata: PASSING_METADATA,
            OutputFilterVerdict: [REGENERATE_VERDICT, PASS_VERDICT],
        },
    )

    await _collect(profile, adapter, input_detected=False)

    first_attempt_prompt = adapter.received_messages_history[0][0]["content"]
    second_attempt_prompt = adapter.received_messages_history[1][0]["content"]
    assert "nie zostawia bohatera samego" not in first_attempt_prompt
    assert "nie zostawia bohatera samego" in second_attempt_prompt


# --- Continuation ("Kontynuuj") ---


@pytest.mark.asyncio
async def test_continuation_prompt_contains_literal_prior_text_verbatim():
    """This is the core capability the old world-state blob could never
    provide (see ASSUMPTIONS.md "M2.5"): the model must see the *exact*
    text it's continuing, not a recap."""
    profile = load_author_profile("dostoevsky")
    adapter = _adapter_that_passes(chunks=["Dalszy ciąg."])
    tail_text = "...i wtedy Arkadij zamilkł, patrząc na deszcz za oknem."

    await _collect(profile, adapter, continuation=ContinuationContext(chapter_tail_text=tail_text))

    system_prompt = adapter.received_messages[0]["content"]
    assert tail_text in system_prompt


@pytest.mark.asyncio
async def test_continuation_uses_a_distinct_user_turn_trigger():
    profile = load_author_profile("dostoevsky")
    adapter = _adapter_that_passes(chunks=["Dalszy ciąg."])

    await _collect(profile, adapter, continuation=ContinuationContext(chapter_tail_text="Fragment."))

    user_message = adapter.received_messages[1]["content"]
    assert "kontynuuj" in user_message.lower()


@pytest.mark.asyncio
async def test_new_chapter_uses_narrator_prompt_not_continuation_prompt():
    profile = load_author_profile("dostoevsky")
    adapter = _adapter_that_passes(chunks=["Nowy wpis."])

    await _collect(profile, adapter, continuation=None)

    system_prompt = adapter.received_messages[0]["content"]
    assert "Sam wymyślasz punkt wyjścia" in system_prompt  # narrator.md-only instruction
    assert "KONIEC TEGO ROZDZIAŁU DOTĄD" not in system_prompt  # continue.md-only section


@pytest.mark.asyncio
async def test_continuation_result_is_appended_not_replaced_conceptually():
    """generate_story doesn't know about display concatenation (that's the
    caller's job) — but it MUST still run metadata/filter/result exactly
    like a new chapter, just against continuation text."""
    profile = load_author_profile("dostoevsky")
    adapter = _adapter_that_passes(chunks=["Dalszy ciąg sceny."])

    events = await _collect(profile, adapter, continuation=ContinuationContext(chapter_tail_text="Poprzedni fragment."))

    result = next(e for e in events if isinstance(e, ResultEvent))
    assert result.story_text == "Dalszy ciąg sceny."
    assert isinstance(events[-1], DoneEvent)
