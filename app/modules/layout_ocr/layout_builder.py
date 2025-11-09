from __future__ import annotations

from typing import List, Optional

from app.schemas.common import (
    BlockType,
    LayoutDoc,
    LayoutElement,
    LayoutPage,
    ParseResponse,
    SlideBlock,
    SlidePage,
)
from app.utils.text import normalize_whitespace, take_sentences


class LayoutBuilder:
    def build(self, parsed: ParseResponse) -> LayoutDoc:
        pages: List[LayoutPage] = []
        for slide in parsed.slides:
            page_headline = self._infer_page_headline(slide)
            elements: List[LayoutElement] = []
            for block in sorted(slide.blocks, key=lambda b: b.order):
                element = self._block_to_element(slide.page_no, page_headline, block)
                if element:
                    elements.append(element)
            pages.append(LayoutPage(page_no=slide.page_no, elements=elements))
        return LayoutDoc(pages=pages)

    def _block_to_element(
        self,
        page_no: int,
        page_headline: str,
        block: SlideBlock,
    ) -> LayoutElement | None:
        if block.type in {BlockType.title, BlockType.text}:
            content = normalize_whitespace(block.raw_text or "")
            kind = BlockType.title if block.type == BlockType.title else BlockType.text
            return LayoutElement(ref=block.id, kind=kind, content=content)
        if block.type == BlockType.formula:
            caption = self._semantic_caption(
                block.raw_text,
                page_headline,
                page_no,
                fallback="关键公式",
            )
            return LayoutElement(
                ref=block.id,
                kind=BlockType.formula,
                latex=block.raw_text,
                caption=caption,
            )
        if block.type == BlockType.image:
            caption = self._semantic_caption(
                block.raw_text,
                page_headline,
                page_no,
                fallback="插图",
            )
            return LayoutElement(
                ref=block.id,
                kind=BlockType.image,
                image_uri=block.asset_uri,
                caption=caption,
            )
        if block.type == BlockType.table:
            caption = self._semantic_caption(
                block.raw_text,
                page_headline,
                page_no,
                fallback="数据表",
            )
            return LayoutElement(
                ref=block.id,
                kind=BlockType.table,
                content=block.raw_text,
                caption=caption,
            )
        return None

    def _infer_page_headline(self, slide: SlidePage) -> str:
        title_block = next(
            (block for block in slide.blocks if block.type == BlockType.title and block.raw_text),
            None,
        )
        if title_block:
            title = normalize_whitespace(title_block.raw_text or "")
            if title:
                return title[:60]
        for block in slide.blocks:
            snippet = take_sentences(block.raw_text or "", 1)
            if snippet:
                return snippet[:60]
        return f"页面{slide.page_no}主题"

    def _semantic_caption(
        self,
        raw_text: Optional[str],
        page_headline: str,
        page_no: int,
        fallback: str,
    ) -> str:
        normalized = normalize_whitespace(raw_text or "")
        snippet = take_sentences(normalized, 1) or normalized
        if snippet:
            return snippet[:80]
        if page_headline:
            return f"{page_headline} · {fallback}"
        return f"{fallback}（页面{page_no}）"
