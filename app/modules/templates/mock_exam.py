from __future__ import annotations

from typing import List

from app.schemas.common import MockPaper, MockQuestion, NoteDoc
from app.utils.identifiers import new_id
from app.utils.text import split_sentences


class MockExamGenerator:
    def generate(self, note_doc: NoteDoc, mode: str, size: int, difficulty: str) -> MockPaper:
        questions: List[MockQuestion] = []
        sections = note_doc.sections if mode == "full" else note_doc.sections[:1]
        for section in sections:
            sentences = split_sentences(section.body_md.replace("#", " "))
            summary = sentences[0] if sentences else section.title
            questions.append(self._build_mcq(section, summary))
            questions.append(self._build_fill(section, summary))
            questions.append(self._build_short(section, summary))
        questions = questions[:size]
        meta = {"mode": mode, "size": size, "difficulty": difficulty}
        return MockPaper(meta=meta, items=questions)

    def _build_mcq(self, section, summary: str) -> MockQuestion:
        correct = summary
        distractors = [
            f"{section.title} 与 {section.title} 无关。",
            f"{section.title} 仅涉及定义，不含推导。",
            f"{section.title} 不需要掌握。",
        ]
        options = [correct] + distractors
        return MockQuestion(
            id=new_id("q"),
            type="mcq",
            stem=f"关于《{section.title}》，下列描述何者最贴近章节内容？",
            options=options,
            answer=correct,
            explain="选择最能反映章节核心观点的一项。",
            refs=section.refs,
        )

    def _build_fill(self, section, summary: str) -> MockQuestion:
        return MockQuestion(
            id=new_id("q"),
            type="fill",
            stem=f"《{section.title}》章节强调 ________。",
            answer=summary[:80],
            explain="填入本章节强调的核心结论。",
            refs=section.refs,
        )

    def _build_short(self, section, summary: str) -> MockQuestion:
        return MockQuestion(
            id=new_id("q"),
            type="short",
            stem=f"请概述《{section.title}》的重点内容，并说明其适用或限制条件。",
            answer=summary[:160],
            key_points=["突出概念", "说明条件或限制"],
            refs=section.refs,
        )
