import pytest
from pydantic import ValidationError

from diary.core.story.mood_input import MoodInput


def _valid_kwargs(**overrides):
    kwargs = dict(
        valence=0,
        energy=5,
        chips=["spokój"],
        answers={"unusual_event": True, "people_or_solitude": False, "afraid_tomorrow": True},
        keywords=["cisza"],
        length="medium",
    )
    kwargs.update(overrides)
    return kwargs


def test_valid_input_accepted():
    MoodInput(**_valid_kwargs())


@pytest.mark.parametrize("valence", [-6, 6])
def test_valence_out_of_range_rejected(valence):
    with pytest.raises(ValidationError):
        MoodInput(**_valid_kwargs(valence=valence))


@pytest.mark.parametrize("energy", [-1, 11])
def test_energy_out_of_range_rejected(energy):
    with pytest.raises(ValidationError):
        MoodInput(**_valid_kwargs(energy=energy))


def test_more_than_three_chips_rejected():
    with pytest.raises(ValidationError):
        MoodInput(**_valid_kwargs(chips=["smutek", "lęk", "złość", "spokój"]))


def test_unknown_chip_rejected():
    with pytest.raises(ValidationError):
        MoodInput(**_valid_kwargs(chips=["euforia"]))


def test_unknown_question_id_rejected():
    with pytest.raises(ValidationError):
        MoodInput(**_valid_kwargs(answers={"not_a_real_question": True}))


def test_keywords_total_over_60_chars_rejected():
    with pytest.raises(ValidationError):
        MoodInput(**_valid_kwargs(keywords=["a" * 30, "b" * 31]))


def test_sentence_over_200_chars_rejected():
    with pytest.raises(ValidationError):
        MoodInput(**_valid_kwargs(sentence="x" * 201))


def test_fewer_than_three_answers_rejected():
    with pytest.raises(ValidationError):
        MoodInput(**_valid_kwargs(answers={"unusual_event": True}))
