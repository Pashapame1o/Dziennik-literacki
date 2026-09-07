from diary.core.safety.helplines import load_helplines


def test_pl_helplines_load_with_expected_numbers():
    helplines = load_helplines("pl")
    assert helplines.locale == "pl"
    phones = [n.phone for n in helplines.numbers]
    assert "116 123" in phones
    assert "800 70 2222" in phones
    assert "112" in phones


def test_unknown_locale_falls_back_to_pl():
    helplines = load_helplines("xx-not-a-real-locale")
    assert helplines.locale == "pl"
