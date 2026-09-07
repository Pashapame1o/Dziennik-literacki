import pytest

from diary.core.llm.mock import MockAdapter
from diary.core.story.generation import DoneEvent, ErrorEvent, StageEvent, TokenEvent, generate_story
from diary.core.story.mood_input import MoodInput
from diary.core.style.profile import load_author_profile


def _sample_mood_input() -> MoodInput:
    return MoodInput(
        valence=1,
        energy=6,
        chips=["radość"],
        answers={"unusual_event": True, "people_or_solitude": True, "something_closed": False},
        keywords=["ogród"],
        length="medium",
    )


async def _collect(profile, adapter):
    events = []
    async for event in generate_story(
        adapter=adapter,
        profile=profile,
        mood_input=_sample_mood_input(),
        model="gpt-4o-mini",
        temperature=0.9,
        story_language="auto",
    ):
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_output_is_prose_only_no_title_or_headers():
    profile = load_author_profile("dostoevsky")
    adapter = MockAdapter(chunks=["Rano ", "padał ", "deszcz, ", "a on milczał."])

    events = await _collect(profile, adapter)

    story_text = "".join(e.text for e in events if isinstance(e, TokenEvent))
    assert story_text == "Rano padał deszcz, a on milczał."
    assert not story_text.lstrip().startswith("#")
    assert "\n#" not in story_text
    assert "Tytuł" not in story_text
    assert isinstance(events[-1], DoneEvent)


@pytest.mark.asyncio
async def test_all_five_stages_emitted_in_order():
    profile = load_author_profile("dostoevsky")
    adapter = MockAdapter(chunks=["Coś."])

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
async def test_messages_include_a_non_system_turn():
    """Regresja: same-system messages (bez tury user/assistant) łamią dostawców,
    których warstwa OpenAI-compatible pod spodem mapuje system -> systemInstruction
    i wymaga niepustego 'contents' (np. Gemini zwraca wtedy 400 'contents is not
    specified'). Prawdziwy OpenAI to toleruje, więc lukę widać dopiero na innym
    dostawcy — ten test pilnuje kształtu payloadu niezależnie od providera."""
    profile = load_author_profile("dostoevsky")
    adapter = MockAdapter(chunks=["Coś."])

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
