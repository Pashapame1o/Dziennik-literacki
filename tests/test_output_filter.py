import pytest

from diary.core.llm.mock import MockAdapter
from diary.core.safety.output_filter import (
    MAX_REGENERATION_ATTEMPTS,
    OutputFilterVerdict,
    build_output_filter_messages,
    fallback_story_text,
    run_output_filter,
)


def test_build_output_filter_messages_wraps_story_in_delimiter():
    messages = build_output_filter_messages(story_text="Rano padał deszcz.", tone_flags=["none"])
    content = messages[0]["content"]
    assert "Rano padał deszcz." in content
    assert content.count("<<<DATA_") == 2


def test_build_output_filter_messages_includes_tone_flags_hint():
    messages = build_output_filter_messages(story_text="x", tone_flags=["harm_method"])
    assert "harm_method" in messages[0]["content"]


def test_verdict_passed_property():
    assert OutputFilterVerdict(verdict="pass").passed is True
    assert OutputFilterVerdict(verdict="regenerate", reasons=["x"]).passed is False


@pytest.mark.asyncio
async def test_run_output_filter_returns_pass_verdict():
    adapter = MockAdapter(structured_response=OutputFilterVerdict(verdict="pass"))
    verdict = await run_output_filter(adapter=adapter, model="m", story_text="x", tone_flags=[])
    assert verdict.passed


@pytest.mark.asyncio
async def test_run_output_filter_returns_regenerate_verdict_with_reasons():
    adapter = MockAdapter(
        structured_response=OutputFilterVerdict(verdict="regenerate", reasons=["opisuje metodę krzywdy"])
    )
    verdict = await run_output_filter(adapter=adapter, model="m", story_text="x", tone_flags=[])
    assert not verdict.passed
    assert verdict.reasons == ["opisuje metodę krzywdy"]


def test_fallback_story_text_mentions_author_and_has_no_risk_words():
    text = fallback_story_text("Fiodor Dostojewski")
    assert "Fiodor Dostojewski" in text
    for risky in ("samobój", "zabić", "krzywd"):
        assert risky not in text.lower()


def test_max_regeneration_attempts_is_two():
    assert MAX_REGENERATION_ATTEMPTS == 2
