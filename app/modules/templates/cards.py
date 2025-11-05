from __future__ import annotations

import re
from typing import List

from app.schemas.common import CardsPayload, KnowledgeCards, NoteDoc
from app.utils.text import split_sentences


class KnowledgeCardGenerator:
    def generate(self, note_doc: NoteDoc) -> KnowledgeCards:
        cards = []
        for section in note_doc.sections:
            definition = self._extract_definition(section.body_md)
            exam_points = self._extract_exam_points(section.body_md)
            example = self._extract_example(section.body_md)
            cards.append(
                CardsPayload(
                    concept=section.title,
                    definition=definition,
                    exam_points=exam_points or ["重点理解章节核心概念。"],
                    example_q=example,
                    anchors=section.refs,
                )
            )
        return KnowledgeCards(cards=cards)

    def _extract_definition(self, markdown: str) -> str:
        sentences = split_sentences(markdown.replace("\n", " "))
        if sentences:
            return " ".join(sentences[:3])[:200]
        return "该概念在课程中用于支撑关键知识点，详见章节内容。"

    def _extract_exam_points(self, markdown: str) -> List[str]:
        lines = [line.strip("- ").strip() for line in markdown.splitlines() if line.strip().startswith("-")]
        return [line for line in lines[:3] if line]

    def _extract_example(self, markdown: str):
        match = re.search(r"(例|示例|案例)[:：]\s*(.+)", markdown)
        if not match:
            return None
        content = match.group(2)
        return {
            "stem": f"说明：{content[:120]}?",
            "answer": content[:180],
            "key_points": [content[:60]],
        }
