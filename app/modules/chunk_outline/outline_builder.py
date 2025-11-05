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
            section_title = title_el.content if title_el and title_el.content else f"第{page.page_no}页"
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
