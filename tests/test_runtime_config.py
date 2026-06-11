from __future__ import annotations

import pytest

from app.agent.runtime_config import RuntimeMode, get_runtime_mode


def test_get_runtime_mode_defaults_to_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENT_RUNTIME", raising=False)

    assert get_runtime_mode("AGENT_RUNTIME") is RuntimeMode.LEGACY


def test_get_runtime_mode_treats_blank_value_as_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_RUNTIME", "   ")

    assert get_runtime_mode("AGENT_RUNTIME") is RuntimeMode.LEGACY


def test_get_runtime_mode_reads_langgraph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_RUNTIME", "  LANGGRAPH ")

    assert get_runtime_mode("AGENT_RUNTIME") is RuntimeMode.LANGGRAPH


def test_get_runtime_mode_rejects_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_RUNTIME", "invalid")

    with pytest.raises(RuntimeError, match="Unsupported runtime mode for AGENT_RUNTIME: invalid"):
        get_runtime_mode("AGENT_RUNTIME")
