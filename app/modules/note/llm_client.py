from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

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


@lru_cache(maxsize=1)
def get_embedding_model():
    if LLM_PROVIDER == "openai":
        if OpenAIEmbeddings is None:
            raise ImportError(
                "langchain-openai is required when LLM_PROVIDER='openai'. "
                "Install it with `pip install langchain-openai openai`."
            )
        api_key = _require_env(os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY", "openai")
        base_url = os.getenv("OPENAI_API_BASE")
        embedding_model_name = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
        kwargs = {"model": embedding_model_name, "openai_api_key": api_key}
        if base_url:
            kwargs["openai_api_base"] = base_url.rstrip("/")
        return OpenAIEmbeddings(**kwargs)

    if GoogleGenerativeAIEmbeddings is None:
        raise ImportError(
            "langchain-google-genai is required when LLM_PROVIDER='google'. "
            "Install it with `pip install langchain-google-genai google-generativeai`."
        )
    api_key = _require_env(os.getenv("GOOGLE_API_KEY"), "GOOGLE_API_KEY", "google")
    embedding_model_name = os.getenv("GOOGLE_EMBEDDING_MODEL", "models/embedding-001")
    return GoogleGenerativeAIEmbeddings(model=embedding_model_name, google_api_key=api_key)


def get_llm(temperature: float = 0.3):
    if LLM_PROVIDER == "openai":
        if ChatOpenAI is None:
            raise ImportError(
                "langchain-openai is required when LLM_PROVIDER='openai'. "
                "Install it with `pip install langchain-openai openai`."
            )
        api_key = _require_env(os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY", "openai")
        base_url = os.getenv("OPENAI_API_BASE")
        llm_model_name = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
        kwargs = {
            "model": llm_model_name,
            "temperature": temperature,
            "openai_api_key": api_key,
        }
        if base_url:
            kwargs["openai_api_base"] = base_url.rstrip("/")
        return ChatOpenAI(**kwargs)

    if ChatGoogleGenerativeAI is None:
        raise ImportError(
            "langchain-google-genai is required when LLM_PROVIDER='google'. "
            "Install it with `pip install langchain-google-genai google-generativeai`."
        )
    llm_model_name = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash-latest")
    return ChatGoogleGenerativeAI(
        model=llm_model_name,
        convert_system_message_to_human=True,
        temperature=temperature,
    )
