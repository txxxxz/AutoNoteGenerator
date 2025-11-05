from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List
import re

import pdfplumber
from pydantic import ValidationError

from app.schemas.common import BlockType, ParseResponse, SlideBlock, SlidePage
from app.storage import assets
from app.utils.identifiers import new_id
from app.utils.logger import logger

try:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
except ImportError as exc:  # pragma: no cover - dependency optional during tests
    Presentation = None
    MSO_SHAPE_TYPE = None
    logger.warning("python-pptx unavailable: PPTX parsing disabled (%s)", exc)


EMU_PER_INCH = 914400


def _emu_to_points(value: int) -> float:
    return round((value / EMU_PER_INCH) * 72.0, 3)


@dataclass(slots=True)
class ParseResult:
    response: ParseResponse


class SlideParser:
    def parse(self, file_path: Path, file_type: str, session_id: str) -> ParseResponse:
        if file_type == "pdf":
            slides = self._parse_pdf(file_path)
        elif file_type == "pptx":
            slides = self._parse_pptx(file_path, session_id)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        doc_meta = {"title": file_path.stem, "pages": len(slides)}
        try:
            return ParseResponse(doc_meta=doc_meta, slides=slides)
        except ValidationError as exc:  # pragma: no cover - schema guard
            logger.error("Parse response failed validation: %s", exc)
            raise

    def _parse_pdf(self, file_path: Path) -> List[SlidePage]:
        results: List[SlidePage] = []
        with pdfplumber.open(str(file_path)) as pdf:
            if not pdf.pages:
                raise ValueError("PDF 未包含任何页面，无法解析")
            for page in pdf.pages:
                blocks: List[SlideBlock] = []
                words = page.extract_words(
                    keep_blank_chars=False, use_text_flow=True, extra_attrs=["size"]
                )
                order = 0
                text_buffer: List[str] = []
                bbox_buffer: List[List[float]] = []
                for word in words:
                    text_buffer.append(word["text"])
                    bbox_buffer.append(
                        [
                            float(word["x0"]),
                            float(word["top"]),
                            float(word["x1"] - word["x0"]),
                            float(word["bottom"] - word["top"]),
                        ]
                    )
                if text_buffer:
                    merged = " ".join(text_buffer).strip()
                    if merged:
                        block_type = (
                            BlockType.formula if _likely_formula(merged) else BlockType.text
                        )
                        blocks.append(
                            SlideBlock(
                                id=new_id("b"),
                                type=block_type,
                                order=order,
                                raw_text=merged,
                                bbox=[float(page.width), float(page.height), 0.0, 0.0],
                            )
                        )
                        order += 1
                results.append(SlidePage(page_no=page.page_number, blocks=blocks))
        return results

    def _parse_pptx(self, file_path: Path, session_id: str) -> List[SlidePage]:
        if Presentation is None:
            raise RuntimeError(
                "python-pptx is required to parse PPTX files. Install python-pptx."
            )
        pres = Presentation(str(file_path))
        slides: List[SlidePage] = []
        for idx, slide in enumerate(pres.slides, start=1):
            blocks: List[SlideBlock] = []
            order = 0
            for shape in slide.shapes:
                bbox = [
                    _emu_to_points(shape.left),
                    _emu_to_points(shape.top),
                    _emu_to_points(shape.width),
                    _emu_to_points(shape.height),
                ]
                if shape.has_text_frame and shape.text.strip():
                    text = shape.text.strip()
                    if order == 0:
                        block_type = BlockType.title
                    elif _likely_formula(text):
                        block_type = BlockType.formula
                    else:
                        block_type = BlockType.text
                    blocks.append(
                        SlideBlock(
                            id=new_id("b"),
                            type=block_type,
                            order=order,
                            raw_text=text,
                            bbox=bbox,
                        )
                    )
                    order += 1
                elif MSO_SHAPE_TYPE and shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    image = shape.image
                    stream = io.BytesIO(image.blob)
                    rel_name = f"{new_id('img')}.{image.ext or 'png'}"
                    asset_uri = assets.write_asset(session_id, rel_name, stream.read())
                    blocks.append(
                        SlideBlock(
                            id=new_id("b"),
                            type=BlockType.image,
                            order=order,
                            bbox=bbox,
                            asset_uri=asset_uri,
                        )
                    )
                    order += 1
            slides.append(SlidePage(page_no=idx, blocks=blocks))
        return slides


FORMULA_PATTERN = re.compile(r"(\\[a-zA-Z]+|[=±×÷∑∫√^_])")


def _likely_formula(text: str) -> bool:
    return bool(FORMULA_PATTERN.search(text))
