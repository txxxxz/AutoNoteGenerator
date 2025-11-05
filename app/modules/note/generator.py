from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

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
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

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
    ) -> NoteDoc:
        style_instructions = build_style_instructions(detail_level, difficulty)
        docs = self._build_documents(layout_doc)
        vector_store = load_or_create(session_id, docs)
        llm = get_llm(temperature=0.2)
        system_prompt = (
            "You are StudyCompanion, tasked with generating structured course notes. "
            "You must adhere to the provided outline, respect the style instructions, "
            "and reference the supplied context. Output in GitHub-flavoured Markdown."
        )
        sections: List[NoteSection] = []
        figures_by_page, equations_by_page = self._collect_assets(layout_doc)

        for section in outline.root.children:
            context_text = self._retrieve_context(vector_store, section, docs)
            prompt = self._build_prompt(section, style_instructions, context_text)
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
            sections.append(
                NoteSection(
                    section_id=section.section_id,
                    title=section.title,
                    body_md=markdown.strip(),
                    figures=figures,
                    equations=equations,
                    refs=[f"anchor:{section.section_id}@page{a.page}#{a.ref}" for a in section.anchors],
                )
            )
        save(session_id, vector_store)
        toc = [{"section_id": section.section_id, "title": section.title} for section in outline.root.children]
        return NoteDoc(
            style={"detail_level": detail_level, "difficulty": difficulty},
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
            "请基于以上信息，生成结构化 Markdown 内容，包含：\n"
            "1. 核心概念与解释\n"
            "2. 关键结论或定理\n"
            "3. 必要示例或推导（若指令允许）\n"
            "4. 小结或适用条件（若指令要求）\n"
            "避免添加超出上下文的内容，如需补充，请明确标注为“扩展说明”。"
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
