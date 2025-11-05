"""
Vector store adapter built on FAISS with LangChain abstractions.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.modules.note.llm_client import get_embedding_model

VECTOR_ROOT = Path(os.getenv("SC_VECTOR_ROOT", ".vectors"))
VECTOR_ROOT.mkdir(exist_ok=True)


def _session_path(session_id: str) -> Path:
    return VECTOR_ROOT / f"{session_id}.faiss"


def load_or_create(session_id: str, docs: Optional[Iterable[Document]] = None) -> FAISS:
    path = _session_path(session_id)
    if path.exists() and (path.with_suffix(".pkl")).exists():
        return FAISS.load_local(
            str(path),
            get_embedding_model(),
            allow_dangerous_deserialization=True,
        )
    if docs is None:
        raise ValueError("docs required for new vector store")
    store = FAISS.from_documents(docs, embedding=get_embedding_model())
    store.save_local(str(path))
    return store


def save(session_id: str, store: FAISS) -> None:
    path = _session_path(session_id)
    store.save_local(str(path))
