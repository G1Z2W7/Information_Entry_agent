from __future__ import annotations

import os
from enum import Enum


class RuntimeSelectionError(RuntimeError):
    pass


class RuntimeMode(str, Enum):
    LEGACY = "legacy"
    LANGGRAPH = "langgraph"


def get_runtime_mode(env_name: str) -> RuntimeMode:
    raw_value = os.getenv(env_name, RuntimeMode.LEGACY.value).strip().lower()
    if not raw_value:
        raw_value = RuntimeMode.LEGACY.value
    try:
        return RuntimeMode(raw_value)
    except ValueError as exc:
        raise RuntimeSelectionError(
            f"Unsupported runtime mode for {env_name}: {raw_value}"
        ) from exc
