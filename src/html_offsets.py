from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from html import unescape
import logging

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class MappedSpan:
    html_start: int
    html_end: int
    text_start: int
    text_end: int
    candidates: list[dict[str, int]] | None = None


def _render_with_offsets(html: str) -> tuple[str, list[int]]:
    """
    Render the HTML to visible text while tracking where each character
    originated in the raw HTML string.
    """

    text_chars: list[str] = []
    html_index_for_char: list[int] = []

    length = len(html)
    i = 0
    while i < length:
        char = html[i]

        if char == "<":
            close = html.find(">", i)
            if close == -1:
                break
            tag = html[i + 1 : close].strip().lower()
            if tag.startswith("br") or tag in {"p", "/p", "div", "/div"}:
                text_chars.append("\n")
                html_index_for_char.append(close + 1)
            i = close + 1
            continue

        if char == "&":
            semi = html.find(";", i)
            if semi != -1:
                entity = html[i : semi + 1]
                decoded = unescape(entity)
                if decoded:
                    for ch in decoded:
                        text_chars.append(ch)
                        html_index_for_char.append(i)
                i = semi + 1
                continue

        text_chars.append(char)
        html_index_for_char.append(i)
        i += 1

    return "".join(text_chars), html_index_for_char


def map_text_offsets_to_html_range(
    html: str,
    text_start: int,
    text_end: int,
) -> tuple[int, int]:
    """
    Translate plain-text offsets into the corresponding HTML slice.

    Retool gives us character offsets based on the rendered text from a rich text
    control. Those indices ignore markup characters and treat HTML entities as
    their decoded character. This helper walks the HTML string and tracks the
    rendered text length so we can recover the start/end indices inside the raw
    HTML string.
    """
    if text_start < 0 or text_end < text_start:
        raise ValueError("Invalid text offset range")

    length = len(html)
    text_pos = 0
    start_html: int | None = None
    end_html: int | None = None
    i = 0

    while i < length:
        char = html[i]
        if char == "<":
            close = html.find(">", i)
            if close == -1:
                raise ValueError("Malformed HTML: unmatched '<'")
            i = close + 1
            continue

        if char == "&":
            semi = html.find(";", i)
            if semi != -1:
                entity = html[i : semi + 1]
                decoded = unescape(entity)
                decoded_len = len(decoded)
                if decoded_len == 0:
                    decoded_len = 1
                if start_html is None and text_pos <= text_start < text_pos + decoded_len:
                    start_html = i
                text_pos += decoded_len
                i = semi + 1
                if text_pos >= text_end and end_html is None:
                    end_html = i
                    break
                continue

        if start_html is None and text_pos == text_start:
            start_html = i

        text_pos += 1
        i += 1

        if text_pos >= text_end and end_html is None:
            end_html = i
            break

    total_text_length = text_pos

    if text_end > total_text_length:
        text_end = total_text_length

    if start_html is None:
        if text_start == total_text_length:
            start_html = length
        else:
            raise ValueError("Unable to locate HTML start for text offset")

    if end_html is None:
        end_html = length

    return start_html, end_html


