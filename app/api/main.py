from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse

from app.orchestrator.pipeline import CourseSessionManager, CourseSessionPipeline
from app.schemas.api import (
    CardsRequest,
    ExportRequest,
    LayoutRequest,
    MindmapRequest,
    MockRequest,
    NotesRequest,
    OutlineRequest,
    ParseRequest,
    QARequest,
    SessionDetail,
    SessionListResponse,
    SessionSummary,
    NoteTaskResponse,
    NoteTaskStatus,
    NoteLanguage,
    LLMSettingsPayload,
    LLMSettingsResponse,
)
from app.schemas.common import (
    ExportResponse,
    KnowledgeCards,
    LayoutDoc,
    MindmapGraph,
    MockPaper,
    NoteDoc,
    OutlineTree,
    ParseResponse,
    QAResponse,
)
from app.storage import uploads
from app.storage.repository import repository
from app.storage.settings_store import get_llm_settings, save_llm_settings
from app.modules.exporter.export_service import ExportService
from app.modules.qa.qa_service import QAService
from app.modules.note.note_tasks import note_task_manager, submit_note_generation_task
from app.modules.note.llm_client import LLM_PROVIDER, reset_llm_cache
from app.configs.settings import settings
from app.utils.logger import logger

app = FastAPI(title="StudyCompanion API", version="1.0.0")
manager = CourseSessionManager()


def get_pipeline(session_id: str) -> CourseSessionPipeline:
    return CourseSessionPipeline(session_id)


ALLOWED_EXTENSIONS = {".pptx", ".pdf"}


@app.post("/api/v1/files")
async def upload_file(
    file: UploadFile = File(...),
    title: str | None = Form(None),
):
    logger.info("收到文件上传请求: filename=%s, content_type=%s", file.filename, file.content_type)
    filename = file.filename or "uploaded_file"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        logger.warning("文件类型不支持: %s", suffix)
        raise HTTPException(status_code=400, detail="仅支持 .pptx 与 .pdf 文件")
    data = await file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > settings.limits.max_file_mb:
        logger.warning("文件超出大小限制: %.2fMB > %dMB", size_mb, settings.limits.max_file_mb)
        raise HTTPException(
            status_code=400,
            detail=f"文件超过 {settings.limits.max_file_mb}MB 限制",
        )
    file_id, _ = uploads.save_upload(filename, data)
    session_id = manager.create_session(title or Path(filename).stem, file_id)
    logger.info("文件上传完成: session_id=%s file_id=%s", session_id, file_id)
    return {"file_id": file_id, "session_id": session_id}


@app.get("/api/v1/sessions", response_model=SessionListResponse)
def list_sessions():
    sessions = manager.list_sessions()
    summaries = [_build_session_summary(session) for session in sessions]
    return SessionListResponse(sessions=summaries)


@app.get("/api/v1/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: str):
    session_data = manager.get_session(session_id)
    return _build_session_detail(session_data)


@app.delete("/api/v1/sessions/{session_id}")
def delete_session(session_id: str):
    if note_task_manager.has_active_task(session_id):
        raise HTTPException(status_code=409, detail="当前会话仍有笔记生成任务进行中")
    try:
        result = manager.delete_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True, **result}


@app.post("/api/v1/parse", response_model=ParseResponse)
def parse_file(request: ParseRequest):
    pipeline = get_pipeline(request.session_id)
    logger.info(
        "开始解析文件: session_id=%s file_id=%s file_type=%s",
        request.session_id,
        request.file_id,
        request.file_type.value,
    )
    try:
        result = pipeline.parse(request.file_id, request.file_type.value)
        logger.info("解析成功: session_id=%s 页数=%s", request.session_id, result.doc_meta.get("pages"))
        return result
    except Exception as exc:
        logger.exception("解析失败: session_id=%s 错误=%s", request.session_id, exc)
        raise HTTPException(status_code=500, detail=f"解析失败: {exc}") from exc


@app.post("/api/v1/layout/build", response_model=LayoutDoc)
def build_layout(request: LayoutRequest):
    pipeline = get_pipeline(request.session_id)
    logger.info("开始版式还原: session_id=%s file_id=%s", request.session_id, request.file_id)
    try:
        result = pipeline.build_layout()
        logger.info("版式还原成功: session_id=%s 页数=%d", request.session_id, len(result.pages))
        return result
    except Exception as exc:
        logger.exception("版式还原失败: session_id=%s 错误=%s", request.session_id, exc)
        raise HTTPException(status_code=500, detail=f"版式还原失败: {exc}") from exc


@app.post("/api/v1/outline/build", response_model=OutlineTree)
def build_outline(request: OutlineRequest):
    pipeline = get_pipeline(request.session_id)
    logger.info("开始生成大纲: session_id=%s", request.session_id)
    try:
        result = pipeline.build_outline()
        logger.info("大纲生成成功: session_id=%s 子节点数=%d", request.session_id, len(result.root.children))
        return result
    except Exception as exc:
        logger.exception("大纲生成失败: session_id=%s 错误=%s", request.session_id, exc)
        raise HTTPException(status_code=500, detail=f"大纲生成失败: {exc}") from exc


