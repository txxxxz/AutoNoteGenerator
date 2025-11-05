"""
SQLite helper for StudyCompanion.

我们按照需求拆分为两个数据库：
- `lectureslides.db`：存储课程会话、原始 PPT/PDF 解析相关的结构数据。
- `note.db`：存储生成的笔记及其衍生物（卡片、模拟题、思维导图等）。
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from app.utils.logger import logger


DEFAULT_DB_DIR = Path("db")
SLIDES_DB_PATH = Path(os.getenv("SC_SLIDES_DB_PATH", DEFAULT_DB_DIR / "lectureslides.db"))
NOTES_DB_PATH = Path(os.getenv("SC_NOTES_DB_PATH", DEFAULT_DB_DIR / "note.db"))

SLIDES_SCHEMA = """
CREATE TABLE IF NOT EXISTS course_session (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TEXT,
    user_id TEXT,
    file_id TEXT,
    status TEXT,
    meta_json TEXT
);
CREATE TABLE IF NOT EXISTS slide (
    id TEXT PRIMARY KEY,
    course_session_id TEXT,
    page_no INTEGER,
    meta_json TEXT
);
CREATE TABLE IF NOT EXISTS block (
    id TEXT PRIMARY KEY,
    slide_id TEXT,
    type TEXT,
    block_order INTEGER,
    bbox_json TEXT,
    raw_text TEXT,
    asset_uri TEXT,
    latex TEXT
);
CREATE TABLE IF NOT EXISTS outline_node (
    id TEXT PRIMARY KEY,
    course_session_id TEXT,
    parent_id TEXT,
    title TEXT,
    summary TEXT,
    anchors_json TEXT,
    level INTEGER,
    node_order INTEGER
);
CREATE TABLE IF NOT EXISTS artifact (
    id TEXT PRIMARY KEY,
    course_session_id TEXT,
    kind TEXT,
    payload_json TEXT
);
"""

NOTES_SCHEMA = """
CREATE TABLE IF NOT EXISTS note_doc (
    id TEXT PRIMARY KEY,
    course_session_id TEXT,
    style_detail TEXT,
    style_difficulty TEXT,
    content_md TEXT,
    toc_json TEXT
);
CREATE TABLE IF NOT EXISTS artifact (
    id TEXT PRIMARY KEY,
    course_session_id TEXT,
    kind TEXT,
    payload_json TEXT
);
"""


class Database:
    def __init__(self, path: Path, schema: str):
        self.path = path
        self.schema = schema
        self._ensure_schema()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(self.schema)
        logger.info("数据库初始化完成: %s", self.path)

    def upsert(self, table: str, data: Dict[str, Any]) -> None:
        keys = ", ".join(data.keys())
        placeholders = ", ".join([":" + k for k in data.keys()])
        sql = f"INSERT OR REPLACE INTO {table} ({keys}) VALUES ({placeholders})"
        with self.connect() as conn:
            conn.execute(sql, data)

    def fetchone(
        self, sql: str, params: Optional[Iterable[Any]] = None
    ) -> Optional[sqlite3.Row]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(sql, params or [])
            return cur.fetchone()

    def fetch_json(self, table: str, ident: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(f"SELECT * FROM {table} WHERE id=? LIMIT 1", (ident,))
            row = cur.fetchone()
            if not row:
                return None
            payload = dict(row)
            for key, value in payload.items():
                if key.endswith("_json") and value:
                    payload[key] = json.loads(value)
            return payload

    def fetch_all(
        self, sql: str, params: Optional[Iterable[Any]] = None
    ) -> list[sqlite3.Row]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(sql, params or [])
            return cur.fetchall()


slides_db = Database(SLIDES_DB_PATH, SLIDES_SCHEMA)
notes_db = Database(NOTES_DB_PATH, NOTES_SCHEMA)
