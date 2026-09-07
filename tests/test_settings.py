from diary.core.settings import get_settings, override_settings


def test_override_settings_applies_and_resets():
    base = get_settings()
    assert base.model_story != "temporary-model"

    with override_settings(model_story="temporary-model", temperature=1.5) as overridden:
        assert overridden.model_story == "temporary-model"
        assert overridden.temperature == 1.5
        assert get_settings().model_story == "temporary-model"

    assert get_settings().model_story == base.model_story
    assert get_settings().temperature == base.temperature


def test_override_settings_does_not_mutate_base_instance():
    base_before = get_settings()
    with override_settings(model_story="other-model"):
        pass
    assert get_settings() is base_before
