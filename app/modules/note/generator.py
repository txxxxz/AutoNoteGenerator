from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_text_splitters import TokenTextSplitter
from langchain_core.documents import Document

from app.modules.note.llm_client import get_llm
from app.modules.note.style_policies import build_style_instructions
from app.schemas.common import (
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
        total_sections = len(outline.root.children)
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
        for index, section in enumerate(outline.root.children, start=1):
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
        toc = [{"section_id": section.section_id, "title": section.title} for section in outline.root.children]
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
        return (
            f"章节标题: {section.title}\n"
            f"大纲摘要: {section.summary}\n"
            f"风格指令:\n{style_instructions}\n\n"
            f"上下文材料:\n{context_text}\n\n"
            "请基于以上信息，生成**严格符合以下格式和内容要求**的 Markdown 内容：\n"
            "### 格式要求\n"
            "1. **标题层级**：仅使用二级标题（##）和三级标题（###），禁止一级标题（#）。\n"
            "   - 二级标题用于核心模块（如“## 核心概念”“## 推导过程”）。\n"
            "   - 三级标题用于子模块（如“### 定义1”“### 性质2”）。\n"
            "2. **列表格式**：所有列表必须以短横线（-）开头，禁止星号（*）或数字序号。\n"
            "3. **公式格式**：所有数学公式必须用 $$ 包裹（块级公式），如：$$L = -\sum p_j \log(q_j)$$。\n"
        "   - 强制要求：公式必须完整闭合（开头和结尾都是 $$），禁止单独出现 $ 或未闭合的 $$。\n"
        "   - 禁止公式内换行，确保 $$ 之间为完整公式（避免拆分到两行）。\n"
            "4. **段落分隔**：不同模块之间用**一个空行**分隔，禁止连续空行。\n"
            "### 内容要求\n"
            "1. **严格过滤无关信息**：\n"
            "   - 剔除所有页码标记（如 `6/78` `10/78` 等格式）。\n"
            "   - 剔除重复文本、无意义标记（如 `Output not zero-centered`）。\n"
            "   - 禁止直接复制上下文的原始段落，需用自己的语言重新组织。\n"
            "2. **必含结构**：\n"
            "   - ## 核心概念与解释\n"
            "   - ## 关键结论或定理\n"
            "   - ## 示例与推导（若上下文支持则包含）\n"
            "   - ## 小结\n"
            "3. **避免添加**：超出上下文的内容（如需补充请标注“扩展说明”）、冗余格式标记。\n"
            "请严格遵循以上要求，输出仅保留与章节主题强相关的核心信息，格式统一、内容精炼。"
        )

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