@app.get("/api/v1/outline/{outline_id}", response_model=OutlineTree)
def get_outline_tree(outline_id: str):
    payload = repository.load_artifact(outline_id)
    if not payload:
        raise HTTPException(status_code=404, detail=f"outline {outline_id} not found")
    return OutlineTree(**payload)


@app.post("/api/v1/notes/generate", response_model=NoteTaskResponse)
def generate_notes(request: NotesRequest):
    style = request.style
    detail = style.get("detail_level")
    difficulty = style.get("difficulty")
    if not detail or not difficulty:
        raise HTTPException(status_code=400, detail="style must include detail_level and difficulty")
    language_value = request.language or style.get("language") or NoteLanguage.zh
    try:
        language = NoteLanguage(language_value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="language must be either 'zh' or 'en'") from exc
    logger.info(
        "生成笔记: session_id=%s detail=%s difficulty=%s language=%s",
        request.session_id,
        detail,
        difficulty,
        language.value,
    )
    try:
        task_id = submit_note_generation_task(request.session_id, detail, difficulty, language.value)
    except Exception as exc:
        logger.exception("生成笔记失败: session_id=%s 错误=%s", request.session_id, exc)
        raise HTTPException(status_code=500, detail=f"生成笔记失败: {exc}") from exc
    return NoteTaskResponse(task_id=task_id)


@app.get("/api/v1/notes/tasks/{task_id}", response_model=NoteTaskStatus)
def get_note_task(task_id: str):
    snapshot = note_task_manager.snapshot(task_id, include_result=True)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="note generation task not found")
    return snapshot


@app.get("/api/v1/notes/tasks/{task_id}/stream")
async def stream_note_task(task_id: str):
    queue = note_task_manager.event_queue(task_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="note generation task not found")

    async def event_generator():
        initial = note_task_manager.snapshot(task_id, include_result=True, for_json=True)
        if initial:
            yield _format_sse(initial)
            if initial.get("status") in {"completed", "failed"}:
                return
        loop = asyncio.get_running_loop()
        while True:
            event = await loop.run_in_executor(None, queue.get)
            yield _format_sse(event)
            if event.get("status") in {"completed", "failed"}:
                break

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@app.post("/api/v1/cards/generate")
def generate_cards(request: CardsRequest):
    pipeline = get_pipeline(request.session_id)
    logger.info("生成知识卡片: session_id=%s note_doc_id=%s", request.session_id, request.note_doc_id)
    cards_id, cards = pipeline.generate_cards(request.note_doc_id)
    return {"cards_id": cards_id, "cards": cards}


@app.post("/api/v1/mock/generate")
def generate_mock(request: MockRequest):
    pipeline = get_pipeline(request.session_id)
    logger.info(
        "生成模拟试题: session_id=%s note_doc_id=%s mode=%s size=%s difficulty=%s",
        request.session_id,
        request.note_doc_id,
        request.options.mode,
        request.options.size,
        request.options.difficulty,
    )
    paper_id, paper = pipeline.generate_mock(
        request.note_doc_id,
        request.options.mode,
        request.options.size,
        request.options.difficulty,
    )
    return {"paper_id": paper_id, "paper": paper}


@app.post("/api/v1/mindmap/generate")
def generate_mindmap(request: MindmapRequest):
    pipeline = get_pipeline(request.session_id)
    logger.info("生成思维导图: session_id=%s outline_id=%s", request.session_id, request.outline_tree_id)
    graph_id, graph = pipeline.generate_mindmap()
    return {"graph_id": graph_id, "graph": graph}


@app.post("/api/v1/export")
def export_artifact(request: ExportRequest):
    exporter = ExportService(request.session_id)
    export_result = None
    
    if request.type == "notes":
        note_doc = _load_note(request.target_id)
        export_result = exporter.export_notes(note_doc, request.format)
    elif request.type == "cards":
        cards = _load_cards(request.target_id)
        export_result = exporter.export_cards(cards, request.format)
    elif request.type == "mock":
        paper = _load_mock(request.target_id)
        export_result = exporter.export_mock(paper, request.format)
    elif request.type == "mindmap":
        graph = _load_mindmap(request.target_id)
        export_result = exporter.export_mindmap(graph, request.format)
    else:
        raise HTTPException(status_code=400, detail="unsupported export type")
    
    # 直接返回文件供浏览器下载
    file_path = Path(export_result.download_url)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="export file not found")
    
    # 根据格式设置 MIME 类型
    media_type_map = {
        "md": "text/markdown",
        "pdf": "application/pdf",
        "png": "image/png",
    }
    media_type = media_type_map.get(request.format, "application/octet-stream")
    
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=export_result.filename,
        headers={
            "Content-Disposition": f'attachment; filename="{export_result.filename}"'
        }
    )


@app.post("/api/v1/qa/ask", response_model=QAResponse)
def ask_question(request: QARequest):
    qa_service = QAService(request.session_id)
    logger.info("问答请求: session_id=%s scope=%s question=%s", request.session_id, request.scope, request.question)
    note_doc = _latest_note(request.session_id)
    cards = _latest_cards(request.session_id)
    mock = _latest_mock(request.session_id)
    return qa_service.ask(request.question, request.scope, note_doc, cards, mock)


