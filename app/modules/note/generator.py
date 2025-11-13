from __future__ import annotations

import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from typing import Callable, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.documents import Document

from app.modules.note.llm_client import get_llm
from app.modules.note.style_policies import build_style_instructions
from app.schemas.common import (
    AnchorRef,
    LayoutDoc,
    LayoutElement,
    NoteDoc,
    NoteEquation,
    NoteFigure,
    NoteSection,
    OutlineNode,
    OutlineTree,
)
from app.storage.vector_store import load_or_create, save
from app.utils.identifiers import new_id
from app.utils.logger import logger
from app.utils.outline import render_outline_markdown
from app.utils.text import normalize_whitespace, take_sentences


class NoteGenerator:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50, max_workers: int = 3):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_workers = max(1, max_workers)

    # --- 语义 RAG 数据库构建 ---
    def _build_semantic_documents(
        self, outline: OutlineTree, layout_doc: LayoutDoc
    ) -> tuple[List[Document], dict[str, str]]:
        page_text_map = self._extract_page_text(layout_doc)
        documents: List[Document] = []
        section_contexts: dict[str, str] = {}
        for section in outline.root.children:
            context_text = self._compose_block_context(section, page_text_map)
            metadata = {
                "section_id": section.section_id,
                "title": section.title,
                "page_span": self._format_page_span(section),
                "page_start": section.page_start,
                "page_end": section.page_end,
            }
            documents.append(Document(page_content=context_text, metadata=metadata))
            section_contexts[section.section_id] = context_text
        if not documents:
            documents.append(
                Document(
                    page_content="文档暂无可用内容。",
                    metadata={"section_id": "fallback", "title": "Empty"},
                )
            )
        return documents, section_contexts

    def _extract_page_text(self, layout_doc: LayoutDoc) -> dict[int, str]:
        page_text: dict[int, str] = {}
        for page in layout_doc.pages:
            segments: List[str] = []
            for element in page.elements:
                if element.content:
                    segments.append(element.content.strip())
                if element.caption:
                    segments.append(f"{element.kind.value}说明: {element.caption.strip()}")
                if element.latex:
                    segments.append(f"公式: {element.latex.strip()}")
            joined = "\n".join(seg for seg in segments if seg).strip()
            if joined:
                page_text[page.page_no] = joined
        return page_text

    def _compose_block_context(self, section: OutlineNode, page_text_map: dict[int, str]) -> str:
        page_numbers = self._collect_pages(section)
        page_segments: List[str] = []
        for page in page_numbers:
            content = page_text_map.get(page)
            if not content:
                continue
            page_segments.append(f"[Page {page}]\n{content}")
        outline_notes = self._structure_outline_notes(section)
        summary = (section.summary or "").strip() or "暂无概述。"
        page_span = self._format_page_span(section)
        parts = [
            f"Section: {section.title}",
            f"Pages: {page_span}",
            f"Summary: {summary}",
            "Semantic Outline:",
            outline_notes or "- 无子结构",
        ]
        if page_segments:
            parts.append("Source Pages:")
            parts.append("\n\n".join(page_segments))
        return "\n".join(parts).strip()

    def _collect_pages(self, section: OutlineNode) -> List[int]:
        pages = list(section.pages or [])
        for anchor in section.anchors:
            pages.append(anchor.page)
        for child in section.children:
            pages.extend(self._collect_pages(child))
        deduped: List[int] = []
        seen = set()
        for page in pages:
            if page in seen:
                continue
            seen.add(page)
            deduped.append(page)
        return sorted(deduped)

    def _format_page_span(self, section: OutlineNode) -> str:
        start = section.page_start or (section.pages[0] if section.pages else None)
        end = section.page_end or (section.pages[-1] if section.pages else None)
        if start and end:
            if start == end:
                return f"p.{start}"
            return f"p.{start}–{end}"
        if start:
            return f"p.{start}"
        return "p.?–?"

    def generate(
        self,
        session_id: str,
        outline: OutlineTree,
        layout_doc: LayoutDoc,
        detail_level: str,
        difficulty: str,
        language: str,
        progress_callback: Optional[Callable[[Dict[str, object]], None]] = None,
    ) -> NoteDoc:
        style_instructions = build_style_instructions(detail_level, difficulty, language)
        enhanced_outline = self._build_natural_outline(layout_doc, outline)
        docs, section_contexts = self._build_semantic_documents(enhanced_outline, layout_doc)
        vector_store = load_or_create(session_id, docs, rebuild=True)
        language_label = "Simplified Chinese" if language == "zh" else "English"
        system_messages = [
            SystemMessage(
                content=(
                    "You are StudyCompanion, tasked with generating structured course notes. "
                    "Adhere strictly to the provided outline and supplied context, and output "
                    "GitHub-flavoured Markdown only. "
                    f"Write every heading, paragraph, bullet, formula, and annotation in {language_label}."
                )
            ),
            SystemMessage(content=f"写作规范如下，请逐条遵守：\n{style_instructions}"),
        ]
        sections_to_render = self._flatten_outline(enhanced_outline)
        total_sections = len(sections_to_render)
        if progress_callback:
            progress_callback(
                {
                    "phase": "prepare",
                    "message": f"共 {total_sections} 个自然结构章节待生成…",
                }
            )
        if progress_callback:
            progress_callback({"phase": "sections_total", "total": total_sections})
        figures_by_page, equations_by_page = self._collect_assets(layout_doc)
        if total_sections == 0:
            save(session_id, vector_store)
            return NoteDoc(
                style={"detail_level": detail_level, "difficulty": difficulty, "language": language},
                toc=[],
                sections=[],
            )

        section_jobs: List[Tuple[int, OutlineNode, str, str]] = []
        for index, section in enumerate(sections_to_render, start=1):
            context_text = section_contexts.get(section.section_id, "")
            prompt = self._build_prompt(section, style_instructions, context_text)
            section_jobs.append((index, section, prompt, context_text))

        def render_section(job: Tuple[int, OutlineNode, str, str]) -> Tuple[int, NoteSection]:
            index, section, prompt, context_text = job
            if progress_callback:
                progress_callback(
                    {
                        "phase": "section",
                        "status": "start",
                        "index": index,
                        "total": total_sections,
                        "title": section.title,
                    }
                )
            llm = get_llm(temperature=0.2)
            try:
                response = llm.invoke([*system_messages, HumanMessage(content=prompt)])
                markdown = getattr(response, "content", str(response))
            except Exception as exc:  # pragma: no cover - network guard
                logger.warning("LLM generation failed, using fallback: %s", exc)
                markdown = self._fallback_section(section, context_text)
            figures = self._resolve_figures(section, figures_by_page)
            equations = self._resolve_equations(section, equations_by_page)
            note_section = NoteSection(
                section_id=section.section_id,
                title=section.title,
                body_md=markdown.strip(),
                figures=figures,
                equations=equations,
                refs=[f"anchor:{section.section_id}@page{a.page}#{a.ref}" for a in section.anchors],
            )
            if progress_callback:
                progress_callback(
                    {
                        "phase": "section",
                        "status": "complete",
                        "index": index,
                        "total": total_sections,
                        "title": section.title,
                    }
                )
            return index, note_section

        sections_map: Dict[int, NoteSection] = {}
        max_workers = min(self.max_workers, total_sections) or 1

        if max_workers == 1:
            for job in section_jobs:
                index, note_section = render_section(job)
                sections_map[index] = note_section
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(render_section, job) for job in section_jobs]
                for future in as_completed(futures):
                    index, note_section = future.result()
                    sections_map[index] = note_section

        sections = [sections_map[index] for index in sorted(sections_map)]
        save(session_id, vector_store)
        toc = [
            {"section_id": section.section_id, "title": section.title}
            for section in enhanced_outline.root.children
        ]
        return NoteDoc(
            style={"detail_level": detail_level, "difficulty": difficulty, "language": language},
            toc=toc,
            sections=sections,
        )

    def _build_prompt(self, section: OutlineNode, style_instructions: str, context_text: str) -> str:
        anchors_text = (
            "\n".join(f"- 页 {anchor.page} · 锚点 {anchor.ref}" for anchor in section.anchors)
            if section.anchors
            else "- 无显式锚点，可结合上下文自由组织。"
        )
        structure_template = self._build_structure_template(section)
        structure_notes = self._structure_outline_notes(section)
        page_span = self._format_page_span(section)
        return (
            "【写作任务】根据给出的自然结构与参考资料，撰写完整章节讲解，禁止只复述大纲。\n"
            f"【章节标题】{section.title}\n"
            f"【章节概述】{section.summary}\n"
            f"【覆盖页码】{page_span}\n"
            f"【内容锚点】\n{anchors_text}\n\n"
            "【必须遵循的 Markdown 结构】\n"
            f"{structure_template}\n"
            "以上每个标题都需要 2-3 句（或条）说明概念、推导、应用与总结，禁止新增/删改标题。\n\n"
            "【结构提示】\n"
            f"{structure_notes}\n\n"
            "【写作风格】\n"
            f"{style_instructions}\n\n"
            "【参考上下文】\n"
            f"{context_text}\n\n"
            "【输出要求】\n"
            "1. 输出以 `## {章节标题}` 开头，并按照结构顺序依次展开子标题；\n"
            "2. 每个标题必须包含连续段落或 bullet 解释概念、推导、案例与注意事项；\n"
            "3. 每个标题至少 2 句正文或等量内容，并写出承上启下的过渡语；\n"
            "4. 图片/图表占位符使用 `[FIG_PAGE_<页号>_IDX_<序号>: 说明]` 并解释其作用；\n"
            "5. 所有公式务必使用 `$$公式$$` 包裹，并解释符号含义与适用条件；\n"
            "6. 最后一个子标题结尾补充 1-2 句总结或下一步提示。\n"
            "请严格依据以上要求输出完整讲解。"
        )

    def _build_natural_outline(self, layout_doc: LayoutDoc, fallback: OutlineTree) -> OutlineTree:
        if fallback.root.children:
            return self._ensure_outline_markdown(fallback)
        try:
            page_units = self._extract_page_units(layout_doc)
            if not page_units:
                return self._ensure_outline_markdown(fallback)
            root_children: List[OutlineNode] = []
            level_stack: List[OutlineNode] = []
            for unit in page_units:
                if not unit["title"].strip() and level_stack:
                    self._extend_outline_node(level_stack[-1], unit)
                    continue
                level = max(1, unit["level"])
                while level_stack and level_stack[-1].level >= level:
                    level_stack.pop()
                parent = level_stack[-1] if level_stack else None
                siblings = parent.children if parent else root_children
                existing = (
                    siblings[-1]
                    if siblings
                    and siblings[-1].level == level
                    and self._titles_similar(siblings[-1].title, unit["title"])
                    else None
                )
                if existing:
                    self._extend_outline_node(existing, unit)
                    level_stack.append(existing)
                    continue
                node = OutlineNode(
                    section_id=new_id("ns"),
                    title=unit["title"],
                    summary=unit["summary"],
                    anchors=list(unit["anchors"]),
                    level=level,
                    children=[],
                    pages=list(unit["pages"]),
                    page_start=unit["page_start"],
                    page_end=unit["page_end"],
                )
                siblings.append(node)
                if parent:
                    self._append_unique_anchors(parent, node.anchors)
                level_stack.append(node)
            if not root_children:
                return self._ensure_outline_markdown(fallback)
            root = OutlineNode(
                section_id=fallback.root.section_id,
                title=fallback.root.title,
                summary="自然结构章节重建完成。",
                anchors=list(fallback.root.anchors),
                level=0,
                children=root_children,
            )
            return self._outline_with_markdown(root)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("自然结构重建失败，回退旧大纲: %s", exc)
            return self._ensure_outline_markdown(fallback)

    def _extract_page_units(self, layout_doc: LayoutDoc) -> List[dict]:
        units: List[dict] = []
        for page in layout_doc.pages:
            title = ""
            anchors: List[AnchorRef] = []
            body_segments: List[str] = []
            for element in page.elements:
                text = normalize_whitespace(element.content or "")
                if element.kind.value == "title" and not title and text:
                    title = text[:80]
                elif text:
                    body_segments.append(text)
                if element.caption:
                    body_segments.append(normalize_whitespace(element.caption))
                if element.latex:
                    body_segments.append(element.latex)
                if element.ref:
                    anchors.append(AnchorRef(page=page.page_no, ref=element.ref))
            merged_body = " ".join(seg for seg in body_segments if seg)
            summary = take_sentences(merged_body, 3)[:320] if merged_body else ""
            if not summary:
                summary = "本部分暂无明确文字内容，请结合上下文生成。"
            normalized_title = title or (body_segments[0][:60] if body_segments else "")
            level = self._infer_level(normalized_title)
            units.append(
                {
                    "title": normalized_title or f"页面{page.page_no}",
                    "summary": summary,
                    "anchors": anchors[:6] or [AnchorRef(page=page.page_no, ref=f"page-{page.page_no}")],
                    "level": level,
                    "pages": [page.page_no],
                    "page_start": page.page_no,
                    "page_end": page.page_no,
                }
            )
        return units

    def _infer_level(self, title: str) -> int:
        if not title:
            return 3
        normalized = normalize_whitespace(title)
        lowered = normalized.lower()
        if re.match(r"^(chapter|chap\.)\s*\d+", lowered) or re.match(r"^第[一二三四五六七八九十百零两]+\s*章", normalized):
            return 1
        if re.match(r"^\d+\.\d+\.\d+", normalized):
            return 3
        if re.match(r"^\d+\.\d+", normalized):
            return 2
        if re.match(r"^\d+(\s|-)", normalized):
            return 1
        if len(normalized.split()) <= 4:
            return 1
        return 2

    def _titles_similar(self, left: str, right: str) -> bool:
        if not left or not right:
            return False
        left_norm = normalize_whitespace(left).lower()
        right_norm = normalize_whitespace(right).lower()
        if left_norm == right_norm:
            return True
        left_key = left_norm.split(":")[0]
        right_key = right_norm.split(":")[0]
        if left_key and left_key == right_key:
            return True
        return SequenceMatcher(None, left_norm, right_norm).ratio() >= 0.88

    def _extend_outline_node(self, node: OutlineNode, unit: dict) -> None:
        node.summary = self._merge_summary(node.summary, unit["summary"])
        combined_pages = list(node.pages or [])
        for page in unit.get("pages", []):
            if page not in combined_pages:
                combined_pages.append(page)
        node.pages = combined_pages
        node.page_start = self._min_page(node.page_start, unit.get("page_start"))
        node.page_end = self._max_page(node.page_end, unit.get("page_end"))
        existing = {(anchor.page, anchor.ref) for anchor in node.anchors}
        for anchor in unit["anchors"]:
            key = (anchor.page, anchor.ref)
            if key not in existing:
                node.anchors.append(anchor)
                existing.add(key)

    def _append_unique_anchors(self, node: OutlineNode, anchors: List[AnchorRef]) -> None:
        existing = {(anchor.page, anchor.ref) for anchor in node.anchors}
        for anchor in anchors:
            key = (anchor.page, anchor.ref)
            if key in existing:
                continue
            node.anchors.append(anchor)
            existing.add(key)
            if len(node.anchors) >= 12:
                break

    def _merge_summary(self, left: str, right: str) -> str:
        merged = " ".join(filter(None, [left, right]))
        if not merged:
            return ""
        return take_sentences(merged, 3)[:320] or merged[:320]

    def _min_page(self, current: Optional[int], candidate: Optional[int]) -> Optional[int]:
        if current is None:
            return candidate
        if candidate is None:
            return current
        return min(current, candidate)

    def _max_page(self, current: Optional[int], candidate: Optional[int]) -> Optional[int]:
        if current is None:
            return candidate
        if candidate is None:
            return current
        return max(current, candidate)

    def _flatten_outline(self, outline: OutlineTree) -> List[OutlineNode]:
        return [child for child in outline.root.children if child.title.strip()]

    def _build_structure_template(self, section: OutlineNode) -> str:
        lines: List[str] = []

        def visit(node: OutlineNode) -> None:
            level = max(2, min(node.level, 5)) if node.level else 2
            prefix = "#" * level
            lines.append(f"{prefix} {node.title}")
            for child in node.children:
                visit(child)

        visit(section)
        return "\n".join(lines)

    def _structure_outline_notes(self, section: OutlineNode) -> str:
        notes: List[str] = []

        def visit(node: OutlineNode, depth: int = 0) -> None:
            indent = "  " * depth
            summary = (node.summary or "").strip()
            page_span = self._format_page_span(node)
            if summary:
                notes.append(f"{indent}- {node.title} ({page_span}): {summary}")
            else:
                notes.append(f"{indent}- {node.title} ({page_span}): 待补充")
            for child in node.children:
                visit(child, depth + 1)

        visit(section)
        return "\n".join(notes)

    def _outline_with_markdown(self, root: OutlineNode) -> OutlineTree:
        return OutlineTree(root=root, markdown=render_outline_markdown(root))

    def _ensure_outline_markdown(self, outline: OutlineTree) -> OutlineTree:
        if outline.markdown:
            return outline
        return OutlineTree(root=outline.root, markdown=render_outline_markdown(outline.root))

    def _fallback_section(self, section: OutlineNode, context_text: str) -> str:
        context = context_text.splitlines()[:5]
        bullet_points = "\n".join(f"- {line}" for line in context if line.strip())
        return f"## {section.title}\n\n{section.summary}\n\n{bullet_points}"

    def _collect_assets(
        self, layout_doc: LayoutDoc
    ) -> Tuple[Dict[int, List[LayoutElement]], Dict[int, List[LayoutElement]]]:
        figures: Dict[int, List[LayoutElement]] = defaultdict(list)
        equations: Dict[int, List[LayoutElement]] = defaultdict(list)
        for page in layout_doc.pages:
            for element in page.elements:
                if element.kind.value == "image":
                    figures[page.page_no].append(element)
                if element.kind.value == "formula":
                    equations[page.page_no].append(element)
        return figures, equations

    def _resolve_figures(
        self, section: OutlineNode, figures_by_page: Dict[int, List[LayoutElement]]
    ) -> List[NoteFigure]:
        figures: List[NoteFigure] = []
        for anchor in section.anchors:
            for element in figures_by_page.get(anchor.page, []):
                if element.image_uri:
                    figures.append(
                        NoteFigure(image_uri=element.image_uri, caption=element.caption or "")
                    )
        return figures

    def _resolve_equations(
        self, section: OutlineNode, equations_by_page: Dict[int, List[LayoutElement]]
    ) -> List[NoteEquation]:
        equations: List[NoteEquation] = []
        for anchor in section.anchors:
            for element in equations_by_page.get(anchor.page, []):
                if element.latex:
                    equations.append(
                        NoteEquation(latex=element.latex, caption=element.caption or "")
                    )
        return equations
