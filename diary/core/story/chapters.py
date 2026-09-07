"""Chapter-level helpers for the "book" interface.

"Kontynuuj" needs the literal end of the chapter's text so the model
continues the same sentence/scene — a summary would lose exactly the
continuity this feature exists for. "Zakończ ten rozdział" needs the
opposite: a short recap, built for free from each entry's own `summary`
field (SPEC 5.3's metadata call already produces one per entry) rather than
a fresh LLM call at close time.
"""

from __future__ import annotations

MAX_CHAPTER_TAIL_CHARS = 6000


def build_chapter_tail(entry_texts: list[str], *, max_chars: int = MAX_CHAPTER_TAIL_CHARS) -> str:
    """Joins a chapter's entries in reading order. If the joined text is
    longer than `max_chars`, keeps only the tail — trimmed to the nearest
    paragraph or sentence boundary so it doesn't start mid-word."""
    full = "\n\n".join(text for text in entry_texts if text)
    if len(full) <= max_chars:
        return full

    tail = full[-max_chars:]
    para_break = tail.find("\n\n")
    if para_break != -1 and para_break < max_chars // 2:
        return tail[para_break + 2 :]
    sentence_break = tail.find(". ")
    if sentence_break != -1 and sentence_break < max_chars // 2:
        return tail[sentence_break + 2 :]
    return tail


def summarize_chapter(entry_summaries: list[str]) -> str:
    """A chapter's closing summary is its entries' own `summary` fields
    joined — each already exists from that entry's metadata call, so no
    extra LLM call is needed just to close a chapter."""
    return " ".join(s.strip() for s in entry_summaries if s and s.strip())
