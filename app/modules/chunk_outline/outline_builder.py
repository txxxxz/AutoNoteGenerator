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
        """主入口：先尝试自然结构大纲，失败则回退到页级大纲"""
        natural_outline = self._build_semantic_outline(layout_doc, title)
        if natural_outline:
            return natural_outline
        logger.warning("自然结构大纲生成失败，回退到页级结构。")
        return self._build_page_outline(layout_doc, title)

    # ==================== 🧩 阶段一：自然结构大纲 ====================

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
        """调用 LLM 生成自然结构教学大纲（Markdown）"""
        llm = get_llm(temperature=0.1)
        clipped_stream = text_stream
        max_chars = 18000
        if len(clipped_stream) > max_chars:
            clipped_stream = clipped_stream[:max_chars] + "\n...[内容截断，后续页略]..."

        system_prompt = (
            "你是一名课程设计专家，负责将课堂PPT内容重组为符合学习逻辑的知识结构大纲。"
            "你的目标是帮助学生理解复杂知识，而不是机械地摘要或按页罗列。"
        )

        user_prompt = (
            "请根据以下课件文字，输出一个**自然结构的教学大纲**。\n\n"
            "### 任务目标\n"
            "1. 按**知识逻辑**组织章节，而不是按页码顺序。\n"
            "2. 每个章节标题要使用自然语言短句，例如“为什么需要粒子滤波”或“改进重采样的思路”。\n"
            "3. 大纲最多四级标题（# 至 ####），层级要体现从概念→方法→问题→解决的递进。\n"
            "4. 每个一级或二级标题下，用 `> Summary:` 写1–2句学习目标。\n"
            "5. 可以在标题末尾加上 `(pages: x–y)` 表示主要来源页码，但页码只作参考。\n"
            "6. 章节总数建议在 3–8 个之间，每个一级章节下不超过三层子标题。\n"
            "7. 输出纯 Markdown，不要解释或前言。\n\n"
            "### 输出示例\n"
            "```\n"
            "# 粒子滤波的基本思想 (pages: 2–5)\n"
            "> Summary: 理解如何通过采样近似概率分布，并区分预测与更新两步。\n\n"
            "## 状态估计的核心问题\n"
            "> Summary: 说明为什么传统卡尔曼滤波不适用于非线性系统。\n\n"
            "### 预测步骤\n"
            "- 根据运动模型生成粒子，模拟系统动态。\n\n"
            "### 更新步骤\n"
            "- 利用观测模型修正权重，实现后验估计。\n\n"
            "# 实际问题与改进策略 (pages: 8–14)\n"
            "> Summary: 探讨粒子退化、粒子饥饿等常见问题及其解决方案。\n"
            "```\n\n"
            f"### 输入\n课程主题：{title}\n\n课件内容：\n{text_stream}\n\n"
            "请输出重组后的教学大纲（纯 Markdown）："
        )

        try:
            response = llm.invoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
            )
            markdown = getattr(response, "content", str(response)).strip()
            return markdown
        except Exception as exc:
            logger.warning("调用 LLM 生成自然结构大纲失败: %s", exc)
            return ""

    def _compose_text_stream(self, layout_doc: LayoutDoc) -> str:
        """将课件的所有页合并成语义流文本"""
        segments: List[str] = []
        for page in layout_doc.pages:
            lines = [f"<<PAGE {page.page_no}>>"]
            for element in page.elements:
                if element.kind.value == "title" and element.content:
                    lines.append(f"Title: {element.content}")
                elif element.kind.value == "text" and element.content:
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
        """解析 Markdown 结构为树节点"""
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
        """根据页码找到大纲锚点"""
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

    # ==================== 🧩 阶段二：页级回退 ====================

    def _build_page_outline(self, layout_doc: LayoutDoc, title: str) -> OutlineTree:
        """回退方案：每页一个章节"""
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
            anchors = [
                AnchorRef(page=page.page_no, ref=title_el.ref if title_el else e.ref)
                for e in content_elements[:1] or page.elements[:1]
            ]
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
        """回退模式下确定页面标题"""
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
