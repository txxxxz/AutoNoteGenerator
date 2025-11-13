from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

from markdown_pdf import MarkdownPdf, Section
from PIL import Image, ImageDraw

from app.schemas.common import (
    ExportResponse,
    KnowledgeCards,
    MindmapGraph,
    MockPaper,
    NoteDoc,
    NoteEquation,
    NoteFigure,
    NoteSection,
)
from app.storage import assets

MARKDOWN_IMAGE_PATTERN = re.compile(r"(!\[[^\]]*\]\()([^)]+)(\))")
HTML_IMAGE_PATTERN = re.compile(r'(<img[^>]*\bsrc=["\'])([^"\']+)(["\'][^>]*>)', re.IGNORECASE)
CSS_PATH = Path(__file__).with_name("github_markdown.css")
DEFAULT_EXPORT_CSS = """
body {
  font-family: "Songti SC", "SimSun", "STSong", "宋体", serif;
  color: #333;
  line-height: 1.7;
  font-size: 8px;
}
"""

EXPORT_ROOT = Path(os.getenv("SC_EXPORT_ROOT", "exports"))
EXPORT_ROOT.mkdir(exist_ok=True)


@lru_cache(maxsize=1)
def _load_github_css() -> str:
    if CSS_PATH.exists():
        return CSS_PATH.read_text(encoding="utf-8")
    return DEFAULT_EXPORT_CSS


class ExportService:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session_dir = EXPORT_ROOT / session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._css = _load_github_css()

    def export_notes(self, note_doc: NoteDoc, fmt: str) -> ExportResponse:
        markdown = self._notes_to_markdown(note_doc)
        if fmt == "md":
            filename = self._write_text("notes.md", markdown)
        elif fmt == "pdf":
            pdf_ready = self._rewrite_image_sources(markdown)
            filename = self._write_pdf("notes.pdf", pdf_ready)
        else:
            raise ValueError("Unsupported format for notes")
        return ExportResponse(download_url=str(filename), filename=filename.name)

    def export_cards(self, cards: KnowledgeCards, fmt: str) -> ExportResponse:
        markdown = self._cards_to_markdown(cards)
        if fmt == "md":
            filename = self._write_text("cards.md", markdown)
        elif fmt == "pdf":
            pdf_ready = self._rewrite_image_sources(markdown)
            filename = self._write_pdf("cards.pdf", pdf_ready)
        else:
            raise ValueError("Unsupported format for cards")
        return ExportResponse(download_url=str(filename), filename=filename.name)

    def export_mock(self, paper: MockPaper, fmt: str) -> ExportResponse:
        markdown = self._mock_to_markdown(paper)
        if fmt == "md":
            filename = self._write_text("mock.md", markdown)
        elif fmt == "pdf":
            pdf_ready = self._rewrite_image_sources(markdown)
            filename = self._write_pdf("mock.pdf", pdf_ready)
        else:
            raise ValueError("Unsupported format for mock exam")
        return ExportResponse(download_url=str(filename), filename=filename.name)

    def export_mindmap(self, graph: MindmapGraph, fmt: str) -> ExportResponse:
        if fmt != "png":
            raise ValueError("Mind map only supports PNG export")
        filename = self._write_mindmap_png("mindmap.png", graph)
        return ExportResponse(download_url=str(filename), filename=filename.name)

    def _notes_to_markdown(self, note_doc: NoteDoc) -> str:
        sections = [self._section_to_markdown(section) for section in note_doc.sections]
        sections = [section for section in sections if section]
        return "\n\n".join(sections)

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
        pdf = MarkdownPdf(toc_level=2, optimize=True)
        pdf.add_section(Section(markdown), user_css=self._css)
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

    def _section_to_markdown(self, section: NoteSection) -> str:
        blocks = [f"# {section.title}".strip()]
        body = (section.body_md or "").strip()
        if body:
            blocks.append(body)
        for figure in section.figures:
            figure_block = self._figure_to_markdown(figure)
            if figure_block:
                blocks.append(figure_block)
        for equation in section.equations:
            equation_block = self._equation_to_markdown(equation)
            if equation_block:
                blocks.append(equation_block)
        return "\n\n".join(blocks).strip()

    def _figure_to_markdown(self, figure: NoteFigure) -> Optional[str]:
        if not figure.image_uri:
            return None
        caption = (figure.caption or "").strip() or "图"
        block = [f'![{caption}]({figure.image_uri})']
        if figure.caption:
            block.append(f"*{figure.caption.strip()}*")
        return "\n".join(block)

    def _equation_to_markdown(self, equation: NoteEquation) -> Optional[str]:
        latex = (equation.latex or "").strip()
        if not latex:
            return None
        block = ["```math", latex, "```"]
        if equation.caption:
            block.append(f"*{equation.caption.strip()}*")
        return "\n".join(block)

    def _rewrite_image_sources(self, markdown: str) -> str:
        if not markdown:
            return markdown
        cache: dict[str, Optional[str]] = {}

        def lookup(url: str) -> Optional[str]:
            if url not in cache:
                cache[url] = self._local_asset_path(url)
            return cache[url]

        def md_repl(match: re.Match[str]) -> str:
            original = match.group(2).strip()
            local = lookup(original)
            if not local:
                return match.group(0)
            return f"{match.group(1)}{local}{match.group(3)}"

        def html_repl(match: re.Match[str]) -> str:
            original = match.group(2).strip()
            local = lookup(original)
            if not local:
                return match.group(0)
            return f'{match.group(1)}{local}{match.group(3)}'

        updated = MARKDOWN_IMAGE_PATTERN.sub(md_repl, markdown)
        return HTML_IMAGE_PATTERN.sub(html_repl, updated)

    def _local_asset_path(self, uri: str) -> Optional[str]:
        if not uri:
            return None
        parsed = urlparse(uri)
        candidates = []
        if parsed.scheme in ("", "file"):
            candidates.append(unquote(parsed.path or uri))
        else:
            candidates.append(unquote(parsed.path or ""))
        candidates.append(uri)
        for candidate in candidates:
            path = self._resolve_asset_candidate(candidate)
            if path:
                return path
        return None

    def _resolve_asset_candidate(self, value: str) -> Optional[str]:
        if not value:
            return None
        normalized = value.lstrip("/")
        direct_path = Path(value)
        if direct_path.is_file():
            return str(direct_path.resolve())
        normalized_path = Path(normalized)
        parts = [part for part in normalized_path.parts if part not in ("/", "")]
        if parts:
            try:
                assets_idx = parts.index("assets")
            except ValueError:
                assets_idx = -1
            if assets_idx >= 0 and len(parts) > assets_idx + 1:
                session = parts[assets_idx + 1]
                remainder_parts = parts[assets_idx + 2 :]
                candidate = assets.ASSET_ROOT / session
                if remainder_parts:
                    candidate = candidate.joinpath(*remainder_parts)
                if candidate.exists():
                    return str(candidate.resolve())
        fallback_name = normalized_path.name
        if fallback_name:
            session_dir = assets.session_dir(self.session_id)
            fallback = session_dir / fallback_name
            if fallback.exists():
                return str(fallback.resolve())
        return None
