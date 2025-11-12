from __future__ import annotations

import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from typing import Callable, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_text_splitters import TokenTextSplitter
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

    def _build_documents(self, layout_doc: LayoutDoc) -> List[Document]:
        documents: List[Document] = []
        for page in layout_doc.pages:
            content_segments = []
            for element in page.elements:
                if element.content:
                    content_segments.append(element.content)
                if element.caption:
                    content_segments.append(f"{element.kind.value.title()}说明: {element.caption}")
                if element.latex:
                    content_segments.append(f"公式: {element.latex}")
            joined = "\n".join(content_segments).strip()
            if not joined:
                continue
            documents.append(
                Document(
                    page_content=joined,
                    metadata={"page_no": page.page_no},
                )
            )
        if not documents:
            documents.append(Document(page_content="暂无内容。", metadata={"page_no": 0}))
        splitter = TokenTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        chunks: List[Document] = []
        for doc in documents:
            chunks.extend(splitter.split_documents([doc]))
        return chunks

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
        docs = self._build_documents(layout_doc)
        vector_store = load_or_create(session_id, docs)
        language_label = "Simplified Chinese" if language == "zh" else "English"
        system_prompt = (
            "You are StudyCompanion, tasked with generating structured course notes. "
            "You must adhere to the provided outline, respect the style instructions, "
            "and reference the supplied context. Output in GitHub-flavoured Markdown. "
            f"Write every heading, sentence, and annotation in {language_label}."
        )
        enhanced_outline = self._build_natural_outline(layout_doc, outline)
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
            context_text = self._retrieve_context(vector_store, section, docs)
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
                response = llm.invoke(
                    [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]
                )
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

    def _retrieve_context(self, vector_store, section: OutlineNode, docs: List[Document]) -> str:
        if not section.anchors:
            top_docs = vector_store.similarity_search(section.summary, k=3)
        else:
            top_docs = []
            for anchor in section.anchors:
                matches = vector_store.similarity_search(
                    f"Page {anchor.page} content related to {section.title}", k=1
                )
                top_docs.extend(matches)
            if not top_docs:
                top_docs = vector_store.similarity_search(section.summary, k=3)
        unique_texts = []
        seen = set()
        for doc in top_docs:
            text = doc.page_content.strip()
            if text not in seen:
                unique_texts.append(text)
                seen.add(text)
        return "\n\n".join(unique_texts[:3])

  
    def _build_prompt(self, section: OutlineNode, style_instructions: str, context_text: str) -> str:
        anchors_text = (
            "\n".join(f"- 页 {anchor.page} · 锚点 {anchor.ref}" for anchor in section.anchors)
            if section.anchors
            else "- 无显式锚点，可结合上下文自由组织。"
        )
        structure_template = self._build_structure_template(section)
        structure_notes = self._structure_outline_notes(section)
        return (
            "你是一名大学课程讲师，请根据给定的自然章节结构写出完整讲解。\n"
            f"章节标题：{section.title}\n"
            f"章节概述：{section.summary}\n"
            f"内容锚点：\n{anchors_text}\n\n"
            "结构树（禁止新增/删减/改名标题，必须依次输出并在标题下填写内容）：\n"
            f"{structure_template}\n\n"
            "结构提示（供参考，可融入过渡语和段落）：\n"
            f"{structure_notes}\n\n"
            f"写作风格设定：\n{style_instructions}\n\n"
            "写作要求：\n"
            "1. 以“概念 → 推导/论证 → 应用/案例 → 小结”的顺序组织内容，必要时显式说明过渡语；\n"
            "2. 对图片/公式引用使用占位符 `[FIG_PAGE_<页号>_IDX_<序号>: 说明]` 并解释其作用；\n"
            "3. 输出须以 `## {章节标题}` 开头，并严格沿用上述结构树中列出的标题层级；\n"
            "4. 禁止创建未在结构树中的标题或更改标题文字，可在标题下使用段落或 bullet；\n"
            "5. 避免原文粘贴或冗余页码，所有陈述都要结合上下文重写；\n"
            "6. 结尾在最后一个标题下用 1-2 句总结本节核心思想。\n\n"
            f"可用上下文：\n{context_text}\n\n"
            "请基于上述信息生成结构清晰、连贯的讲解。"
        )

    def _build_natural_outline(self, layout_doc: LayoutDoc, fallback: OutlineTree) -> OutlineTree:
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

    def _flatten_outline(self, outline: OutlineTree) -> List[OutlineNode]:
        sections: List[OutlineNode] = []

        def visit(node: OutlineNode) -> None:
            if node.summary.strip() or node.anchors:
                sections.append(node)
            for child in node.children:
                visit(child)

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
            if summary:
                notes.append(f"{indent}- {node.title}: {summary}")
            else:
                notes.append(f"{indent}- {node.title}: 待补充")
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
        return f"### {section.title}\n\n{section.summary}\n\n{bullet_points}"

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
