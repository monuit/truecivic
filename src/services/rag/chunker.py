"""Utilities for hierarchical text chunking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class Chunk:
    """A structured chunk with metadata."""

    title: str
    text: str


def chunk_text(title: str, text: str, max_length: int = 800) -> Iterable[Chunk]:
    """Yield paragraph-based chunks up to max_length characters."""
    paragraphs: List[str] = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        yield Chunk(title=title, text=text.strip())
        return

    buffer: List[str] = []
    current_length = 0
    for paragraph in paragraphs:
        segments = _split_paragraph(paragraph, max_length)
        for segment in segments:
            seg_len = len(segment)
            if current_length + seg_len > max_length and buffer:
                yield Chunk(title=title, text="\n\n".join(buffer))
                buffer = [segment]
                current_length = seg_len
            else:
                buffer.append(segment)
                current_length += seg_len
    if buffer:
        yield Chunk(title=title, text="\n\n".join(buffer))


def _split_paragraph(paragraph: str, max_length: int) -> List[str]:
    """Break long paragraphs into max_length segments."""
    if len(paragraph) <= max_length:
        return [paragraph]
    return [
        paragraph[idx: idx + max_length]
        for idx in range(0, len(paragraph), max_length)
    ]
