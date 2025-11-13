"""
Utility for storing page-level assets (images, tables, formulas) on disk.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO

ASSET_ROOT = Path(os.getenv("SC_ASSET_ROOT", "assets"))
ASSET_ROOT.mkdir(exist_ok=True)
ASSET_BASE_URL = os.getenv("SC_ASSET_BASE_URL", "http://127.0.0.1:8000")


def _public_uri(session_id: str, filename: str) -> str:
    safe_session = session_id.strip().replace("..", "")
    safe_name = Path(filename).name
    base = (ASSET_BASE_URL or "").rstrip("/")
    prefix = base if base else ""
    return f"{prefix}/assets/{safe_session}/{safe_name}"


def session_dir(session_id: str) -> Path:
    path = ASSET_ROOT / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_asset(session_id: str, filename: str, data: bytes) -> str:
    path = session_dir(session_id) / filename
    with open(path, "wb") as fh:
        fh.write(data)
    return _public_uri(session_id, filename)


def save_stream(session_id: str, filename: str, stream: BinaryIO) -> str:
    return write_asset(session_id, filename, stream.read())
