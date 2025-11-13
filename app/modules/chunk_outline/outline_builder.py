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
        logger.info(f"📝 Composed text_stream: {len(text_stream)} chars from {len(layout_doc.pages)} pages")
        if not text_stream.strip():
            logger.warning("❌ text_stream is empty, cannot generate outline")
            return None
        markdown = self._generate_outline_markdown(title, text_stream)
        logger.info(f"📋 LLM generated markdown: {len(markdown)} chars")
        if not markdown:
            logger.warning("❌ LLM returned empty markdown")
            return None
        parsed = parse_outline_markdown(markdown)
        if not parsed:
            logger.warning("❌ Failed to parse markdown into outline structure")
            return None
        children = self._headings_to_nodes(parsed, layout_doc)
        if not children:
            logger.warning("❌ No outline nodes generated from markdown")
            return None
        # 质量检查：至少要有2个一级章节，否则认为质量太差
        level_2_chapters = [c for c in children if c.level == 2]
        if len(level_2_chapters) < 2:
            logger.warning(f"❌ Outline quality too low: only {len(level_2_chapters)} top-level chapters, expected at least 2")
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
            logger.info(f"✂️ Clipping text_stream from {len(clipped_stream)} to {max_chars} chars")
            clipped_stream = clipped_stream[:max_chars] + "\n...[内容截断，后续页略]..."
        else:
            logger.info(f"📄 Using full text_stream: {len(clipped_stream)} chars (under {max_chars} limit)")

        system_prompt = (
            "你是一名课程设计专家，负责让大学课程材料转化为有逻辑、可教学的知识大纲。"
            "你的目标是帮助学生建立语义结构，而不是按页罗列摘要。"
        )

        user_prompt = (
            "请通读以下课件文本，生成**自然结构的 Markdown 大纲**。\n\n"
            "### 强制要求\n"
            "1. 课件内容使用 `<<PAGE n>>` 标识页码，请根据这些标记推断范围；\n"
            "2. 顶层标题必须以 `##` 开始，最多细化到 `#####`，禁止使用 `#`；\n"
            "3. 每个标题后追加 `(p.x–y)` 或 `(p.x)`，表示该部分覆盖的 PDF 页码范围；\n"
            "4. 依据语义/逻辑组织章节，而非逐页罗列；\n"
            "5. 在每个标题正下方写一行 `> Summary:`，概述 1–2 句学习目标；\n"
            "6. **必须生成至少 3 个一级章节（##），最多 8 个**，即使内容较少也要合理拆分主题；\n"
            "7. 每个一级章节至少包含 1-2 个子章节（###），展现内容的层次结构；\n"
            "8. 大纲必须涵盖所有重要页面，不要遗漏关键内容；\n"
            "9. 输出纯 Markdown，不要额外解释或注释。\n\n"
            "### 示例结构\n"
            "```\n"
            "## 算法 1：线性回归 (p.3–10)\n"
            "> Summary: 给出线性回归的基本假设、损失函数与直觉。 \n"
            "### 概念与直觉 (p.3–4)\n"
            "> Summary: 使用数据点和超平面关系介绍问题。 \n"
            "#### 推导流程 (p.4–6)\n"
            "> Summary: 详细说明最小二乘推导、矩阵形式与几何解释。 \n"
            "##### 应用示例 (p.7)\n"
            "> Summary: 将模型套用到房价预测。 \n"
            "```\n\n"
            f"### 输入\n课程主题：{title}\n\n课件内容（含页码标记）：\n{clipped_stream}\n\n"
            "请输出满足上述要求的 Markdown 大纲："
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
            pages = heading.pages or [anchor.page for anchor in anchors]
            page_start = min(pages) if pages else None
            page_end = max(pages) if pages else None
            node = OutlineNode(
                section_id=new_id("s"),
                title=heading.title,
                summary=heading.summary,
                anchors=anchors,
                level=heading.level,
                pages=pages,
                page_start=page_start,
                page_end=page_end,
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
                    pages=[page.page_no],
                    page_start=page.page_no,
                    page_end=page.page_no,
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
