from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_distributor_agent_playground_route_returns_html() -> None:
    with TestClient(app) as client:
        response = client.get("/playground/distributor-agent")

    assert response.status_code == 200
    assert "经销商 Agent 联调页" in response.text
    assert "/api/agent/distributors/chat" in response.text
    assert "/api/agent/distributors/asr/realtime" in response.text
    assert "快捷补充" in response.text
    assert "开始录音" in response.text
    assert "停止录音" in response.text
    assert "语音会实时转写到输入框" in response.text


def test_location_agent_playground_route_returns_html() -> None:
    with TestClient(app) as client:
        response = client.get("/playground/location-agent")

    assert response.status_code == 200
    assert "位置解析 Agent 联调页" in response.text
    assert "/api/location-agent/nearby" in response.text
    assert "/api/location-agent/search" in response.text
    assert "/api/location-agent/resolve" in response.text
    assert "获取当前位置" in response.text
