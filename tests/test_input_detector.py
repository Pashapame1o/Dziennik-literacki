"""Input safety detector (SPEC 6.2). DoD M2 #4: both directions covered —
metaphors must not trigger, real signals must."""

from __future__ import annotations

import pytest

from diary.core.safety.input_detector import KNOWN_SAFE_METAPHORS, detect
from diary.core.story.mood_input import MoodInput


def _mood(**overrides) -> MoodInput:
    kwargs = dict(
        valence=0,
        energy=5,
        chips=["spokój"],
        answers={"unusual_event": True, "people_or_solitude": False, "afraid_tomorrow": False},
        keywords=["cisza"],
        sentence=None,
        length="medium",
    )
    kwargs.update(overrides)
    return MoodInput(**kwargs)


@pytest.mark.parametrize("metaphor", KNOWN_SAFE_METAPHORS)
def test_known_safe_metaphors_do_not_trigger(metaphor):
    result = detect(_mood(sentence=metaphor))
    assert result.triggered is False


@pytest.mark.parametrize(
    "phrase",
    [
        "Chcę się zabić.",
        "Chcę odebrać sobie życie.",
        "Nie chcę już żyć.",
        "Nie ma sensu dalej żyć.",
        "Chcę zniknąć na zawsze.",
        "To już koniec ze mną.",
        "Myślę o samobójstwie.",
        "Mam plan, żeby się zabić jutro.",
        "I want to die.",
        "I want to kill myself.",
    ],
)
def test_real_crisis_phrases_in_sentence_trigger(phrase):
    result = detect(_mood(sentence=phrase))
    assert result.triggered is True
    assert result.reasons


def test_crisis_phrase_in_keywords_triggers():
    result = detect(_mood(keywords=["samobójstwo"]))
    assert result.triggered is True


def test_ordinary_sad_sentence_does_not_trigger():
    result = detect(_mood(sentence="Był ciężki dzień, czuję smutek i zmęczenie."))
    assert result.triggered is False


def test_extreme_low_valence_alone_does_not_trigger():
    result = detect(_mood(valence=-5, answers={"unusual_event": False, "people_or_solitude": False, "afraid_tomorrow": False}))
    assert result.triggered is False


def test_extreme_low_valence_with_afraid_tomorrow_triggers_combination():
    result = detect(
        _mood(
            valence=-4,
            answers={"unusual_event": False, "people_or_solitude": False, "afraid_tomorrow": True},
        )
    )
    assert result.triggered is True
    assert any("low_valence_combination" in r for r in result.reasons)


def test_moderate_low_valence_with_afraid_tomorrow_does_not_trigger():
    result = detect(
        _mood(
            valence=-3,
            answers={"unusual_event": False, "people_or_solitude": False, "afraid_tomorrow": True},
        )
    )
    assert result.triggered is False


def test_no_sentence_no_crisis_keywords_does_not_trigger():
    result = detect(_mood(sentence=None, keywords=["deszcz", "cisza"]))
    assert result.triggered is False
