from __future__ import annotations

from typing import List

from app.schemas.common import (
    BlockType,
    LayoutDoc,
    LayoutElement,
    LayoutPage,
    ParseResponse,
    SlideBlock,
)
from app.utils.text import normalize_whitespace, take_sentences


class LayoutBuilder:
    def build(self, parsed: ParseResponse) -> LayoutDoc:
        pages: List[LayoutPage] = []
        for slide in parsed.slides:
            elements: List[LayoutElement] = []
            for block in sorted(slide.blocks, key=lambda b: b.order):
                element = self._block_to_element(slide.page_no, block)
                if element:
                    elements.append(element)
            pages.append(LayoutPage(page_no=slide.page_no, elements=elements))
        return LayoutDoc(pages=pages)

    def _block_to_element(self, page_no: int, block: SlideBlock) -> LayoutElement | None:
        if block.type in {BlockType.title, BlockType.text}:
            content = normalize_whitespace(block.raw_text or "")
            kind = BlockType.title if block.type == BlockType.title else BlockType.text
            return LayoutElement(ref=block.id, kind=kind, content=content)
        if block.type == BlockType.formula:
            caption = take_sentences(block.raw_text or "", 1) or "公式说明"
            return LayoutElement(
                ref=block.id,
                kind=BlockType.formula,
                latex=block.raw_text,
                caption=caption,
            )
        if block.type == BlockType.image:
            caption = f"第{page_no}页插图"
            return LayoutElement(
                ref=block.id,
                kind=BlockType.image,
                image_uri=block.asset_uri,
                caption=caption,
            )
        if block.type == BlockType.table:
            caption = f"第{page_no}页表格"
            return LayoutElement(
                ref=block.id,
                kind=BlockType.table,
                content=block.raw_text,
                caption=caption,
            )
        return None
