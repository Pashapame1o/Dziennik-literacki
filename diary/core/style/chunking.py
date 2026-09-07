"""Corpus chunking (SPEC 4.3), simplified: paragraphs packed into a word-count
budget approximating "tokens" (no real tokenizer dependency). No incremental
index, no persistence — M3 replaces this with the full pipeline described in
SPEC 4.3 (see ASSUMPTIONS.md "M2.5" for the explicit scope cut).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    text: str
    source_file: str
    index: int


def chunk_text(
    text: str, *, source_file: str, chunk_size_words: int = 450, overlap_words: int = 60
) -> list[Chunk]:
    """Packs paragraphs (blank-line separated) into chunks of roughly
    `chunk_size_words` words, carrying the tail ~`overlap_words` worth of
    paragraphs into the next chunk for a little continuity across the cut."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []
    current: list[str] = []
    current_words = 0

    for paragraph in paragraphs:
        current.append(paragraph)
        current_words += len(paragraph.split())
        if current_words >= chunk_size_words:
            chunks.append(Chunk(text="\n\n".join(current), source_file=source_file, index=len(chunks)))
            current, current_words = [], 0
            if overlap_words:
                for prev_paragraph in reversed(chunks[-1].text.split("\n\n")):
                    current.insert(0, prev_paragraph)
                    current_words += len(prev_paragraph.split())
                    if current_words >= overlap_words:
                        break

    if current:
        chunks.append(Chunk(text="\n\n".join(current), source_file=source_file, index=len(chunks)))

    return chunks
