"""
Vector store adapter built on FAISS with LangChain abstractions.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterable, Optional
import re

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.modules.note.llm_client import get_embedding_model
from app.utils.logger import logger

VECTOR_ROOT = Path(os.getenv("SC_VECTOR_ROOT", ".vectors"))
VECTOR_ROOT.mkdir(exist_ok=True)

_SCOPE_SANITIZER = re.compile(r"[^a-z0-9_\-]+")


def _normalize_scope(scope: Optional[str]) -> str | None:
    if not scope or scope == "notes":
        return None
    slug = _SCOPE_SANITIZER.sub("-", scope.lower()).strip("-")
    return slug or None


def _session_path(session_id: str, scope: Optional[str] = None) -> Path:
    scope_slug = _normalize_scope(scope)
    suffix = f"__{scope_slug}" if scope_slug else ""
    return VECTOR_ROOT / f"{session_id}{suffix}.faiss"


def load_or_create(
    session_id: str, 
    docs: Optional[Iterable[Document]] = None, 
    rebuild: bool = False,
    max_retries: int = 3,
    timeout: int = 180,
    scope: Optional[str] = None,
) -> FAISS:
    """
    加载或创建向量存储，带重试机制和超时控制
    
    Args:
        session_id: 会话ID
        docs: 文档列表
        rebuild: 是否强制重建
        max_retries: 最大重试次数
        timeout: 单次请求超时时间（秒）
        scope: 逻辑作用域（notes/cards/mock 等），用于在同一 session 下区分索引
    """
    path = _session_path(session_id, scope)
    
    # 尝试加载已存在的索引
    if (
        path.exists()
        and (path.with_suffix(".pkl")).exists()
        and not rebuild
    ):
        logger.info(
            "从缓存加载向量索引: session_id=%s scope=%s",
            session_id,
            _normalize_scope(scope) or "notes",
        )
        try:
            return FAISS.load_local(
                str(path),
                get_embedding_model(),
                allow_dangerous_deserialization=True,
            )
        except Exception as exc:
            logger.warning(f"加载缓存失败，将重新构建: {exc}")
    
    if docs is None:
        raise ValueError("docs required for new vector store")
    
    # 转换为列表以便计数
    docs_list = list(docs)
    if not docs_list:
        logger.warning("文档列表为空，创建占位向量存储")
        docs_list = [Document(page_content="Empty document", metadata={"placeholder": True})]
    
    logger.info(
        "准备构建向量索引: session_id=%s scope=%s 文档数=%d 超时=%ds 最大重试=%d次",
        session_id,
        _normalize_scope(scope) or "notes",
        len(docs_list),
        timeout,
        max_retries,
    )
    
    # 带重试的向量存储构建
    last_exception = None
    for attempt in range(max_retries):
        try:
            logger.info("构建向量索引 (尝试 %d/%d)...", attempt + 1, max_retries)
            
            # 获取 embedding 模型并配置超时
            embedding_model = get_embedding_model()
            
            # 为 OpenAI 客户端设置超时（如果支持）
            if hasattr(embedding_model, 'client') and hasattr(embedding_model.client, 'timeout'):
                original_timeout = embedding_model.client.timeout
                embedding_model.client.timeout = timeout
                logger.debug(f"已设置 embedding 超时: {timeout}秒 (原值: {original_timeout})")
            
            # 构建向量存储
            start_time = time.time()
            store = FAISS.from_documents(docs_list, embedding=embedding_model)
            elapsed = time.time() - start_time
            
            logger.info(
                "✅ 向量索引构建成功: session_id=%s scope=%s 耗时=%.2fs 文档数=%d",
                session_id,
                _normalize_scope(scope) or "notes",
                elapsed,
                len(docs_list),
            )
            
            # 保存到磁盘
            store.save_local(str(path))
            logger.info("向量索引已保存: %s", path)
            
            return store
            
        except TimeoutError as exc:
            last_exception = exc
            logger.warning(
                f"⏱️  向量索引构建超时 (尝试 {attempt + 1}/{max_retries}): {exc}"
            )
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避: 1s, 2s, 4s
                logger.info("等待 %d 秒后重试...", wait_time)
                time.sleep(wait_time)
                continue
                
        except ValueError as exc:
            if "No embedding data received" in str(exc):
                last_exception = exc
                logger.error(
                    f"❌ Embedding API 返回空数据 (尝试 {attempt + 1}/{max_retries})"
                )
                logger.error(
                    "可能原因:\n"
                    "  1. 代理服务器不支持当前 embedding 模型\n"
                    "  2. API Key 无效或额度不足\n"
                    "  3. 网络连接问题或请求过大"
                )
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info("等待 %d 秒后重试...", wait_time)
                    time.sleep(wait_time)
                    continue
            else:
                # 其他 ValueError 直接抛出
                raise
                
        except Exception as exc:
            last_exception = exc
            logger.error(
                f"❌ 向量索引构建失败 (尝试 {attempt + 1}/{max_retries}): "
                f"{type(exc).__name__}: {exc}"
            )
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.info("等待 %d 秒后重试...", wait_time)
                time.sleep(wait_time)
                continue
            else:
                raise
    
    # 所有重试都失败
    error_msg = (
        f"向量索引构建失败，已重试 {max_retries} 次。\n"
        f"最后错误: {type(last_exception).__name__}: {last_exception}\n"
        f"建议:\n"
        f"  1. 检查 .env.txt 中的 OPENAI_EMBEDDING_MODEL 设置\n"
        f"  2. 尝试使用 text-embedding-3-small 或 text-embedding-ada-002\n"
        f"  3. 验证 API Key 是否有效\n"
        f"  4. 检查代理服务器是否支持该模型"
    )
    logger.error(error_msg)
    raise RuntimeError(error_msg) from last_exception


def load_existing(session_id: str, scope: Optional[str] = None) -> Optional[FAISS]:
    """
    若存在则加载向量存储，否则返回 None。
    """
    path = _session_path(session_id, scope)
    if not (path.exists() and path.with_suffix(".pkl").exists()):
        return None
    try:
        logger.info(
            "加载现有向量索引: session_id=%s scope=%s",
            session_id,
            _normalize_scope(scope) or "notes",
        )
        return FAISS.load_local(
            str(path),
            get_embedding_model(),
            allow_dangerous_deserialization=True,
        )
    except Exception as exc:
        logger.warning("加载向量索引失败，将返回 None: %s", exc)
        return None


def save(session_id: str, store: FAISS, scope: Optional[str] = None) -> None:
    path = _session_path(session_id, scope)
    store.save_local(str(path))
