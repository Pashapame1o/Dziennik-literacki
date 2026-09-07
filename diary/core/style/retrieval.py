"""Style retrieval (SPEC 4.4), simplified: word-overlap scoring between the
mood input and corpus chunks — no embeddings, no MMR/diversification. This
is a deliberate scope cut for now (see ASSUMPTIONS.md "M2.5"); M3 replaces
it with the full embedding + MMR pipeline SPEC 4.4 describes.
"""

from __future__ import annotations

import re

from diary.core.story.mood_input import MoodInput
from diary.core.style.chunking import Chunk

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)  # letters only
_MIN_WORD_LEN = 3


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text) if len(w) >= _MIN_WORD_LEN}


def _query_terms(mood_input: MoodInput) -> set[str]:
    terms: set[str] = set()
    for chip in mood_input.chips:
        terms |= _tokenize(chip)
    for keyword in mood_input.keywords:
        terms |= _tokenize(keyword)
    if mood_input.sentence:
        terms |= _tokenize(mood_input.sentence)
    return terms


def select_style_chunks(chunks: list[Chunk], mood_input: MoodInput, *, k: int = 4) -> list[Chunk]:
    """Top-k chunks by word overlap with the mood input. No signal (empty
    query, or zero overlap everywhere) falls back to the first k chunks in
    file order — deterministic, and still "some" style material rather than
    none. Ties keep original order."""
    if not chunks:
        return []
    query = _query_terms(mood_input)
    if not query:
        return chunks[:k]

    scored = sorted(
        range(len(chunks)),
        key=lambda i: (-len(query & _tokenize(chunks[i].text)), i),
    )
    return [chunks[i] for i in scored[:k]]
