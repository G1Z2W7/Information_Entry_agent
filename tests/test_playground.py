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
    assert "支持语音输入" in response.text
    assert "开始/停止录音" in response.text
    assert "输入消息，或点击麦克风语音输入" in response.text
    assert "请使用 HTTPS 或 localhost 打开页面" in response.text
    assert "当前浏览器不支持麦克风采集" in response.text
