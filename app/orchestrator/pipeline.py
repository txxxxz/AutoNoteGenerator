from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.configs.settings import settings
from app.modules.chunk_outline.outline_builder import OutlineBuilder
from app.modules.layout_ocr.layout_builder import LayoutBuilder
from app.modules.note.generator import NoteGenerator
from app.modules.parser.slide_parser import SlideParser
from app.modules.templates.cards import KnowledgeCardGenerator
from app.modules.templates.mindmap import MindmapGenerator
from app.modules.templates.mock_exam import MockExamGenerator
from app.schemas.common import (
    KnowledgeCards,
    LayoutDoc,
    MockPaper,
    NoteDoc,
    OutlineTree,
    ParseResponse,
)
from app.storage import uploads
from app.storage.database import notes_db, slides_db
from app.storage.repository import repository
from app.utils.identifiers import new_id
from app.utils.logger import logger

ASSET_ROOT = Path(os.getenv("SC_ASSET_ROOT", "assets"))
EXPORT_ROOT = Path(os.getenv("SC_EXPORT_ROOT", "exports"))
VECTOR_ROOT = Path(os.getenv("SC_VECTOR_ROOT", ".vectors"))


class CourseSessionManager:
    def create_session(self, title: str, file_id: str) -> str:
        session_id = new_id("session")
        logger.info("创建会话: session_id=%s title=%s file_id=%s", session_id, title, file_id)
        slides_db.upsert(
            "course_session",
            {
                "id": session_id,
                "title": title,
                "created_at": datetime.utcnow().isoformat(),
                "user_id": "anonymous",
                "file_id": file_id,
                "status": "UPLOADED",
                "meta_json": json.dumps({}),
            },
        )
        return session_id

    def update_status(self, session_id: str, status: str) -> None:
        row = slides_db.fetchone(
            "SELECT title, file_id, created_at, user_id, meta_json FROM course_session WHERE id=?",
            (session_id,),
        )
        if not row:
            logger.error("更新状态失败: session %s 未找到", session_id)
            raise ValueError(f"session {session_id} not found")
        row_dict = dict(zip(row.keys(), row)) if hasattr(row, "keys") else {
            "title": row[0],
            "file_id": row[1],
            "created_at": row[2],
            "user_id": row[3],
            "meta_json": row[4],
        }
        logger.info("更新会话状态: session_id=%s status=%s", session_id, status)
        slides_db.upsert(
            "course_session",
            {
                "id": session_id,
                "title": row_dict["title"],
                "created_at": row_dict["created_at"],
                "user_id": row_dict.get("user_id", "anonymous"),
                "file_id": row_dict["file_id"],
                "status": status,
                "meta_json": row_dict.get("meta_json", json.dumps({})),
            },
        )

    def list_sessions(self) -> list[dict]:
        rows = slides_db.fetch_all(
            "SELECT id, title, status, created_at, file_id FROM course_session ORDER BY datetime(created_at) DESC"
        )
        results = []
        for row in rows:
            results.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "file_id": row["file_id"],
                }
            )
        return results

    def get_session(self, session_id: str) -> dict:
        row = slides_db.fetchone(
            "SELECT id, title, status, created_at, file_id FROM course_session WHERE id=?",
            (session_id,),
        )
        if not row:
            raise ValueError(f"session {session_id} not found")
        if hasattr(row, "keys"):
            return {key: row[key] for key in row.keys()}
        return {
            "id": row[0],
            "title": row[1],
            "status": row[2],
            "created_at": row[3],
            "file_id": row[4],
        }

    def delete_session(self, session_id: str) -> dict:
        row = slides_db.fetchone(
            "SELECT file_id FROM course_session WHERE id=?",
            (session_id,),
        )
        if not row:
            logger.warning("删除会话失败: 未找到 session_id=%s", session_id)
            raise ValueError(f"session {session_id} not found")
        file_id = row["file_id"] if hasattr(row, "keys") else row[0]
        logger.info("开始删除会话: session_id=%s file_id=%s", session_id, file_id)
        self._purge_relational_data(session_id)
        released_bytes = self._purge_session_files(session_id, file_id)
        logger.info("会话删除完成: session_id=%s 释放 %.2f KB", session_id, released_bytes / 1024 or 0.0)
        return {
            "session_id": session_id,
            "released_bytes": released_bytes,
        }

    def _purge_relational_data(self, session_id: str) -> None:
        with slides_db.connect() as conn:
            cursor = conn.execute(
                "SELECT id FROM slide WHERE course_session_id=?",
                (session_id,),
            )
            slide_ids = [row[0] for row in cursor.fetchall()]
            if slide_ids:
                conn.executemany(
                    "DELETE FROM block WHERE slide_id=?",
                    ((slide_id,) for slide_id in slide_ids),
                )
            conn.execute("DELETE FROM slide WHERE course_session_id=?", (session_id,))
            conn.execute("DELETE FROM outline_node WHERE course_session_id=?", (session_id,))
            conn.execute("DELETE FROM artifact WHERE course_session_id=?", (session_id,))
            conn.execute("DELETE FROM course_session WHERE id=?", (session_id,))
        with notes_db.connect() as conn:
            conn.execute("DELETE FROM note_doc WHERE course_session_id=?", (session_id,))
            conn.execute("DELETE FROM artifact WHERE course_session_id=?", (session_id,))

    def _purge_session_files(self, session_id: str, file_id: str | None) -> int:
        released = 0
        if file_id:
            released += self._delete_upload_files(file_id)
        released += self._delete_path(ASSET_ROOT / session_id)
        released += self._delete_path(EXPORT_ROOT / session_id)
        released += self._delete_vector_files(session_id)
        return released

    def _delete_upload_files(self, file_id: str) -> int:
        released = 0
        for path in uploads.UPLOAD_ROOT.glob(f"{file_id}*"):
            released += self._delete_path(path)
        return released

    def _delete_vector_files(self, session_id: str) -> int:
        released = 0
        base = VECTOR_ROOT / f"{session_id}.faiss"
        aux = base.with_suffix(".pkl")
        released += self._delete_path(base)
        released += self._delete_path(aux)
        return released

    def _delete_path(self, path: Path) -> int:
        try:
            if not path.exists():
                return 0
            if path.is_file():
                size = path.stat().st_size
                path.unlink(missing_ok=True)
                return size
            if path.is_dir():
                size = 0
                for file_path in path.rglob("*"):
                    if file_path.is_file():
                        try:
                            size += file_path.stat().st_size
                        except OSError:
                            continue
                shutil.rmtree(path, ignore_errors=True)
                return size
        except FileNotFoundError:
            return 0
        except OSError as exc:
            logger.warning("删除路径失败: path=%s error=%s", path, exc)
        return 0


