from __future__ import annotations

import os
from pathlib import Path

from app.utils.identifiers import new_id

UPLOAD_ROOT = Path(os.getenv("SC_UPLOAD_ROOT", "uploads"))
UPLOAD_ROOT.mkdir(exist_ok=True)


def save_upload(filename: str, data: bytes) -> tuple[str, Path]:
    file_id = new_id("file")
    ext = Path(filename).suffix or ""
    path = UPLOAD_ROOT / f"{file_id}{ext}"
    with open(path, "wb") as fh:
        fh.write(data)
    return file_id, path


def get_path(file_id: str) -> Path:
    for path in UPLOAD_ROOT.glob(f"{file_id}*"):
        return path
    raise FileNotFoundError(f"file {file_id} not found")
