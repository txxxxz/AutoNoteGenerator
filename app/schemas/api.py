from __future__ import annotations

from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.common import NoteDoc


class FileType(str, Enum):
    pptx = "pptx"
    pdf = "pdf"


class ParseRequest(BaseModel):
    file_id: str
    file_type: FileType
    session_id: str


class LayoutRequest(BaseModel):
    file_id: str
    session_id: str


class OutlineRequest(BaseModel):
    session_id: str


class StyleDetail(str, Enum):
    brief = "brief"
    medium = "medium"
    detailed = "detailed"


class StyleDifficulty(str, Enum):
    simple = "simple"
    explanatory = "explanatory"
    academic = "academic"


class NotesRequest(BaseModel):
    outline_tree_id: str
    style: Dict[str, str]
    session_id: str


class NoteTaskResponse(BaseModel):
    task_id: str


class NoteTaskStatus(BaseModel):
    task_id: str
    session_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: float = 0.0
    detail_level: str
    difficulty: str
    total_sections: int = 0
    current_section: Optional[str] = None
    message: Optional[str] = None
    note_doc_id: Optional[str] = None
    note_doc: Optional[NoteDoc] = None
    error: Optional[str] = None


class CardsRequest(BaseModel):
    note_doc_id: str
    session_id: str


class MockOptions(BaseModel):
    mode: Literal["chapter", "full"] = "full"
    size: int = Field(ge=1, le=100)
    difficulty: Literal["low", "mid", "high"] = "mid"


class MockRequest(BaseModel):
    note_doc_id: str
    options: MockOptions
    session_id: str


class MindmapRequest(BaseModel):
    outline_tree_id: str
    session_id: str


class ExportRequest(BaseModel):
    target_id: str
    type: Literal["notes", "cards", "mock", "mindmap"]
    format: Literal["md", "pdf", "png"]
    session_id: str


class QARequest(BaseModel):
    session_id: str
    question: str
    scope: Literal["notes", "cards", "mock"]


class SessionSummary(BaseModel):
    id: str
    title: str
    status: str
    created_at: str
    file_id: str
    note_doc_ids: List[str] = Field(default_factory=list)
    cards_ids: List[str] = Field(default_factory=list)
    mock_ids: List[str] = Field(default_factory=list)
    mindmap_ids: List[str] = Field(default_factory=list)


class SessionListResponse(BaseModel):
    sessions: List[SessionSummary]


class SessionDetail(SessionSummary):
    available_artifacts: Dict[str, List[str]] = Field(default_factory=dict)
