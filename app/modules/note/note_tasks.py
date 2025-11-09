from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from queue import Queue
from typing import Dict, Optional

from app.orchestrator.pipeline import CourseSessionPipeline
from app.schemas.common import NoteDoc
from app.utils.identifiers import new_id
from app.utils.logger import logger


@dataclass
class NoteTaskState:
    task_id: str
    session_id: str
    detail_level: str
    difficulty: str
    status: str = "queued"
    progress: float = 0.0
    total_sections: int = 0
    current_section: Optional[str] = None
    message: Optional[str] = None
    note_doc_id: Optional[str] = None
    note_doc: Optional[NoteDoc] = None
    error: Optional[str] = None
    events: "Queue[dict]" = field(default_factory=Queue)


class NoteTaskManager:
    def __init__(self) -> None:
        self._tasks: Dict[str, NoteTaskState] = {}
        self._lock = threading.Lock()

    def create_task(self, session_id: str, detail_level: str, difficulty: str) -> NoteTaskState:
        task_id = new_id("task")
        state = NoteTaskState(
            task_id=task_id,
            session_id=session_id,
            detail_level=detail_level,
            difficulty=difficulty,
            message="任务已排队，等待执行…",
        )
        with self._lock:
            self._tasks[task_id] = state
        self._push_event(state, include_result=False)
        return state

    def mark_running(self, task_id: str) -> None:
        with self._lock:
            state = self._tasks.get(task_id)
            if not state:
                return
            state.status = "running"
            state.message = "笔记生成已开始…"
        self._push_event(state, include_result=False)

    def handle_progress(self, task_id: str, event: dict) -> None:
        if not isinstance(event, dict):
            return
        with self._lock:
            state = self._tasks.get(task_id)
            if not state:
                return
            state.status = "running"
            phase = event.get("phase")
            status = event.get("status")
            message = event.get("message")
            if isinstance(message, str):
                state.message = message
            total = event.get("total")
            if isinstance(total, int) and total > 0:
                state.total_sections = total
            if phase == "sections_total" and isinstance(total, int):
                state.progress = 0.0 if total else 100.0
            elif phase == "section":
                title = event.get("title")
                if isinstance(title, str):
                    state.current_section = title
                index = event.get("index")
                total_sections = state.total_sections or event.get("total") or 0
                if status == "start":
                    if isinstance(title, str):
                        state.message = f"正在生成：{title}"
                elif status == "complete":
                    if isinstance(index, int) and total_sections:
                        state.progress = max(
                            state.progress, min((index / total_sections) * 100.0, 100.0)
                        )
                    if isinstance(title, str):
                        state.message = f"完成章节：{title}"
            elif phase == "save":
                state.message = message or "保存结果中…"
            elif phase == "prepare":
                if isinstance(message, str):
                    state.message = message
            state.progress = min(state.progress, 100.0)
        self._push_event(state, include_result=False)

    def mark_completed(self, task_id: str, note_doc_id: str, note_doc: NoteDoc) -> None:
        with self._lock:
            state = self._tasks.get(task_id)
            if not state:
                return
            state.status = "completed"
            state.progress = 100.0
            state.current_section = None
            state.message = "笔记生成完成"
            state.note_doc_id = note_doc_id
            state.note_doc = note_doc
        self._push_event(state, include_result=True)

    def mark_failed(self, task_id: str, error: str) -> None:
        with self._lock:
            state = self._tasks.get(task_id)
            if not state:
                return
            state.status = "failed"
            state.current_section = None
            state.message = "笔记生成失败"
            state.error = error
        self._push_event(state, include_result=True)

    def snapshot(
        self,
        task_id: str,
        include_result: bool = True,
        for_json: bool = False,
    ) -> Optional[dict]:
        with self._lock:
            state = self._tasks.get(task_id)
            if not state:
                return None
            return self._serialize(state, include_result=include_result, for_json=for_json)

    def event_queue(self, task_id: str) -> Optional["Queue[dict]"]:
        with self._lock:
            state = self._tasks.get(task_id)
            if not state:
                return None
            return state.events

    def has_active_task(self, session_id: str) -> bool:
        with self._lock:
            return any(
                state.session_id == session_id and state.status in {"queued", "running"}
                for state in self._tasks.values()
            )

    def _push_event(self, state: NoteTaskState, include_result: bool) -> None:
        payload = self._serialize(state, include_result=include_result, for_json=True)
        state.events.put(payload)

    def _serialize(
        self,
        state: NoteTaskState,
        include_result: bool,
        for_json: bool,
    ) -> dict:
        data: dict = {
            "task_id": state.task_id,
            "session_id": state.session_id,
            "status": state.status,
            "progress": round(state.progress, 2),
            "detail_level": state.detail_level,
            "difficulty": state.difficulty,
            "total_sections": state.total_sections,
            "current_section": state.current_section,
            "message": state.message,
        }
        if state.note_doc_id:
            data["note_doc_id"] = state.note_doc_id
        if state.error:
            data["error"] = state.error
        if include_result and state.note_doc is not None:
            data["note_doc"] = (
                state.note_doc.model_dump()
                if for_json
                else state.note_doc
            )
        return data


note_task_manager = NoteTaskManager()
_executor = ThreadPoolExecutor(max_workers=2)


def submit_note_generation_task(session_id: str, detail_level: str, difficulty: str) -> str:
    state = note_task_manager.create_task(session_id, detail_level, difficulty)

    def runner() -> None:
        note_task_manager.mark_running(state.task_id)
        pipeline = CourseSessionPipeline(session_id)
        try:
            note_id, note_doc = pipeline.generate_notes(
                detail_level,
                difficulty,
                progress_callback=lambda event: note_task_manager.handle_progress(state.task_id, event),
            )
            note_task_manager.mark_completed(state.task_id, note_id, note_doc)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception(
                "笔记生成任务失败: task_id=%s session_id=%s error=%s",
                state.task_id,
                session_id,
                exc,
            )
            note_task_manager.mark_failed(state.task_id, str(exc))

    _executor.submit(runner)
    return state.task_id
