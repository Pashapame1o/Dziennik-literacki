from diary.core.story.chapters import build_chapter_tail, summarize_chapter


def test_build_chapter_tail_joins_entries_in_order():
    assert build_chapter_tail(["Pierwsza część.", "Druga część."]) == "Pierwsza część.\n\nDruga część."


def test_build_chapter_tail_skips_empty_entries():
    assert build_chapter_tail(["Coś.", "", None]) == "Coś."


def test_build_chapter_tail_returns_full_text_when_under_limit():
    text = "Krótki fragment."
    assert build_chapter_tail([text], max_chars=6000) == text


def test_build_chapter_tail_truncates_long_text_to_the_tail():
    long_text = "Zdanie numer X. " * 1000  # far over any reasonable max_chars
    tail = build_chapter_tail([long_text], max_chars=200)
    assert len(tail) <= 200
    assert tail in long_text  # it's a real suffix of the original, not mangled
    assert long_text.endswith(tail.rstrip()) or long_text.rstrip().endswith(tail.rstrip())


def test_build_chapter_tail_prefers_a_paragraph_boundary_when_truncating():
    part_a = "A" * 50
    part_b = "B" * 50
    text = part_a + "\n\n" + part_b
    tail = build_chapter_tail([text], max_chars=80)
    assert not tail.startswith("A")  # cut lands inside part_a; should skip to the paragraph break
    assert tail.startswith("B") or "BBBB" in tail


def test_summarize_chapter_joins_non_empty_summaries():
    assert summarize_chapter(["Arkadij poznaje Ludmiłę.", "", "  ", "Dowiaduje się o długu."]) == (
        "Arkadij poznaje Ludmiłę. Dowiaduje się o długu."
    )


def test_summarize_chapter_empty_list_gives_empty_string():
    assert summarize_chapter([]) == ""
