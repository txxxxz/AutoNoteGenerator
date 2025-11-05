from __future__ import annotations

from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.vectorstores import FAISS

from app.modules.note.llm_client import get_embedding_model, get_llm
from app.schemas.common import KnowledgeCards, MockPaper, NoteDoc, QAResponse


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
        texts, refs = self._collect_texts(scope, note_doc, cards, mock)
        if not texts:
            return QAResponse(answer="当前范围内暂无内容可供检索。", refs=[])
        store = FAISS.from_texts(texts, get_embedding_model())
        docs = store.similarity_search(question, k=3)
        context = "\n\n".join(doc.page_content for doc in docs)
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

    def _collect_texts(
        self,
        scope: str,
        note_doc: NoteDoc | None,
        cards: KnowledgeCards | None,
        mock: MockPaper | None,
    ) -> tuple[List[str], List[str]]:
        texts: List[str] = []
        refs: List[str] = []
        if scope == "notes" and note_doc:
            for section in note_doc.sections:
                texts.append(f"{section.title}\n{section.body_md}")
                refs.extend(section.refs)
        if scope == "cards" and cards:
            for card in cards.cards:
                exam_points = "; ".join(card.exam_points)
                card_text = f"{card.concept}\n定义: {card.definition}\n考点: {exam_points}"
                texts.append(card_text)
                refs.extend(card.anchors)
        if scope == "mock" and mock:
            for item in mock.items:
                item_text = f"{item.stem}\n答案: {item.answer}\n解析: {item.explain or ''}"
                texts.append(item_text)
                refs.extend(item.refs)
        return texts, refs
