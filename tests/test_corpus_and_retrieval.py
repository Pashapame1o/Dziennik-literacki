"""Simplified RAG (SPEC 4.3/4.4, scoped down per ASSUMPTIONS.md "M2.5"):
loading real files from authors/<slug>/corpus/ and a no-embeddings
word-overlap retrieval. Uses a temporary author directory, not the real
authors/dostoevsky/ (which ships with no corpus files by design)."""

from __future__ import annotations

import pytest

from diary.core.story.mood_input import MoodInput
from diary.core.style import corpus
from diary.core.style.chunking import Chunk
from diary.core.style.profile import AuthorProfile
from diary.core.style.retrieval import select_style_chunks


@pytest.fixture
def fake_author(tmp_path, monkeypatch):
    monkeypatch.setattr(corpus, "AUTHORS_DIR", tmp_path)
    corpus._load_chunks_cached.cache_clear()
    author_dir = tmp_path / "testauthor" / "corpus"
    author_dir.mkdir(parents=True)
    return author_dir


def _mood(**overrides) -> MoodInput:
    kwargs = dict(
        valence=-2, energy=3, chips=["smutek"],
        answers={"unusual_event": False, "people_or_solitude": False, "something_closed": True},
        keywords=["deszcz"], sentence=None, length="medium",
    )
    kwargs.update(overrides)
    return MoodInput(**kwargs)


def test_has_corpus_false_when_no_files(fake_author):
    assert corpus.has_corpus("testauthor") is False


def test_has_corpus_true_with_a_txt_file(fake_author):
    (fake_author / "book1.txt").write_text("Jakiś tekst.", encoding="utf-8")
    assert corpus.has_corpus("testauthor") is True


def test_has_corpus_ignores_non_text_files(fake_author):
    (fake_author / "notes.pdf").write_bytes(b"%PDF-fake")
    assert corpus.has_corpus("testauthor") is False


def test_load_corpus_chunks_reads_txt_and_md_files(fake_author):
    (fake_author / "a.txt").write_text("Akapit jeden.\n\nAkapit dwa deszcz smutek.", encoding="utf-8")
    (fake_author / "b.md").write_text("Inny plik.", encoding="utf-8")

    profile = AuthorProfile(name="Test", slug="testauthor")
    chunks = corpus.load_corpus_chunks(profile)

    sources = {c.source_file for c in chunks}
    assert sources == {"a.txt", "b.md"}


def test_load_corpus_chunks_empty_when_no_corpus_dir(fake_author, tmp_path):
    import shutil

    shutil.rmtree(fake_author)
    profile = AuthorProfile(name="Test", slug="testauthor")
    assert corpus.load_corpus_chunks(profile) == []


def test_select_style_chunks_prefers_overlapping_keywords():
    chunks = [
        Chunk(text="Słońce świeciło jasno nad polami zboża.", source_file="a.txt", index=0),
        Chunk(text="Deszcz padał na miasto, a smutek wypełniał ulice.", source_file="a.txt", index=1),
        Chunk(text="Radość i śmiech niosły się przez wioskę.", source_file="a.txt", index=2),
    ]
    selected = select_style_chunks(chunks, _mood(chips=["smutek"], keywords=["deszcz"]), k=1)
    assert selected == [chunks[1]]


def test_select_style_chunks_falls_back_to_first_k_when_nothing_overlaps():
    chunks = [Chunk(text=f"Fragment numer {i} bez wspólnych słów.", source_file="a.txt", index=i) for i in range(5)]
    selected = select_style_chunks(chunks, _mood(chips=["radość"], keywords=["ogród"]), k=2)
    assert selected == chunks[:2]  # zero overlap everywhere -> deterministic first-k fallback


def test_select_style_chunks_returns_empty_for_no_chunks():
    assert select_style_chunks([], _mood(), k=4) == []


def test_select_style_chunks_respects_k():
    chunks = [Chunk(text="deszcz smutek " * 3, source_file="a.txt", index=i) for i in range(10)]
    selected = select_style_chunks(chunks, _mood(), k=3)
    assert len(selected) == 3
