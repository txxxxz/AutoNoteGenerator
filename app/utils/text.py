from __future__ import annotations

import re
from typing import Iterable, List


SENTENCE_PATTERN = re.compile(r"(?<=[。！？!?])\s+")


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> List[str]:
    return [seg.strip() for seg in SENTENCE_PATTERN.split(text) if seg.strip()]


def take_sentences(text: str, count: int) -> str:
    sentences = split_sentences(text)
    return " ".join(sentences[:count])


def bullet_join(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items if item)