class CourseSessionPipeline:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.parser = SlideParser()
        self.layout_builder = LayoutBuilder()
        self.outline_builder = OutlineBuilder()
        self.note_generator = NoteGenerator(
            chunk_size=settings.rag.chunk.max_tokens,
            chunk_overlap=settings.rag.chunk.overlap,
            max_workers=settings.rag.note_max_workers,
        )
        self.cards_generator = KnowledgeCardGenerator()
        self.mock_generator = MockExamGenerator()
        self.mindmap_generator = MindmapGenerator()
        self.manager = CourseSessionManager()

    def parse(self, file_id: str, file_type: str) -> ParseResponse:
        file_path = uploads.get_path(file_id)
        logger.info("开始解析: session_id=%s file_id=%s path=%s", self.session_id, file_id, file_path)
        parsed = self.parser.parse(file_path, file_type, self.session_id)
        repository.save_artifact(
            self.session_id, "parse", parsed.model_dump(), artifact_id=f"parse_{self.session_id}"
        )
        self.manager.update_status(self.session_id, "PARSED")
        return parsed

    def build_layout(self) -> LayoutDoc:
        parsed = self._load_parse()
        logger.info("构建版式: session_id=%s", self.session_id)
        layout = self.layout_builder.build(parsed)
        repository.save_artifact(
            self.session_id, "layout", layout.model_dump(), artifact_id=f"layout_{self.session_id}"
        )
        self.manager.update_status(self.session_id, "LAYOUT_BUILT")
        return layout

    def build_outline(self) -> OutlineTree:
        layout = self._load_layout()
        parsed = self._load_parse()
        logger.info("生成大纲: session_id=%s", self.session_id)
        outline = self.outline_builder.build(layout, parsed.doc_meta.get("title", "课程材料"))
        repository.save_artifact(
            self.session_id, "outline", outline.model_dump(), artifact_id=f"outline_{self.session_id}"
        )
        self.manager.update_status(self.session_id, "OUTLINE_READY")
        return outline

    def generate_notes(
        self,
        detail_level: str,
        difficulty: str,
        language: str,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> tuple[str, NoteDoc]:
        if progress_callback:
            progress_callback({"phase": "prepare", "message": "加载解析数据…"})
        outline = self._load_outline()
        layout = self._load_layout()
        if progress_callback:
            progress_callback(
                {
                    "phase": "prepare",
                    "message": f"共 {len(outline.root.children)} 个章节待生成…",
                }
            )
        logger.info(
            "调用笔记生成器: session_id=%s detail=%s difficulty=%s",
            self.session_id,
            detail_level,
            difficulty,
        )
        if progress_callback:
            progress_callback({"phase": "prepare", "message": "构建章节内容…"})
        note_doc = self.note_generator.generate(
            self.session_id,
            outline,
            layout,
            detail_level,
            difficulty,
            language,
            progress_callback=progress_callback,
        )
        if progress_callback:
            progress_callback({"phase": "save", "message": "整理并保存生成结果…"})
        note_id = f"note_{self.session_id}_{detail_level}_{difficulty}_{language}"
        repository.save_artifact(self.session_id, "note_doc", note_doc.model_dump(), artifact_id=note_id)
        notes_db.upsert(
            "note_doc",
            {
                "id": note_id,
                "course_session_id": self.session_id,
                "style_detail": detail_level,
                "style_difficulty": difficulty,
                "style_language": language,
                "content_md": json.dumps([s.model_dump() for s in note_doc.sections], ensure_ascii=False),
                "toc_json": json.dumps(note_doc.toc, ensure_ascii=False),
            },
        )
        self.manager.update_status(self.session_id, "NOTES_READY")
        return note_id, note_doc

    def generate_cards(self, note_doc_id: str) -> tuple[str, KnowledgeCards]:
        note_doc = self._load_note(note_doc_id)
        cards = self.cards_generator.generate(note_doc)
        cards_id = f"cards_{note_doc_id}"
        repository.save_artifact(
            self.session_id, "cards", cards.model_dump(), artifact_id=cards_id
        )
        self.manager.update_status(self.session_id, "TEMPLATES_READY")
        return cards_id, cards

    def generate_mock(self, note_doc_id: str, mode: str, size: int, difficulty: str) -> tuple[str, MockPaper]:
        note_doc = self._load_note(note_doc_id)
        paper = self.mock_generator.generate(note_doc, mode, size, difficulty)
        paper_id = f"mock_{note_doc_id}_{mode}_{size}"
        repository.save_artifact(
            self.session_id, "mock", paper.model_dump(), artifact_id=paper_id
        )
        self.manager.update_status(self.session_id, "TEMPLATES_READY")
        return paper_id, paper

    def generate_mindmap(self) -> tuple[str, dict]:
        outline = self._load_outline()
        graph = self.mindmap_generator.generate(outline)
        graph_id = f"mindmap_{self.session_id}"
        repository.save_artifact(
            self.session_id, "mindmap", graph.model_dump(), artifact_id=graph_id
        )
        return graph_id, graph.model_dump()

    def _load_parse(self) -> ParseResponse:
        payload = repository.load_artifact(f"parse_{self.session_id}")
        if not payload:
            logger.error("解析数据缺失: session_id=%s", self.session_id)
            raise ValueError("parse stage not completed")
        return ParseResponse(**payload)

    def _load_layout(self) -> LayoutDoc:
        payload = repository.load_artifact(f"layout_{self.session_id}")
        if not payload:
            logger.warning("layout 缓存缺失，重新生成: session_id=%s", self.session_id)
            layout = self.build_layout()
            return layout
        return LayoutDoc(**payload)

    def _load_outline(self) -> OutlineTree:
        outline_id = f"outline_{self.session_id}"
        logger.info("尝试加载 outline: artifact_id=%s", outline_id)
        payload = repository.load_artifact(outline_id)
        if not payload:
            logger.warning("⚠️ outline 缓存缺失，重新生成: session_id=%s artifact_id=%s", self.session_id, outline_id)
            outline = self.build_outline()
            logger.info("✅ outline 重新生成完成，children=%d", len(outline.root.children))
            return outline
        logger.info("✅ 成功加载缓存的 outline，children=%d", len(payload.get("root", {}).get("children", [])))
        return OutlineTree(**payload)

    def _load_note(self, note_doc_id: str) -> NoteDoc:
        payload = repository.load_artifact(note_doc_id)
        if not payload:
            raise ValueError(f"note doc {note_doc_id} not found")
        return NoteDoc(**payload)
