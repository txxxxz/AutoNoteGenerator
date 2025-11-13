from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Optional, Tuple

from dotenv import load_dotenv

from app.storage.settings_store import get_llm_settings
from app.utils.logger import logger

# Load environment variables early so CLI usage works.
load_dotenv(dotenv_path=".env.txt")

_default_provider = "google"
if os.getenv("OPENAI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    _default_provider = "openai"

LLM_PROVIDER = os.getenv("LLM_PROVIDER", _default_provider).strip().lower()

try:
    from langchain_google_genai import (
        ChatGoogleGenerativeAI,
        GoogleGenerativeAIEmbeddings,
    )
except ImportError:
    ChatGoogleGenerativeAI = None  # type: ignore
    GoogleGenerativeAIEmbeddings = None  # type: ignore

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
except ImportError:
    ChatOpenAI = None  # type: ignore
    OpenAIEmbeddings = None  # type: ignore


def _require_env(value: str | None, var_name: str, provider: str) -> str:
    if value:
        return value
    raise ValueError(
        f"{var_name} must be set when LLM_PROVIDER='{provider}'. "
        "Update your environment variables (e.g. .env.txt)."
    )


def _set_env_if_needed(var_name: str, value: str) -> None:
    if value and os.getenv(var_name) != value:
        os.environ[var_name] = value


def _resolve_provider(overrides: dict[str, Any]) -> str:
    provider = (overrides.get("provider") or LLM_PROVIDER or _default_provider).strip().lower()
    if provider not in {"google", "openai"}:
        provider = LLM_PROVIDER
    return provider


def _resolve_openai_api_key(overrides: dict[str, Any]) -> str:
    return overrides.get("api_key") or _require_env(
        os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY", "openai"
    )


def _resolve_google_api_key(overrides: dict[str, Any]) -> str:
    return overrides.get("api_key") or _require_env(
        os.getenv("GOOGLE_API_KEY"), "GOOGLE_API_KEY", "google"
    )


def _resolve_openai_base_url(overrides: dict[str, Any]) -> Optional[str]:
    base_url = overrides.get("base_url") or os.getenv("OPENAI_API_BASE")
    return base_url.rstrip("/") if base_url else None


def _resolve_models(
    overrides: dict[str, Any], provider: str
) -> Tuple[str, str]:
    if provider == "openai":
        llm_model = overrides.get("llm_model") or os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
        embedding_model = overrides.get("embedding_model") or os.getenv(
            "OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"
        )
    else:
        llm_model = overrides.get("llm_model") or os.getenv(
            "GOOGLE_LLM_MODEL", "gemini-1.5-flash-latest"
        )
        embedding_model = overrides.get("embedding_model") or os.getenv(
            "GOOGLE_EMBEDDING_MODEL", "models/embedding-001"
        )
    return llm_model, embedding_model


@lru_cache(maxsize=4)
def _embedding_model_factory(
    provider: str, embedding_model_name: str, base_url: Optional[str], api_key: str
):
    if provider == "openai":
        if OpenAIEmbeddings is None:
            raise ImportError(
                "langchain-openai is required when LLM_PROVIDER='openai'. "
                "Install it with `pip install langchain-openai openai`."
            )
        
        # 构建参数，包括更长的超时时间
        kwargs = {
            "model": embedding_model_name,
            "openai_api_key": api_key,
            "request_timeout": 180.0,  # 3分钟超时
            "max_retries": 2,  # 允许重试2次
        }
        if base_url:
            kwargs["openai_api_base"] = base_url
        
        logger.info(
            f"初始化 OpenAI Embedding 模型: model={embedding_model_name}, "
            f"base_url={base_url or 'default'}, timeout=180s"
        )
        
        try:
            embeddings = OpenAIEmbeddings(**kwargs)
            logger.info(f"✅ Embedding 模型初始化成功: {embedding_model_name}")
            return embeddings
        except Exception as e:
            logger.error(f"❌ OpenAI Embedding 初始化失败: {e}")
            # 不自动降级，让用户明确知道问题
            raise

    if GoogleGenerativeAIEmbeddings is None:
        raise ImportError(
            "langchain-google-genai is required when LLM_PROVIDER='google'. "
            "Install it with `pip install langchain-google-genai google-generativeai`."
        )
    logger.info(f"初始化 Google Embedding 模型: model={embedding_model_name}")
    return GoogleGenerativeAIEmbeddings(model=embedding_model_name, google_api_key=api_key)


def get_embedding_model():
    overrides = get_llm_settings()
    provider = _resolve_provider(overrides)
    llm_model, embedding_model = _resolve_models(overrides, provider)
    
    logger.info(f"获取 Embedding 模型: provider={provider}, model={embedding_model}")
    
    if provider == "openai":
        api_key = _resolve_openai_api_key(overrides)
        base_url = _resolve_openai_base_url(overrides)
        _set_env_if_needed("OPENAI_API_KEY", api_key)
        if base_url:
            _set_env_if_needed("OPENAI_API_BASE", base_url)
        logger.debug(f"OpenAI 配置: base_url={base_url}, api_key={'***' + api_key[-4:] if api_key else 'None'}")
    else:
        api_key = _resolve_google_api_key(overrides)
        _set_env_if_needed("GOOGLE_API_KEY", api_key)
        base_url = None
    
    return _embedding_model_factory(provider, embedding_model, base_url, api_key)


def get_llm(temperature: float = 0.3):
    overrides = get_llm_settings()
    provider = _resolve_provider(overrides)
    llm_model, _ = _resolve_models(overrides, provider)
    if provider == "openai":
        if ChatOpenAI is None:
            raise ImportError(
                "langchain-openai is required when LLM_PROVIDER='openai'. "
                "Install it with `pip install langchain-openai openai`."
            )
        api_key = _resolve_openai_api_key(overrides)
        base_url = _resolve_openai_base_url(overrides)
        _set_env_if_needed("OPENAI_API_KEY", api_key)
        if base_url:
            _set_env_if_needed("OPENAI_API_BASE", base_url)
        kwargs = {
            "model": llm_model,
            "temperature": temperature,
            "openai_api_key": api_key,
        }
        if base_url:
            kwargs["openai_api_base"] = base_url
        return ChatOpenAI(**kwargs)

    if ChatGoogleGenerativeAI is None:
        raise ImportError(
            "langchain-google-genai is required when LLM_PROVIDER='google'. "
            "Install it with `pip install langchain-google-genai google-generativeai`."
        )
    api_key = _resolve_google_api_key(overrides)
    _set_env_if_needed("GOOGLE_API_KEY", api_key)
    return ChatGoogleGenerativeAI(
        model=llm_model,
        convert_system_message_to_human=True,
        temperature=temperature,
        google_api_key=api_key,
    )


def reset_llm_cache() -> None:
    _embedding_model_factory.cache_clear()
