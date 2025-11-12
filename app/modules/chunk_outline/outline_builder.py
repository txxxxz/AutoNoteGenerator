from __future__ import annotations

from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.modules.note.llm_client import get_llm
from app.schemas.common import AnchorRef, LayoutDoc, OutlineNode, OutlineTree
from app.utils.identifiers import new_id
from app.utils.logger import logger
from app.utils.outline import ParsedHeading, parse_outline_markdown, render_outline_markdown
from app.utils.text import normalize_whitespace, take_sentences


class OutlineBuilder:
    def build(self, layout_doc: LayoutDoc, title: str) -> OutlineTree:
        natural_outline = self._build_semantic_outline(layout_doc, title)
        if natural_outline:
            return natural_outline
        logger.warning("自然结构大纲生成失败，回退到页级结构。")
        return self._build_page_outline(layout_doc, title)

    def _build_semantic_outline(self, layout_doc: LayoutDoc, title: str) -> Optional[OutlineTree]:
        text_stream = self._compose_text_stream(layout_doc)
        if not text_stream.strip():
            return None
        markdown = self._generate_outline_markdown(title, text_stream)
        if not markdown:
            return None
        parsed = parse_outline_markdown(markdown)
        if not parsed:
            return None
        children = self._headings_to_nodes(parsed, layout_doc)
        if not children:
            return None
        root_summary = "自然结构大纲涵盖：" + "；".join(child.title for child in children[:5])
        root = OutlineNode(
            section_id=new_id("root"),
            title=title,
            summary=root_summary,
            anchors=[],
            level=0,
            children=children,
        )
        return OutlineTree(root=root, markdown=markdown)

    def _generate_outline_markdown(self, title: str, text_stream: str) -> str:
        llm = get_llm(temperature=0.1)
        clipped_stream = text_stream
        max_chars = 18000
        if len(clipped_stream) > max_chars:
            clipped_stream = clipped_stream[:max_chars] + "\n...[内容截断，后续页略]..."
        system_prompt = (
            "You are a teaching assistant who converts slide transcripts into a natural, "
            "semantically grouped outline for a university course."
        )
        user_prompt = (
            "请根据以下课件文本流，生成一个最多 5 级的 Markdown 章节结构，规则：\n"
            "1. 用 # 至 ##### 表示层级。\n"
            "2. 每个标题行末尾添加 (pages: x-y) 表示涵盖的页码，可用逗号分隔多个区间。\n"
            "3. 在标题下一行写 `> Summary: ...` 概括该节学习目标（1-2 句）。\n"
            "4. 章节应体现知识逻辑而非页码顺序，可合并多页，必要时补写过渡语。\n"
            "5. 不要回显原文或列出逐页要点，输出仅包含 Markdown 大纲。\n\n"
            f"课程标题：{title}\n"
            "课件文本流：\n"
            f"{clipped_stream}"
        )
        try:
            response = llm.invoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
            )
            markdown = getattr(response, "content", str(response)).strip()
            return markdown
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("调用 LLM 生成大纲失败: %s", exc)
            return ""

    def _compose_text_stream(self, layout_doc: LayoutDoc) -> str:
        segments: List[str] = []
        for page in layout_doc.pages:
            lines = [f"<<PAGE {page.page_no}>>"]
            for element in page.elements:
                if element.kind.value == "title":
                    if element.content:
                        lines.append(f"Title: {element.content}")
                elif element.kind.value == "text":
                    if element.content:
                        lines.append(f"Text: {element.content}")
                elif element.kind.value == "image":
                    label = element.caption or "插图"
                    lines.append(f"Image: {label}")
                elif element.kind.value == "formula":
                    latex = element.latex or ""
                    caption = element.caption or ""
                    lines.append(f"Formula: {latex} {caption}")
                elif element.kind.value == "table":
                    caption = element.caption or (element.content or "数据表")
                    lines.append(f"Table: {caption}")
            segments.append("\n".join(lines))
        return "\n\n".join(segments)

    def _headings_to_nodes(
        self,
        headings: List[ParsedHeading],
        layout_doc: LayoutDoc,
    ) -> List[OutlineNode]:
        root_children: List[OutlineNode] = []
        stack: List[OutlineNode] = []
        for heading in headings:
            anchors = self._resolve_anchors(heading.pages, layout_doc)
            node = OutlineNode(
                section_id=new_id("s"),
                title=heading.title,
                summary=heading.summary,
                anchors=anchors,
                level=heading.level,
                children=[],
            )
            while stack and stack[-1].level >= node.level:
                stack.pop()
            if stack:
                stack[-1].children.append(node)
            else:
                root_children.append(node)
            stack.append(node)
        return root_children

    def _resolve_anchors(self, pages: List[int], layout_doc: LayoutDoc) -> List[AnchorRef]:
        if not pages:
            return []
        anchors: List[AnchorRef] = []
        for page_no in pages:
            page = next((p for p in layout_doc.pages if p.page_no == page_no), None)
            if not page:
                continue
            ref = page.elements[0].ref if page.elements else f"page-{page_no}"
            anchors.append(AnchorRef(page=page_no, ref=ref))
            if len(anchors) >= 6:
                break
        return anchors

    def _build_page_outline(self, layout_doc: LayoutDoc, title: str) -> OutlineTree:
        children: List[OutlineNode] = []
        for page in layout_doc.pages:
            title_el = next((e for e in page.elements if e.kind.value == "title"), None)
            content_elements = [e for e in page.elements if e is not title_el]
            section_title = self._resolve_section_title(page, title_el, content_elements)
            full_text = " ".join(
                normalize_whitespace(e.content or "") for e in content_elements if e.content
            )
            summary = take_sentences(full_text, 2)[:240] or "本页内容概述为空。"
            section_id = new_id("s")
            anchors = [AnchorRef(page=page.page_no, ref=title_el.ref if title_el else e.ref) for e in content_elements[:1] or page.elements[:1]]
            children.append(
                OutlineNode(
                    section_id=section_id,
                    title=section_title,
                    summary=summary,
                    anchors=anchors,
                    level=1,
                    children=[],
                )
            )
        root_summary = (
            "本课程包含以下章节: " + "；".join(child.title for child in children[:6])
            if children
            else "未检测到有效章节。"
        )
        root = OutlineNode(
            section_id=new_id("root"),
            title=title,
            summary=root_summary,
            anchors=[],
            level=0,
            children=children,
        )
        markdown = render_outline_markdown(root)
        return OutlineTree(root=root, markdown=markdown)

    def _resolve_section_title(self, page, title_el, content_elements) -> str:
        if title_el and title_el.content:
            return normalize_whitespace(title_el.content)[:60]
        for element in content_elements:
            candidate = take_sentences(element.content or "", 1)
            if candidate:
                return candidate[:60]
        for element in page.elements:
            if element.content:
                candidate = take_sentences(element.content, 1)
                if candidate:
                    return candidate[:60]
        return f"页面{page.page_no}主题"
