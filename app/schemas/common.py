"""
Pydantic schemas shared across API boundaries.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class BlockType(str, Enum):
    title = "title"
    text = "text"
    image = "image"
    formula = "formula"
    table = "table"


class SlideBlock(BaseModel):
    id: str
    type: BlockType
    order: int
    bbox: Optional[List[float]] = None
    raw_text: Optional[str] = None
    asset_uri: Optional[str] = None
    latex: Optional[str] = None


class SlidePage(BaseModel):
    page_no: int
    blocks: List[SlideBlock] = Field(default_factory=list)


class ParseResponse(BaseModel):
    doc_meta: dict
    slides: List[SlidePage]


class LayoutElement(BaseModel):
    ref: str
    kind: BlockType
    content: Optional[str] = None
    image_uri: Optional[str] = None
    latex: Optional[str] = None
    caption: Optional[str] = None


class LayoutPage(BaseModel):
    page_no: int
    elements: List[LayoutElement]


class LayoutDoc(BaseModel):
    pages: List[LayoutPage]


class AnchorRef(BaseModel):
    page: int
    ref: str


class OutlineNode(BaseModel):
    section_id: str
    title: str
    summary: str
    anchors: List[AnchorRef] = Field(default_factory=list)
    children: List["OutlineNode"] = Field(default_factory=list)
    level: int = 0

    model_config = {
        "json_encoders": {BlockType: lambda v: v.value},
        "arbitrary_types_allowed": True,
    }


OutlineNode.model_rebuild()


class OutlineTree(BaseModel):
    root: OutlineNode


class NoteFigure(BaseModel):
    image_uri: str
    caption: str


class NoteEquation(BaseModel):
    latex: str
    caption: str


class NoteSection(BaseModel):
    section_id: str
    title: str
    body_md: str
    figures: List[NoteFigure] = Field(default_factory=list)
    equations: List[NoteEquation] = Field(default_factory=list)
    refs: List[str] = Field(default_factory=list)


class NoteDoc(BaseModel):
    style: dict
    toc: List[dict]
    sections: List[NoteSection]


class CardsPayload(BaseModel):
    concept: str
    definition: str
    exam_points: List[str]
    example_q: Optional[dict] = None
    anchors: List[str] = Field(default_factory=list)


class KnowledgeCards(BaseModel):
    cards: List[CardsPayload]


class MockQuestion(BaseModel):
    id: str
    type: str
    stem: str
    options: Optional[List[str]] = None
    answer: str
    explain: Optional[str] = None
    key_points: Optional[List[str]] = None
    refs: List[str] = Field(default_factory=list)


class MockPaper(BaseModel):
    meta: dict
    items: List[MockQuestion]


class MindmapEdge(BaseModel):
    from_: str = Field(..., alias="from")
    to: str
    type: str = "hierarchy"


class MindmapGraph(BaseModel):
    nodes: List[dict]
    edges: List[MindmapEdge]


class ExportResponse(BaseModel):
    download_url: str
    filename: str


class QAResponse(BaseModel):
    answer: str
    refs: List[str] = Field(default_factory=list)
