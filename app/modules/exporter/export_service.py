from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from markdown_pdf import MarkdownPdf, Section
from PIL import Image, ImageDraw

from app.schemas.common import ExportResponse, KnowledgeCards, MockPaper, MindmapGraph, NoteDoc

EXPORT_ROOT = Path(os.getenv("SC_EXPORT_ROOT", "exports"))
EXPORT_ROOT.mkdir(exist_ok=True)


class ExportService:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session_dir = EXPORT_ROOT / session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def export_notes(self, note_doc: NoteDoc, fmt: str) -> ExportResponse:
        markdown = self._notes_to_markdown(note_doc)
        if fmt == "md":
            filename = self._write_text("notes.md", markdown)
        elif fmt == "pdf":
            filename = self._write_pdf("notes.pdf", markdown)
        else:
            raise ValueError("Unsupported format for notes")
        return ExportResponse(download_url=str(filename), filename=filename.name)

    def export_cards(self, cards: KnowledgeCards, fmt: str) -> ExportResponse:
        markdown = self._cards_to_markdown(cards)
        if fmt == "md":
            filename = self._write_text("cards.md", markdown)
        elif fmt == "pdf":
            filename = self._write_pdf("cards.pdf", markdown)
        else:
            raise ValueError("Unsupported format for cards")
        return ExportResponse(download_url=str(filename), filename=filename.name)

    def export_mock(self, paper: MockPaper, fmt: str) -> ExportResponse:
        markdown = self._mock_to_markdown(paper)
        if fmt == "md":
            filename = self._write_text("mock.md", markdown)
        elif fmt == "pdf":
            filename = self._write_pdf("mock.pdf", markdown)
        else:
            raise ValueError("Unsupported format for mock exam")
        return ExportResponse(download_url=str(filename), filename=filename.name)

    def export_mindmap(self, graph: MindmapGraph, fmt: str) -> ExportResponse:
        if fmt != "png":
            raise ValueError("Mind map only supports PNG export")
        filename = self._write_mindmap_png("mindmap.png", graph)
        return ExportResponse(download_url=str(filename), filename=filename.name)

    def _notes_to_markdown(self, note_doc: NoteDoc) -> str:
        parts = [f"# {section.title}\n\n{section.body_md}\n" for section in note_doc.sections]
        return "\n".join(parts)

    def _cards_to_markdown(self, cards: KnowledgeCards) -> str:
        parts = []
        for card in cards.cards:
            block = [
                f"## {card.concept}",
                f"**定义：** {card.definition}",
                "**考点：**",
            ]
            block.extend(f"- {point}" for point in card.exam_points)
            if card.example_q:
                example = card.example_q
                block.append("**例题：**")
                block.append(f"Q: {example['stem']}")
                block.append(f"A: {example['answer']}")
            parts.append("\n".join(block))
        return "\n\n".join(parts)

    def _mock_to_markdown(self, paper: MockPaper) -> str:
        parts = [f"# 模拟试卷（模式：{paper.meta['mode']}，难度：{paper.meta['difficulty']}）\n"]
        for idx, item in enumerate(paper.items, start=1):
            block = [f"## 第 {idx} 题（{item.type}）", item.stem]
            if item.options:
                block.extend(f"- {opt}" for opt in item.options)
            block.append(f"**答案：** {item.answer}")
            if item.explain:
                block.append(f"**解析：** {item.explain}")
            if item.key_points:
                block.append("**得分点：** " + ", ".join(item.key_points))
            parts.append("\n\n".join(block))
        return "\n\n".join(parts)

    def _write_text(self, filename: str, content: str) -> Path:
        path = self.session_dir / filename
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def _write_pdf(self, filename: str, markdown: str) -> Path:
        path = self.session_dir / filename
        pdf = MarkdownPdf()
        pdf.add_section(Section(markdown))
        pdf.save(str(path))
        return path

    def _write_mindmap_png(self, filename: str, graph: MindmapGraph) -> Path:
        width = 1024
        height = 80 * max(len(graph.nodes), 1)
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        for idx, node in enumerate(graph.nodes):
            y = 40 + idx * 80
            draw.text((20 + node["level"] * 60, y), f"{node['label']}", fill="black")
        path = self.session_dir / filename
        image.save(path)
        return path