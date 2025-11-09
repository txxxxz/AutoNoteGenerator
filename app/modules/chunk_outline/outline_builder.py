from __future__ import annotations

from typing import List

from app.schemas.common import AnchorRef, LayoutDoc, OutlineNode, OutlineTree
from app.utils.identifiers import new_id
from app.utils.text import normalize_whitespace, take_sentences


class OutlineBuilder:
    def build(self, layout_doc: LayoutDoc, title: str) -> OutlineTree:
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
        return OutlineTree(root=root)

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