def _load_note(note_doc_id: str) -> NoteDoc:
    payload = repository.load_artifact(note_doc_id)
    if not payload:
        raise HTTPException(status_code=404, detail="note doc not found")
    return NoteDoc(**payload)


def _load_cards(cards_id: str) -> KnowledgeCards:
    payload = repository.load_artifact(cards_id)
    if not payload:
        raise HTTPException(status_code=404, detail="cards not found")
    return KnowledgeCards(**payload)


def _load_mock(mock_id: str) -> MockPaper:
    payload = repository.load_artifact(mock_id)
    if not payload:
        raise HTTPException(status_code=404, detail="mock paper not found")
    return MockPaper(**payload)


def _load_mindmap(graph_id: str) -> MindmapGraph:
    payload = repository.load_artifact(graph_id)
    if not payload:
        raise HTTPException(status_code=404, detail="mindmap not found")
    return MindmapGraph(**payload)


def _latest_note(session_id: str) -> NoteDoc | None:
    artifacts = repository.list_artifacts(session_id, "note_doc")
    if not artifacts:
        return None
    artifact = artifacts[-1]
    return NoteDoc(**artifact[1])


def _latest_cards(session_id: str) -> KnowledgeCards | None:
    artifacts = repository.list_artifacts(session_id, "cards")
    if not artifacts:
        return None
    return KnowledgeCards(**artifacts[-1][1])


def _latest_mock(session_id: str) -> MockPaper | None:
    artifacts = repository.list_artifacts(session_id, "mock")
    if not artifacts:
        return None
    return MockPaper(**artifacts[-1][1])


def _format_sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.get("/api/v1/notes/{note_doc_id}", response_model=NoteDoc)
def get_note(note_doc_id: str):
    return _load_note(note_doc_id)


@app.get("/api/v1/cards/{cards_id}", response_model=KnowledgeCards)
def get_cards(cards_id: str):
    return _load_cards(cards_id)


@app.get("/api/v1/mock/{mock_id}", response_model=MockPaper)
def get_mock(mock_id: str):
    return _load_mock(mock_id)


@app.get("/api/v1/mindmap/{graph_id}", response_model=MindmapGraph)
def get_mindmap(graph_id: str):
    return _load_mindmap(graph_id)


@app.get("/api/v1/settings/llm", response_model=LLMSettingsResponse)
def read_llm_settings():
    return _build_llm_settings_response(get_llm_settings())


@app.post("/api/v1/settings/llm", response_model=LLMSettingsResponse)
def update_llm_settings(payload: LLMSettingsPayload):
    updates = payload.model_dump(exclude_unset=True)
    saved = save_llm_settings(updates)
    reset_llm_cache()
    return _build_llm_settings_response(saved)


def _build_session_summary(session_data: dict) -> SessionSummary:
    session_id = session_data["id"]
    note_ids = repository.list_artifact_ids(session_id, "note_doc")
    cards_ids = repository.list_artifact_ids(session_id, "cards")
    mock_ids = repository.list_artifact_ids(session_id, "mock")
    mindmap_ids = repository.list_artifact_ids(session_id, "mindmap")
    return SessionSummary(
        id=session_id,
        title=session_data["title"],
        status=session_data["status"],
        created_at=session_data["created_at"],
        file_id=session_data["file_id"],
        note_doc_ids=note_ids,
        cards_ids=cards_ids,
        mock_ids=mock_ids,
        mindmap_ids=mindmap_ids,
    )


def _build_session_detail(session_data: dict) -> SessionDetail:
    summary = _build_session_summary(session_data)
    available = {
        "parse": repository.list_artifact_ids(summary.id, "parse"),
        "layout": repository.list_artifact_ids(summary.id, "layout"),
        "outline": repository.list_artifact_ids(summary.id, "outline"),
        "note_doc": summary.note_doc_ids,
        "cards": summary.cards_ids,
        "mock": summary.mock_ids,
        "mindmap": summary.mindmap_ids,
    }
    return SessionDetail(
        **summary.model_dump(),
        available_artifacts=available,
    )


def _build_llm_settings_response(payload: dict | None) -> LLMSettingsResponse:
    payload = payload or {}
    provider = (payload.get("provider") or LLM_PROVIDER).strip().lower()
    if provider not in {"google", "openai"}:
        provider = LLM_PROVIDER
    llm_model = payload.get("llm_model")
    embedding_model = payload.get("embedding_model")
    base_url = payload.get("base_url")
    api_key = payload.get("api_key")
    api_key_present = bool(api_key)
    preview = None
    if api_key_present and isinstance(api_key, str):
        preview = f"...{api_key[-4:]}" if len(api_key) > 4 else "****"
    return LLMSettingsResponse(
        provider=provider,  # type: ignore[arg-type]
        llm_model=llm_model,
        embedding_model=embedding_model,
        base_url=base_url,
        api_key_present=api_key_present,
        api_key_preview=preview,
    )
