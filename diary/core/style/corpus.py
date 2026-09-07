"""Loads authors/<slug>/corpus/*.txt|*.md and chunks them (SPEC 4.1, 4.3).

Simplified for now: chunks are read and cached in memory per process, not
persisted to a SQLite index (no `diary index` CLI yet, no embeddings — see
ASSUMPTIONS.md "M2.5"). Adding or changing corpus files requires restarting
`diary serve` to be picked up; acceptable for a personal, single-process app
at this stage.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from diary.core.style.chunking import Chunk, chunk_text
from diary.core.style.profile import AUTHORS_DIR, AuthorProfile

CORPUS_EXTENSIONS = (".txt", ".md")


def corpus_dir(slug: str) -> Path:
    return AUTHORS_DIR / slug / "corpus"


def has_corpus(slug: str) -> bool:
    directory = corpus_dir(slug)
    if not directory.is_dir():
        return False
    return any(p.is_file() and p.suffix.lower() in CORPUS_EXTENSIONS for p in directory.iterdir())


@lru_cache(maxsize=16)
def _load_chunks_cached(slug: str, chunk_size_words: int, overlap_words: int) -> tuple[Chunk, ...]:
    directory = corpus_dir(slug)
    if not directory.is_dir():
        return ()
    chunks: list[Chunk] = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in CORPUS_EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        chunks.extend(
            chunk_text(text, source_file=path.name, chunk_size_words=chunk_size_words, overlap_words=overlap_words)
        )
    return tuple(chunks)


def load_corpus_chunks(profile: AuthorProfile) -> list[Chunk]:
    return list(
        _load_chunks_cached(
            profile.slug, profile.retrieval.chunk_size_tokens, profile.retrieval.chunk_overlap_tokens
        )
    )
