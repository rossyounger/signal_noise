"""Utilities for slicing long-form text into manageable chunks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class TextChunk:
    """Represents a candidate chunk of text with offsets."""

    index: int
    start_offset: int
    end_offset: int
    text: str


def normalize_whitespace(text: str) -> str:
    """Collapse trailing whitespace to keep offsets stable."""

    return text.replace("\r\n", "\n")


def split_into_chunks(
    text: str,
    *,
    max_chars: int = 1200,
    min_chars: int = 400,
    overlap_chars: int = 150,
) -> List[TextChunk]:
    """Chunk text by heuristics while preserving character offsets."""

    if not text:
        return []

    normalized = normalize_whitespace(text)
    length = len(normalized)
    cursor = 0
    chunks: list[TextChunk] = []
    index = 0

    while cursor < length:
        window_end = min(cursor + max_chars, length)
        window_text = normalized[cursor:window_end]

        cutoff = _find_breakpoint(window_text, min_chars)
        end_offset = cursor + cutoff if cutoff else window_end

        snippet = normalized[cursor:end_offset].strip()
        if not snippet:
            cursor = end_offset if end_offset > cursor else window_end
            continue

        chunk = TextChunk(
            index=index,
            start_offset=cursor,
            end_offset=end_offset,
            text=snippet,
        )
        chunks.append(chunk)
        index += 1

        if end_offset >= length:
            break

        next_cursor = max(end_offset - overlap_chars, 0)
        if next_cursor <= cursor:
            next_cursor = end_offset
        cursor = next_cursor

    return chunks


def _find_breakpoint(window_text: str, min_chars: int) -> int:
    """Find best breakpoint within the window respecting ``min_chars``."""

    length = len(window_text)
    if length <= min_chars:
        return length

    paragraph_break = window_text.rfind("\n\n", min_chars)
    if paragraph_break != -1 and paragraph_break >= min_chars:
        return paragraph_break + 2

    for sep in [". ", "! ", "? ", "\n"]:
        sentence_break = window_text.rfind(sep, min_chars)
        if sentence_break != -1 and sentence_break + len(sep) >= min_chars:
            return sentence_break + len(sep)

    return length


def iter_chunk_texts(chunks: Iterable[TextChunk]) -> Iterable[str]:
    """Expose only the string contents of chunks."""

    for chunk in chunks:
        yield chunk.text
