from __future__ import annotations

import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from html import escape
from typing import Callable, Dict, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from app.modules.note.llm_client import get_llm
from app.modules.note.style_policies import (
    StyleProfile,
    build_style_instructions,
    build_style_profile,
)
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


PAGE_HEADING_PATTERN = re.compile(
    r"^(?P<leading>#{2,6})\s*"
    r"(?:第\s*(?P<page_cn>\d+)\s*页|Page\s+(?P<page_en>\d+))"
    r"(?:\s*[:：-]\s*(?P<rest>.*))?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


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
        """组织上下文，按页码顺序清晰呈现，方便LLM逐页讲解"""
        page_numbers = self._collect_pages(section)
        page_segments: List[str] = []
        for page in sorted(page_numbers):
            content = page_text_map.get(page)
            if not content:
                continue
            # 更清晰的页码标记，方便LLM识别
            page_segments.append(f"=== 第{page}页 ===\n{content}")
        
        summary = (section.summary or "").strip() or "暂无概述。"
        page_span = self._format_page_span(section)
        
        parts = [
            f"【章节】{section.title}",
            f"【页码范围】{page_span}",
            f"【总体概述】{summary}",
        ]
        
        if page_segments:
            parts.append("\n【逐页内容】")
            parts.append("\n\n".join(page_segments))
        
        # 如果有子章节结构，也提供参考
        if section.children:
            outline_notes = self._structure_outline_notes(section)
            if outline_notes:
                parts.append("\n【子章节结构参考】")
                parts.append(outline_notes)
        
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
        """
        Stream a full note document with style-aware prompting.

        The generator now consults StyleProfile directives to split system prompts,
        assemble few-shot structural hints, and post-process the raw LLM output so
        that headers、summaries、analogies、表格等可见结构会随着风格设置明显变化。
        """
        try:
            style_profile = build_style_profile(detail_level, difficulty, language)
        except KeyError as exc:
            logger.warning(
                "Unknown style tuple detail=%s tone=%s -> fallback instructions: %s",
                detail_level,
                difficulty,
                exc,
            )
            fallback_text = build_style_instructions(detail_level, difficulty, language)
            style_profile = StyleProfile(
                text=fallback_text,
                directives={"language": language, "summary_mode": "none"},
                example_snippet="",
            )
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
                    f"Write every heading, paragraph, bullet, formula, and annotation in {language_label}. "
                    "Respect style directives before answering any follow-up user nudge."
                )
            ),
            SystemMessage(content=f"请遵守以下风格规则：\n{style_profile.text}"),
        ]
        if style_profile.example_snippet:
            system_messages.append(
                SystemMessage(
                    content="以下示例展示了期望的 Markdown 节奏，请模仿结构：\n"
                    f"{style_profile.example_snippet}"
                )
            )
        sections_to_render = self._flatten_outline(enhanced_outline)
        total_sections = len(sections_to_render)
        
        # 统计总页数
        total_pages = sum(len(section.pages or []) for section in sections_to_render)
        
        if progress_callback:
            progress_callback(
                {
                    "phase": "prepare",
                    "message": f"共 {total_sections} 个章节，覆盖 {total_pages} 页PPT，准备逐页讲解…",
                }
            )
        
        logger.info(
            "准备生成笔记: session_id=%s, 章节数=%d, 总页数=%d",
            session_id,
            total_sections,
            total_pages
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
            prompt = self._build_prompt(section, style_profile, context_text)
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
            markdown = self._post_process_markdown(
                markdown, section, style_profile.directives
            )
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

    def _build_prompt(
        self, section: OutlineNode, style_profile: StyleProfile, context_text: str
    ) -> str:
        directives = (style_profile.directives or {}) if style_profile else {}
        page_span = self._format_page_span(section)
        pages = sorted(set(section.pages or []))
        language = directives.get("language", "zh")
        summary_mode = directives.get("summary_mode", "none")
        header_template = directives.get("page_header_template", "### 第{page}页")
        page_numbers = pages or [section.page_start or section.page_end or "?"]

        if language == "zh":
            heading_template = "## {title} ({page_span})"
            task_intro = "【写作任务】按照 PPT 页码顺序，逐页详细讲解本章节内容。"
            structure_label = "【必须遵循的逐页结构】"
            requirements_label = "【写作要求】"
            context_label = "【参考资料（按页组织）】"
            section_label = "【章节标题】"
            summary_label = "【总体概述】"
            span_label = "【覆盖页码】"
            summary_stub = "> **章节洞察：** 用 2-3 句话串联推理、限制与下一步提醒。"
            concept_line = "- 核心概念/问题：用 2-3 句话点出动机与定义。"
            detail_line = "- 推导、案例或应用：交代条件、步骤与用途。"
            table_stub = "| 对比项 | 说明 | 提示 |\n| --- | --- | --- |\n| 示例 | 在此比较差异 | 应用线索 |"
            analogy_stub = "> 💡 打个比方：……"
            takeaway_stub = "> **一句话总结：** （填入 1 句 takeaway）"
        else:
            heading_template = "## {title} ({page_span})"
            task_intro = "[Task] Walk through the PPT deck page by page so a student can follow without slides."
            structure_label = "[Structure]"
            requirements_label = "[Writing Requirements]"
            context_label = "[Context grouped by page]"
            section_label = "[Section]"
            summary_label = "[Overview]"
            span_label = "[Page span]"
            summary_stub = "> **Section insight:** Capture the reasoning chain and next-step cues."
            concept_line = "- Core idea / definition: explain why it matters first."
            detail_line = "- Derivation / scenario: outline steps, assumptions, and usage."
            table_stub = "| Aspect | Explanation | Tip |\n| --- | --- | --- |\n| Example | Compare the two ideas | Coach the reader |"
            analogy_stub = "> 💡 Analogy: ..."
            takeaway_stub = "> **One-sentence takeaway:** (fill in a one-line takeaway)"

        page_structure_lines: List[str] = []
        for page in page_numbers:
            header = header_template.format(page=page)
            per_page_lines = [header, concept_line, detail_line]
            # 移除强制表格模板，让LLM根据内容自主选择
            # if directives.get("use_table"):
            #     per_page_lines.append(table_stub)
            if directives.get("analogy_required"):
                per_page_lines.append(analogy_stub)
            if summary_mode == "takeaway":
                per_page_lines.append(takeaway_stub)
            page_structure_lines.append("\n".join(per_page_lines))

        if summary_mode == "insight":
            page_structure_lines.append(summary_stub)

        page_template = "\n\n".join(page_structure_lines)

        subsection_template = ""
        if section.children:
            label = "【子章节结构】" if language == "zh" else "[Sub-sections]"
            subsection_template = f"\n\n{label}\n" + self._build_structure_template(section)

        heading_line = heading_template.format(title=section.title, page_span=page_span)
        base_requirements = (
            [
                f"1. 以 `{heading_line}` 作为章节大标题，并保持 Markdown 二级标题。",
                "2. 严格按照上述页码顺序输出正文，确保每页至少 4-6 句完整讲解。",
                "3. **智能选择格式**：根据内容特点，灵活使用段落、项目符号或表格。",
                "   - **表格**：仅在需要对比多个项目（如优缺点、多种方法、特性对比）时使用。",
                "   - **项目符号（-）**：用于罗列步骤、要点清单、多个独立概念。",
                "   - **段落**：用于连贯的叙述、推导过程、概念解释。",
                "4. 图片占位符使用 `[FIG_PAGE_<页号>_IDX_<序号>: 用途说明]` 并解释其含义。",
                "5. 遇到公式时使用 `$`/`$$` 包裹，并逐个解释符号含义与适用条件。",
            ]
            if language == "zh"
            else [
                f"1. Begin with `{heading_line}` as the section H2 heading.",
                "2. Follow the page order above; each page needs 4-6 flowing sentences.",
                "3. **Choose format intelligently**: Use paragraphs, bullet points, or tables based on content logic.",
                "   - **Tables**: Only when comparing multiple items (pros/cons, methods, features).",
                "   - **Bullet points (-)**: For steps, checklists, or independent key points.",
                "   - **Paragraphs**: For narrative explanations, derivations, or concept introductions.",
                "4. Image placeholders must follow `[FIG_PAGE_<no>_IDX_<idx>: purpose]` and be interpreted in prose.",
                "5. Wrap formulas with `$`/`$$` and describe each symbol plus its constraints.",
            ]
        )

        directive_notes: List[str] = []
        # 移除强制表格指令，改为在base_requirements中提供智能选择指南
        # if directives.get("use_table"):
        #     directive_notes.append(
        #         "当同页出现多个概念时，以 Markdown 表格比较差异、优缺点。"
        #         if language == "zh"
        #         else "Insert a Markdown table whenever the page contrasts multiple ideas."
        #     )
        formula_mode = directives.get("formula_mode")
        if formula_mode == "light":
            directive_notes.append(
                "公式只保留 1 个关键版本，并用口语解释它解决的问题。"
                if language == "zh"
                else "Only keep one key formula and explain the practical problem it solves."
            )
        elif formula_mode == "extended":
            directive_notes.append(
                "需要写出 2-3 句推理链，说明变量、假设与适用范围。"
                if language == "zh"
                else "Provide 2-3 sentences of reasoning to unpack variables, assumptions, and scope."
            )
        if directives.get("analogy_required"):
            directive_notes.append(
                "每页至少写一句“打个比方/换句话说”，帮助建立直觉。"
                if language == "zh"
                else "Each page should include an analogy or 'in other words' sentence."
            )

        if summary_mode == "insight":
            directive_notes.append(
                "章节末尾写 2-3 句洞察/下一步提示。"
                if language == "zh"
                else "Close with 2-3 sentences of section-level insight or next steps."
            )

        if directive_notes:
            extra_header = "附加风格提示：" if language == "zh" else "Additional nudges:"
            base_requirements.append(extra_header)
            base_requirements.extend(f"- {note}" for note in directive_notes)

        requirements_block = "\n".join(base_requirements)
        section_summary = (section.summary or "").strip() or (
            "暂无概述。" if language == "zh" else "No summary available."
        )

        closing = (
            "请严格按照上述逐页结构输出完整讲解。"
            if language == "zh"
            else "Follow the structure above exactly and cover every listed page."
        )

        return (
            f"{task_intro}\n\n"
            f"{section_label}{section.title}\n"
            f"{summary_label}{section_summary}\n"
            f"{span_label}{page_span}\n\n"
            f"{structure_label}\n"
            f"{heading_line}\n\n"
            f"{page_template}\n"
            f"{subsection_template}\n\n"
            f"{requirements_label}\n"
            f"{requirements_block}\n\n"
            f"{context_label}\n"
            f"{context_text}\n\n"
            f"{closing}"
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
        """判断两个标题是否相似，用于智能合并相关页面"""
        if not left or not right:
            return False
        left_norm = normalize_whitespace(left).lower()
        right_norm = normalize_whitespace(right).lower()
        
        # 完全相同才合并
        if left_norm == right_norm:
            return True
        
        # 检查是否有相同的数字编号前缀（如 "1.1" "2.3.1"）
        left_prefix = left_norm.split()[0] if left_norm.split() else ""
        right_prefix = right_norm.split()[0] if right_norm.split() else ""
        if left_prefix and right_prefix and re.match(r'^\d+(\.\d+)*$', left_prefix):
            if left_prefix == right_prefix:
                return True
        
        # 检查冒号前的关键词是否相同
        left_key = left_norm.split(":")[0].strip()
        right_key = right_norm.split(":")[0].strip()
        if left_key and right_key and len(left_key) > 3 and left_key == right_key:
            return True
        
        # 提高相似度阈值，避免过度合并不相关内容
        return SequenceMatcher(None, left_norm, right_norm).ratio() >= 0.95

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
        """扁平化大纲，只取顶层章节（每个章节内部会逐页讲解）"""
        sections = []
        for child in outline.root.children:
            if child.title.strip():
                sections.append(child)
                # 确保 pages 字段包含所有子章节的页码
                if child.children:
                    all_pages = set(child.pages or [])
                    for subchild in child.children:
                        all_pages.update(subchild.pages or [])
                    child.pages = sorted(all_pages)
        return sections

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

    def _post_process_markdown(
        self, markdown: str, section: OutlineNode, directives: Dict[str, object]
    ) -> str:
        text = (markdown or "").strip()
        if not directives:
            return text
        warnings: List[str] = []
        text = self._ensure_page_headers(text, section, directives, warnings)
        text = self._decorate_page_headers(text, section, directives)
        text = self._ensure_summary_blocks(text, directives, warnings)
        if directives.get("analogy_required"):
            text = self._ensure_analogy(text, directives, warnings)
        if directives.get("blockquote_required"):
            text = self._ensure_blockquote(text, directives, warnings)
        if warnings:
            logger.debug(
                "Post-processed section %s with style validators: %s",
                section.section_id,
                "; ".join(warnings),
            )
        return text

    def _ensure_page_headers(
        self,
        text: str,
        section: OutlineNode,
        directives: Dict[str, object],
        warnings: List[str],
    ) -> str:
        template = directives.get("page_header_template", "### 第{page}页")
        language = directives.get("language", "zh")
        pages = sorted(set(section.pages or []))
        if not pages:
            return text
        placeholder = (
            "> 待补充：补写这一页的细节。"
            if language == "zh"
            else "> TODO: fill in the explanation for this slide."
        )
        updated = text
        for page in pages:
            header = template.format(page=page)
            pattern = rf"^{re.escape(header)}\b"
            if not re.search(pattern, updated, flags=re.MULTILINE):
                updated += f"\n\n{header}\n{placeholder}\n"
                warnings.append(f"missing header {header}")
        return updated

    def _decorate_page_headers(
        self, text: str, section: OutlineNode, directives: Dict[str, object]
    ) -> str:
        language = directives.get("language", "zh")
        if not PAGE_HEADING_PATTERN.search(text):
            return text
        page_titles = self._map_page_outline_titles(section)

        def replace(match: re.Match[str]) -> str:
            page_token = match.group("page_cn") or match.group("page_en")
            if not page_token or not page_token.isdigit():
                return match.group(0)
            page_no = int(page_token)
            level = len(match.group("leading") or "###")
            level = max(2, min(level, 5))
            title = page_titles.get(page_no)
            if not title:
                title = (section.title or "").strip()
            if not title:
                title = f"第{page_no}页" if language == "zh" else f"Page {page_no}"
            badge_label = f"第{page_no}页" if language == "zh" else f"Page {page_no}"
            heading_html = (
                f'<h{level} class="page-heading" data-page="{page_no}">'
                f'<span class="page-heading__title">{escape(title)}</span>'
                f'<span class="page-heading__badge">{escape(badge_label)}</span>'
                f"</h{level}>"
            )
            return heading_html

        return PAGE_HEADING_PATTERN.sub(replace, text)

    def _map_page_outline_titles(self, section: OutlineNode) -> Dict[int, str]:
        page_map: Dict[int, tuple[str, int]] = {}

        def visit(node: OutlineNode, depth: int) -> None:
            title = (node.title or "").strip()
            pages = list(node.pages or [])
            if not pages and node.page_start and node.page_end and node.page_start <= node.page_end:
                pages = list(range(node.page_start, node.page_end + 1))
            if not pages and node.anchors:
                pages = [anchor.page for anchor in node.anchors]
            if not pages:
                pages = self._collect_pages(node)
            pages = list(dict.fromkeys(pages))
            if title and pages:
                for page in pages:
                    current = page_map.get(page)
                    if not current or depth >= current[1]:
                        page_map[page] = (title, depth)
            for child in node.children:
                visit(child, depth + 1)

        visit(section, 1)
        return {page: title for page, (title, _) in page_map.items()}

    def _ensure_summary_blocks(
        self, text: str, directives: Dict[str, object], warnings: List[str]
    ) -> str:
        summary_mode = directives.get("summary_mode")
        if not summary_mode or summary_mode == "none":
            return text
        language = directives.get("language", "zh")
        if summary_mode == "takeaway":
            label = "一句话总结" if language == "zh" else "One-sentence takeaway"
            pattern = label.lower()
            haystack = text.lower()
            if pattern not in haystack:
                addition = (
                    f"> **{label}：** 待补充。\n"
                    if language == "zh"
                    else f"> **{label}:** TODO.\n"
                )
                warnings.append("added takeaway summary")
                return text + "\n\n" + addition
            return text
        if summary_mode == "insight":
            label = "章节洞察" if language == "zh" else "Section insight"
            if label.lower() not in text.lower():
                addition = (
                    f"> **{label}：** 补写 2-3 句串联洞察。\n"
                    if language == "zh"
                    else f"> **{label}:** Add 2-3 sentences summarising the reasoning.\n"
                )
                warnings.append("added insight summary")
                return text + "\n\n" + addition
        return text

    def _ensure_analogy(
        self, text: str, directives: Dict[str, object], warnings: List[str]
    ) -> str:
        language = directives.get("language", "zh")
        haystack = text.lower()
        tokens = (
            ["打个比方", "换句话说", "比喻", "类比"]
            if language == "zh"
            else ["analogy", "metaphor", "imagine"]
        )
        if any(token.lower() in haystack for token in tokens):
            return text
        addition = (
            "> 💡 打个比方：可以把本页内容类比成……（请补写比喻）。"
            if language == "zh"
            else "> 💡 Analogy: Describe how this concept mirrors a familiar scenario."
        )
        warnings.append("analogy placeholder injected")
        return text + "\n\n" + addition + "\n"

    def _ensure_blockquote(
        self, text: str, directives: Dict[str, object], warnings: List[str]
    ) -> str:
        if re.search(r"^\s*>", text, flags=re.MULTILINE):
            return text
        language = directives.get("language", "zh")
        addition = (
            "> 重点提醒：在此写一句承上启下或注意事项。"
            if language == "zh"
            else "> Key reminder: add a bridging or caution sentence here."
        )
        warnings.append("blockquote placeholder injected")
        return text + "\n\n" + addition + "\n"

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
