from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from app.utils.logger import logger

RUNTIME_SETTINGS_PATH = Path(
    os.getenv("SC_RUNTIME_SETTINGS_PATH", "config/runtime_settings.json")
)


def _load_all() -> Dict[str, Any]:
    if not RUNTIME_SETTINGS_PATH.exists():
        return {}
    try:
        with open(RUNTIME_SETTINGS_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("加载运行时配置失败，将使用默认值: %s", exc)
        return {}


def _save_all(payload: Dict[str, Any]) -> None:
    RUNTIME_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RUNTIME_SETTINGS_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def get_llm_settings() -> Dict[str, Any]:
    data = _load_all()
    llm = data.get("llm") or {}
    return llm


def save_llm_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    data = _load_all()
    current = data.get("llm") or {}
    for key, value in updates.items():
        if isinstance(value, str):
            value = value.strip()
        if value in {None, ""}:
            current.pop(key, None)
        else:
            current[key] = value
    data["llm"] = current
    _save_all(data)
    logger.info("LLM 设置已更新: %s", {k: v for k, v in current.items() if k != "api_key"})
    return current
