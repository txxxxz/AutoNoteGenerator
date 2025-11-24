from __future__ import annotations

from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.vectorstores import FAISS

from app.modules.note.llm_client import get_llm
from app.schemas.common import KnowledgeCards, MockPaper, NoteDoc, QAResponse
from app.storage.vector_store import load_existing, load_or_create
from app.utils.logger import logger


class QAService:
    def __init__(self, session_id: str):
        self.session_id = session_id

    def ask(
        self,
        question: str,
        scope: str,
        note_doc: NoteDoc | None,
        cards: KnowledgeCards | None,
        mock: MockPaper | None,
    ) -> QAResponse:
        retrieval = self._retrieve_context(scope, question, note_doc, cards, mock)
        if not retrieval:
            return QAResponse(answer="当前范围内暂无内容可供检索。", refs=[])
        context, refs = retrieval
        llm = get_llm(temperature=0.1)
        system_prompt = (
            "You are an assistant answering questions strictly based on provided study materials. "
            "Cite relevant sections when possible."
        )
        prompt = f"Question: {question}\n\nContext:\n{context}"
        response = llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]
        )
        answer = getattr(response, "content", str(response))
        return QAResponse(answer=answer, refs=refs[:3])

    def _retrieve_context(
        self,
        scope: str,
        question: str,
        note_doc: NoteDoc | None,
        cards: KnowledgeCards | None,
        mock: MockPaper | None,
    ) -> Optional[tuple[str, List[str]]]:
        store = self._get_or_build_store(scope, note_doc, cards, mock)
        if store is None:
            return None
        docs = store.similarity_search(question, k=4)
        if not docs:
            return None
        context_parts = []
        for idx, doc in enumerate(docs, start=1):
            title = doc.metadata.get("title") or doc.metadata.get("concept") or doc.metadata.get("stem")
            header = f"[材料 {idx}] {title}" if title else f"[材料 {idx}]"
            context_parts.append(f"{header}\n{doc.page_content.strip()}")
        refs = self._collect_refs(docs)
        return "\n\n".join(context_parts), refs

    def _collect_refs(self, docs: List[Document]) -> List[str]:
        seen: set[str] = set()
        refs: List[str] = []
        for doc in docs:
            metadata_refs = doc.metadata.get("refs") or []
            for ref in metadata_refs:
                if ref and ref not in seen:
                    seen.add(ref)
                    refs.append(ref)
        return refs

    def _get_or_build_store(
        self,
        scope: str,
        note_doc: NoteDoc | None,
        cards: KnowledgeCards | None,
        mock: MockPaper | None,
    ) -> Optional[FAISS]:
        normalized_scope = scope or "notes"
        store = load_existing(self.session_id, normalized_scope)
        if store:
            return store
        docs: List[Document] = []
        if scope == "notes" and note_doc:
            docs = self._build_note_documents(note_doc)
        elif scope == "cards" and cards:
            docs = self._build_card_documents(cards)
        elif scope == "mock" and mock:
            docs = self._build_mock_documents(mock)
        if not docs:
            logger.info("scope=%s 缺少文档，无法构建向量索引", scope)
            return None
        logger.info("scope=%s 缺少向量索引，正在构建...", scope)
        return load_or_create(
            self.session_id,
            docs,
            rebuild=True,
            scope=normalized_scope,
        )

    def _build_note_documents(self, note_doc: NoteDoc) -> List[Document]:
        documents: List[Document] = []
        for section in note_doc.sections:
            metadata = {
                "section_id": section.section_id,
                "title": section.title,
                "refs": section.refs or [],
                "source": "notes",
            }
            content = f"{section.title}\n\n{section.body_md}"
            documents.append(Document(page_content=content, metadata=metadata))
        return documents

    def _build_card_documents(self, cards: KnowledgeCards) -> List[Document]:
        documents: List[Document] = []
        for card in cards.cards:
            metadata = {
                "concept": card.concept,
                "refs": card.anchors or [],
                "source": "cards",
            }
            exam_points = "; ".join(card.exam_points)
            payload = [
                f"概念: {card.concept}",
                f"定义: {card.definition}",
            ]
            if exam_points:
                payload.append(f"考点: {exam_points}")
            if card.example_q:
                payload.append(f"示例: {card.example_q.get('stem')}")
            documents.append(
                Document(
                    page_content="\n".join(payload),
                    metadata=metadata,
                )
            )
        return documents

    def _build_mock_documents(self, mock: MockPaper) -> List[Document]:
        documents: List[Document] = []
        for item in mock.items:
            metadata = {
                "stem": item.stem[:48],
                "refs": item.refs or [],
                "source": "mock",
            }
            payload = [f"题干: {item.stem}"]
            if item.options:
                payload.append("选项: " + " | ".join(item.options))
            payload.append(f"答案: {item.answer}")
            if item.explain:
                payload.append(f"解析: {item.explain}")
            if item.key_points:
                payload.append("得分点: " + "; ".join(item.key_points))
            documents.append(
                Document(
                    page_content="\n".join(payload),
                    metadata=metadata,
                )
            )
        return documents
