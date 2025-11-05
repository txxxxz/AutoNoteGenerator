"""
Application settings loader aligned with the architecture specification.

The configuration file (`config.yaml`) is optional; when absent we fall back to
defaults that satisfy the documented limits. Environment variables can override
individual sections using the `SC__` prefix (e.g. `SC__LIMITS__MAX_PAGES=150`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import yaml

CONFIG_PATH = os.getenv("SC_CONFIG_PATH", "config.yaml")
ENV_PREFIX = "SC__"


def _apply_env_overrides(base: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flattened env overrides use the format `SC__SECTION__KEY=value`.
    Nested objects are created on demand.
    """
    result: Dict[str, Any] = dict(base)
    for key, value in os.environ.items():
        if not key.startswith(ENV_PREFIX):
            continue
        parts = key[len(ENV_PREFIX) :].lower().split("__")
        cursor = result
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = _cast_env_value(value)
    return result


def _cast_env_value(raw: str) -> Any:
    lowered = raw.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


@dataclass(slots=True)
class LimitsConfig:
    max_pages: int = 200
    max_file_mb: int = 100


@dataclass(slots=True)
class NotesConfig:
    default_detail: str = "medium"
    default_difficulty: str = "explanatory"


@dataclass(slots=True)
class ExportConfig:
    pdf_header: bool = True
    pdf_toc: bool = True
    md_math_block: bool = True


@dataclass(slots=True)
class RAGChunkConfig:
    max_tokens: int = 500
    overlap: int = 50


@dataclass(slots=True)
class RAGConfig:
    chunk: RAGChunkConfig = field(default_factory=RAGChunkConfig)


@dataclass(slots=True)
class Settings:
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    notes: NotesConfig = field(default_factory=NotesConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Settings":
        path_to_use = path or CONFIG_PATH
        data: Dict[str, Any] = {}
        if os.path.exists(path_to_use):
            with open(path_to_use, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        merged = _apply_env_overrides(data)
        return cls(
            limits=LimitsConfig(**merged.get("limits", {})),
            notes=NotesConfig(**merged.get("notes", {})),
            export=ExportConfig(
                pdf_header=merged.get("export", {}).get("pdf", {}).get("header", True),
                pdf_toc=merged.get("export", {}).get("pdf", {}).get("toc", True),
                md_math_block=merged.get("export", {}).get("md", {}).get("math_block", True),
            ),
            rag=RAGConfig(
                chunk=RAGChunkConfig(**merged.get("rag", {}).get("chunk", {})),
            ),
        )


settings = Settings.load()