def find_html_fragment(
    document_html: str,
    selection_text: str,
    selection_html: str | None,
    text_start: int | None,
    text_end: int | None,
) -> MappedSpan | None:
    if not document_html:
        return None

    plain_text, html_positions = _render_with_offsets(document_html)
    if not plain_text:
        return None

    selection_raw = selection_text or ""
    if not selection_raw.strip():
        return None

    def _html_range_for_text(text_idx: int, length: int) -> tuple[int, int]:
        if not html_positions:
            return (text_idx, text_idx + length)
        start_idx = max(0, min(text_idx, len(html_positions) - 1))
        end_idx = min(text_idx + length, len(html_positions))
        if end_idx <= start_idx:
            end_idx = start_idx + 1
        html_start = html_positions[start_idx]
        html_end = html_positions[end_idx - 1] + 1
        return html_start, html_end

    def _text_range_for_html(html_start: int, html_end: int) -> tuple[int, int]:
        if not html_positions:
            return (html_start, html_end)
        start_idx = bisect_left(html_positions, html_start)
        end_idx = bisect_right(html_positions, max(html_start, html_end - 1))
        end_idx = min(end_idx, len(html_positions))
        return (start_idx, end_idx)

    candidates: list[MappedSpan] = []

    total_chars = len(plain_text)
    requested_length = (
        max(0, (text_end or 0) - (text_start or 0)) if text_end is not None and text_start is not None else 0
    )

    if selection_html:
        snippet_raw = selection_html.strip()
        if snippet_raw:
            pos = document_html.find(snippet_raw)
            while pos != -1:
                html_start = pos
                html_end = pos + len(snippet_raw)
                text_start_idx, text_end_idx = _text_range_for_html(html_start, html_end)
                text_start_idx = min(text_start_idx, total_chars)
                text_end_idx = min(text_end_idx, total_chars)
                candidates.append(
                    MappedSpan(
                        html_start=html_start,
                        html_end=html_end,
                        text_start=text_start_idx,
                        text_end=text_end_idx,
                    )
                )
                pos = document_html.find(snippet_raw, pos + 1)

            stripped_html = BeautifulSoup(snippet_raw, "html.parser").decode()
            if stripped_html and stripped_html != snippet_raw:
                pos = document_html.find(stripped_html)
                while pos != -1:
                    html_start = pos
                    html_end = pos + len(stripped_html)
                    text_start_idx, text_end_idx = _text_range_for_html(html_start, html_end)
                    candidates.append(
                        MappedSpan(
                            html_start=html_start,
                            html_end=html_end,
                            text_start=text_start_idx,
                            text_end=text_end_idx,
                        )
                    )
                    pos = document_html.find(stripped_html, pos + 1)

    # Primary exact match on raw selection text
    idx = plain_text.find(selection_raw)
    while idx != -1:
        html_start, html_end = _html_range_for_text(idx, len(selection_raw))
        candidates.append(
            MappedSpan(
                html_start=html_start,
                html_end=html_end,
                text_start=idx,
                text_end=idx + len(selection_raw),
            )
        )
        idx = plain_text.find(selection_raw, idx + 1)

    # Match on HTML-rendered text if provided (after stripping wrappers)
    if selection_html:
        cleaned_html_text = BeautifulSoup(selection_html, "html.parser").get_text()
        if cleaned_html_text and cleaned_html_text != selection_raw:
            idx = plain_text.find(cleaned_html_text)
            while idx != -1:
                html_start, html_end = _html_range_for_text(idx, len(cleaned_html_text))
                candidates.append(
                    MappedSpan(
                        html_start=html_start,
                        html_end=html_end,
                        text_start=idx,
                        text_end=idx + len(cleaned_html_text),
                    )
                )
                idx = plain_text.find(cleaned_html_text, idx + 1)

    # Trimmed fallback to handle leading/trailing whitespace differences
    trimmed = selection_raw.strip()
    if not candidates and trimmed and trimmed != selection_raw:
        idx = plain_text.find(trimmed)
        while idx != -1:
            html_start, html_end = _html_range_for_text(idx, len(trimmed))
            candidates.append(
                MappedSpan(
                    html_start=html_start,
                    html_end=html_end,
                    text_start=idx,
                    text_end=idx + len(trimmed),
                )
            )
            idx = plain_text.find(trimmed, idx + 1)

    if not candidates:
        return None

    target_text = max(0, min(text_start or 0, total_chars))
    requested_length = 0
    if text_end is not None and text_start is not None:
        requested_length = max(0, text_end - text_start)

    target_html = html_positions[target_text] if html_positions and target_text < len(html_positions) else 0

    def _score(span: MappedSpan) -> tuple[float, float, float]:
        text_distance = abs(span.text_start - target_text)
        html_distance = abs(span.html_start - target_html)
        candidate_length = span.text_end - span.text_start
        if candidate_length == 0:
            candidate_length = 1
        target_length = requested_length or candidate_length
        if requested_length == 0:
            length_ratio = 0.0
        else:
            length_ratio = abs(candidate_length - target_length) / max(target_length, 1)
        return (text_distance, html_distance, length_ratio)

    chosen = min(candidates, key=_score)

    debug_payload = [
        {
            "html_start": span.html_start,
            "html_end": span.html_end,
            "text_start": span.text_start,
            "text_end": span.text_end,
        }
        for span in candidates
    ]
    chosen.candidates = debug_payload

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "html_offsets.find_html_fragment candidates=%s chosen=%s target_text=%s target_html=%s",
            debug_payload,
            {
                "html_start": chosen.html_start,
                "html_end": chosen.html_end,
                "text_start": chosen.text_start,
                "text_end": chosen.text_end,
            },
            target_text,
            target_html,
        )

    def _refine_span(span: MappedSpan) -> dict[str, int] | None:
        if not span.candidates:
            return None

        extract = document_html[
            max(span.html_start - 500, 0) : min(span.html_end + 500, len(document_html))
        ]
        neighborhood_plain, neighborhood_positions = _render_with_offsets(extract)

        def _search_variant(label: str, variant: str) -> tuple[int, int, int, int] | None:
            if not variant:
                return None
            idx = neighborhood_plain.find(variant)
            best_local: tuple[int, int, int, int] | None = None
            while idx != -1:
                local_start = idx
                local_end = idx + len(variant)
                if local_end > len(neighborhood_positions):
                    break
                html_start_candidate = neighborhood_positions[local_start] + max(span.html_start - 500, 0)
                html_end_candidate = (
                    neighborhood_positions[local_end - 1] + max(span.html_start - 500, 0) + 1
                )
                text_start_candidate = span.text_start + (local_start - (span.text_start - target_text))
                score = abs((span.text_start + local_start) - target_text)
                if best_local is None or score < best_local[0]:
                    best_local = (
                        score,
                        html_start_candidate,
                        html_end_candidate,
                        span.text_start + local_start,
                    )
                idx = neighborhood_plain.find(variant, idx + 1)
            if best_local is None:
                return None
            _, html_start_cand, html_end_cand, text_start_cand = best_local
            text_end_cand = text_start_cand + len(variant)
            return html_start_cand, html_end_cand, text_start_cand, text_end_cand

        variants: list[tuple[str, str]] = []
        if selection_text:
            variants.append(("selection_text", selection_text))
        if selection_html:
            html_text = BeautifulSoup(selection_html, "html.parser").get_text()
            if html_text and html_text != selection_text:
                variants.append(("selection_html_text", html_text))

        refined_result: tuple[str, int, int, int, int] | None = None
        for label, variant in variants:
            result = _search_variant(label, variant)
            if result:
                html_start_cand, html_end_cand, text_start_cand, text_end_cand = result
                refined_result = (label, html_start_cand, html_end_cand, text_start_cand, text_end_cand)
                break

        if refined_result is None:
            return None

        label, html_start_cand, html_end_cand, text_start_cand, text_end_cand = refined_result
        span.html_start = html_start_cand
        span.html_end = html_end_cand
        span.text_start = text_start_cand
        span.text_end = text_end_cand
        return {
            "source": f"refined:{label}",
            "html_start": html_start_cand,
            "html_end": html_end_cand,
            "text_start": text_start_cand,
            "text_end": text_end_cand,
        }

    refinement = _refine_span(chosen)
    if refinement:
        chosen.candidates.append(refinement)

    return chosen

