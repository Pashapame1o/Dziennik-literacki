from diary.core.style.chunking import chunk_text


def _paragraphs(n: int, words_per_paragraph: int = 50) -> str:
    return "\n\n".join(" ".join(f"słowo{p}_{w}" for w in range(words_per_paragraph)) for p in range(n))


def test_short_text_becomes_a_single_chunk():
    text = "Jeden krótki akapit."
    chunks = chunk_text(text, source_file="test.txt", chunk_size_words=450, overlap_words=60)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].source_file == "test.txt"
    assert chunks[0].index == 0


def test_long_text_is_split_into_multiple_chunks():
    text = _paragraphs(20, words_per_paragraph=50)  # ~1000 words total
    chunks = chunk_text(text, source_file="test.txt", chunk_size_words=450, overlap_words=60)
    assert len(chunks) >= 2
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_chunks_carry_some_overlap_from_the_previous_chunk():
    text = _paragraphs(20, words_per_paragraph=50)
    chunks = chunk_text(text, source_file="test.txt", chunk_size_words=450, overlap_words=60)
    # last paragraph(s) of chunk N should reappear at the start of chunk N+1
    first_paragraph_of_second_chunk = chunks[1].text.split("\n\n")[0]
    assert first_paragraph_of_second_chunk in chunks[0].text


def test_no_overlap_when_overlap_words_is_zero():
    text = _paragraphs(20, words_per_paragraph=50)
    chunks = chunk_text(text, source_file="test.txt", chunk_size_words=450, overlap_words=0)
    first_paragraph_of_second_chunk = chunks[1].text.split("\n\n")[0]
    assert first_paragraph_of_second_chunk not in chunks[0].text


def test_blank_paragraphs_are_ignored():
    text = "Akapit jeden.\n\n\n\nAkapit dwa."
    chunks = chunk_text(text, source_file="test.txt")
    assert len(chunks) == 1
    assert "Akapit jeden." in chunks[0].text
    assert "Akapit dwa." in chunks[0].text
