from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List

from app.schemas.common import OutlineNode


def render_outline_markdown(
    root: OutlineNode,
    include_summary: bool = True,
    max_heading_level: int = 5,
) -> str:
    lines: List[str] = []

    def visit(node: OutlineNode, depth: int) -> None:
        heading_level = max(1, min(depth, max_heading_level))
        prefix = "#" * heading_level
        title = (node.title or "").strip() or f"Untitled Section {node.section_id}"
        lines.append(f"{prefix} {title}")
        summary = (node.summary or "").strip()
        if include_summary and summary:
            lines.append(f"> {summary}")
        lines.append("")
        next_depth = min(heading_level + 1, max_heading_level)
        for child in node.children:
            visit(child, next_depth)

    visit(root, 1)
    return "\n".join(lines).strip()


@dataclass
class ParsedHeading:
    level: int
    title: str
    summary: str
    pages: List[int]


HEADING_RE = re.compile(r"^(#{1,5})\s+(.*)$")
PAGES_RE = re.compile(r"\((?:pages?|p)\.?\s*[:：]?\s*([^)]+)\)\s*$", re.IGNORECASE)
SUMMARY_RE = re.compile(r"^>\s*(.+)$")


def parse_outline_markdown(markdown: str, max_heading_level: int = 5) -> List[ParsedHeading]:
    headings: List[ParsedHeading] = []
    current: dict | None = None
    summary_buffer: List[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        heading_match = HEADING_RE.match(line)
        if heading_match:
            if current:
                current["summary"] = _summarize(summary_buffer, current["title"])
                headings.append(
                    ParsedHeading(
                        level=current["level"],
                        title=current["title"],
                        summary=current["summary"],
                        pages=current["pages"],
                    )
                )
                summary_buffer = []
            level = min(len(heading_match.group(1)), max_heading_level)
            title_raw = heading_match.group(2).strip()
            title, pages = _strip_pages_metadata(title_raw)
            current = {"level": level, "title": title or "未命名章节", "pages": pages or []}
            continue
        summary_match = SUMMARY_RE.match(line)
        if summary_match:
            summary_buffer.append(summary_match.group(1).strip())
    if current:
        current["summary"] = _summarize(summary_buffer, current["title"])
        headings.append(
            ParsedHeading(
                level=current["level"],
                title=current["title"],
                summary=current["summary"],
                pages=current["pages"],
            )
        )
    return headings


def _strip_pages_metadata(text: str) -> tuple[str, List[int]]:
    match = PAGES_RE.search(text)
    if not match:
        return text, []
    pages_spec = match.group(1)
    title = PAGES_RE.sub("", text).strip()
    pages = _expand_page_spec(pages_spec)
    return title, pages


def _expand_page_spec(spec: str) -> List[int]:
    pages: List[int] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        normalized = token.replace("–", "-").replace("—", "-")
        if "-" in normalized:
            start_str, end_str = normalized.split("-", 1)
            if start_str.isdigit() and end_str.isdigit():
                start = int(start_str)
                end = int(end_str)
                if start <= end:
                    pages.extend(range(start, end + 1))
                else:
                    pages.extend(range(end, start + 1))
            continue
        if normalized.isdigit():
            pages.append(int(normalized))
    # Deduplicate while preserving order
    seen = set()
    unique_pages = []
    for page in pages:
        if page not in seen:
            unique_pages.append(page)
            seen.add(page)
    return unique_pages


def _summarize(lines: List[str], fallback: str) -> str:
    summary = " ".join(line.strip() for line in lines if line.strip())
    return summary or fallback or "未提供摘要"
