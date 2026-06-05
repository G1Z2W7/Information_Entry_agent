from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.api.chat import agent_service
from app.agent.models import Contact, DistributorStatus, MainInfo, SessionStage, SessionState
from app.main import app


@dataclass
class FakeResponse:
    content: object


def _extract_user_message(prompt: str) -> str:
    marker = "本轮用户输入："
    if marker not in prompt:
        return prompt
    return prompt.split(marker, maxsplit=1)[1].strip()


class FakeIntentLLMClient:
    def invoke(self, prompt: str) -> FakeResponse:
        user_message = _extract_user_message(prompt)
        if user_message == "你好":
            return FakeResponse(content='{"intent":"greeting"}')
        if user_message == "你是谁":
            return FakeResponse(content='{"intent":"identity_query"}')
        if user_message == "你能干什么":
            return FakeResponse(content='{"intent":"help_query"}')
        return FakeResponse(content='{"intent":"task_input"}')


class FakeExtractionLLMClient:
    def invoke(self, prompt: str) -> FakeResponse:
        user_message = _extract_user_message(prompt)
        if "HZ001" in user_message and "13800138000" in user_message:
            return FakeResponse(
                content='{"main_info":{"erpCode":"HZ001","customerMobile":"13800138000"}}'
            )
        if (
            "zhixing@example.com" in user_message
            and "王磊" in user_message
            and "13900001111" in user_message
        ):
            return FakeResponse(
                content=(
                    '{"main_info":{"customerEmail":"zhixing@example.com"},'
                    '"contacts":[{"contactName":"王磊","position":"老板","mobile":"13900001111","wechat":"same_as_mobile"}]}'
                )
            )
        return FakeResponse(content="{}")



def setup_function() -> None:
    agent_service.reset()


@pytest.fixture
def client() -> TestClient:
    agent_service.llm_client = FakeExtractionLLMClient()
    agent_service.intent_llm_client = FakeIntentLLMClient()
    with TestClient(app) as test_client:
        yield test_client
    agent_service.llm_client = None
    agent_service.intent_llm_client = None


def test_health_endpoints_return_ok(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    api_response = client.get("/api/agent/distributors/health")
    assert api_response.status_code == 200
    assert api_response.json() == {"status": "ok"}


def test_field_options_endpoint_returns_supported_enum_fields(client: TestClient) -> None:
    response = client.get("/api/agent/distributors/field-options")

    assert response.status_code == 200
    payload = response.json()
    assert "main_info.mainCategory" in payload["fields"]
    assert payload["fields"]["main_info.mainCategory"]["label"] == "主营品类"
    assert payload["fields"]["main_info.status"]["options"][0]["value"] == "normal"


def test_address_resolve_endpoint_returns_placeholder_response(client: TestClient) -> None:
    response = client.post(
        "/api/agent/distributors/address/resolve",
        json={
            "session_id": "session-api-address-1",
            "full_address": "浙江省杭州市西湖区文三路18号",
            "current_location": {
                "latitude": 30.2741,
                "longitude": 120.1551,
                "accuracyMeters": 18.5,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["resolution_status"] == "not_implemented"
    assert "当前未接入真实定位/地理编码服务" in payload["message"]
    assert payload["current_location"]["latitude"] == 30.2741
    assert payload["full_address"] == "浙江省杭州市西湖区文三路18号"


def test_realtime_asr_websocket_endpoint_streams_proxy_events(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_bridge(websocket) -> None:
        await websocket.send_json({"type": "ready"})
        probe = await websocket.receive_json()
        assert probe["type"] == "probe"
        await websocket.send_json({"type": "finished"})

    monkeypatch.setattr("app.api.chat.bridge_qwen_realtime_asr", fake_bridge)

    with client.websocket_connect("/api/agent/distributors/asr/realtime") as websocket:
        assert websocket.receive_json() == {"type": "ready"}
        websocket.send_json({"type": "probe"})
        assert websocket.receive_json() == {"type": "finished"}


def test_realtime_asr_websocket_endpoint_reports_runtime_errors(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_bridge(_websocket) -> None:
        raise RuntimeError("ASR_API_KEY is not configured.")

    monkeypatch.setattr("app.api.chat.bridge_qwen_realtime_asr", fake_bridge)

    with client.websocket_connect("/api/agent/distributors/asr/realtime") as websocket:
        payload = websocket.receive_json()

    assert payload["type"] == "error"
    assert payload["message"] == "ASR_API_KEY is not configured."


def test_chat_endpoint_returns_reply_and_missing_fields(client: TestClient) -> None:
    response = client.post(
        "/api/agent/distributors/chat",
        json={
            "session_id": "session-api-1",
            "message": "新增经销商，ERP编码是HZ001，客户手机号是13800138000。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "reply" in payload
    assert payload["stage"] == "collecting"
    assert "main_info.customerEmail" in payload["missing_required_fields"]
    assert payload["state_summary"]["main_info"]["erpCode"] == "HZ001"
    assert "按类别补充这些信息" in payload["reply"]
    assert "主体信息（必填）" in payload["reply"]


def test_chat_endpoint_persists_state_across_turns(client: TestClient) -> None:
    first_response = client.post(
        "/api/agent/distributors/chat",
        json={
            "session_id": "session-api-2",
            "message": "新增经销商，ERP编码是HZ001，客户手机号是13800138000。",
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/agent/distributors/chat",
        json={
            "session_id": "session-api-2",
            "message": "客户邮箱是zhixing@example.com，老板王磊，电话13900001111，微信同手机号。",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["state_summary"]["main_info"]["erpCode"] == "HZ001"
    assert payload["state_summary"]["main_info"]["customerEmail"] == "zhixing@example.com"
    assert payload["state_summary"]["contacts"][0]["contactName"] == "王磊"


def test_fields_endpoint_updates_state_with_structured_patch(client: TestClient) -> None:
    response = client.patch(
        "/api/agent/distributors/fields",
        json={
            "session_id": "session-api-fields-1",
            "patch": {
                "main_info": {
                    "mainCategory": "汽配",
                    "mainCategoryGrade": "国内主流品牌为主",
                    "businessType": "批发B2B",
                    "cooperationStatus": "稳定合作｜已签约",
                    "status": "normal",
                    "providePoints": False,
                }
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["state_summary"]["main_info"]["mainCategory"] == "汽配"
    assert payload["state_summary"]["main_info"]["providePoints"] is False
    assert payload["state_summary"]["main_info"]["providePointsRatio"] == 0.0
    assert "main_info.mainCategory" not in payload["missing_required_fields"]
    assert "已更新" in payload["reply"]


def test_fields_endpoint_rejects_invalid_structured_value(client: TestClient) -> None:
    response = client.patch(
        "/api/agent/distributors/fields",
        json={
            "session_id": "session-api-fields-2",
            "patch": {
                "main_info": {
                    "status": "active",
                }
            },
        },
    )

    assert response.status_code == 422


def test_chat_and_fields_share_same_session_state(client: TestClient) -> None:
    first_response = client.post(
        "/api/agent/distributors/chat",
        json={
            "session_id": "session-api-mixed-1",
            "message": "新增经销商，ERP编码是HZ001，客户手机号是13800138000。",
        },
    )
    assert first_response.status_code == 200

    second_response = client.patch(
        "/api/agent/distributors/fields",
        json={
            "session_id": "session-api-mixed-1",
            "patch": {
                "main_info": {
                    "mainCategory": "汽配",
                    "mainCategoryGrade": "国内主流品牌为主",
                    "businessType": "批发B2B",
                    "cooperationStatus": "稳定合作｜已签约",
                    "status": "normal",
                    "providePoints": False,
                }
            },
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["state_summary"]["main_info"]["erpCode"] == "HZ001"
    assert payload["state_summary"]["main_info"]["customerMobile"] == "13800138000"
    assert payload["state_summary"]["main_info"]["mainCategory"] == "汽配"


def test_chat_endpoint_rejects_invalid_body(client: TestClient) -> None:
    response = client.post(
        "/api/agent/distributors/chat",
        json={"session_id": "missing-message"},
    )

    assert response.status_code == 422


def test_chat_endpoint_fails_closed_when_deepseek_not_configured(monkeypatch) -> None:
    agent_service.reset()
    agent_service.llm_client = None
    agent_service.intent_llm_client = None
    monkeypatch.setenv("LLM_EXTRACTION_ENABLED", "true")
    monkeypatch.delenv("DS_API_KEY", raising=False)
    monkeypatch.delenv("DS_MODEL", raising=False)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/agent/distributors/chat",
            json={
                "session_id": "session-api-no-deepseek",
                "message": "新增经销商，ERP编码是HZ001，客户手机号是13800138000。",
            },
        )

    assert response.status_code == 503
    assert "DeepSeek extraction is required" in response.json()["detail"]


def test_chat_endpoint_confirms_and_creates_when_ready(client: TestClient) -> None:
    ready_state = SessionState(
        session_id="session-api-create-1",
        stage=SessionStage.AWAITING_CONFIRMATION,
        awaiting_confirmation=True,
        creation_ready=True,
        main_info=MainInfo(
            distributorName="智行汽车",
            customerEmail="zhixing@example.com",
            customerMobile="13800138000",
            belongRegion="华东",
            erpCode="HZ001",
            status=DistributorStatus.NORMAL,
            providePoints=False,
            mainCategory="汽配",
            mainCategoryGrade="国内主流品牌为主",
            businessType="批发B2B",
            cooperationStatus="稳定合作｜已签约",
        ),
        contacts=[
            Contact(
                contactName="王磊",
                position="老板",
                mobile="13900001111",
                wechat="same_as_mobile",
                isPrimary=True,
            )
        ],
    )
    agent_service.store.save(ready_state)

    response = client.post(
        "/api/agent/distributors/chat",
        json={
            "session_id": "session-api-create-1",
            "message": "确认创建",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["stage"] == "completed"
    assert payload["created_result"]["success"] is True
    assert payload["created_result"]["distributorName"] == "智行汽车"


def test_chat_endpoint_guides_greeting_instead_of_mechanical_prompt(client: TestClient) -> None:
    response = client.post(
        "/api/agent/distributors/chat",
        json={
            "session_id": "session-api-guidance-1",
            "message": "你好",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["stage"] == "collecting"
    assert "新增经销商信息收集助手" in payload["reply"]
    assert "经销商名称" in payload["reply"]
    assert "客户手机号" in payload["reply"]


def test_chat_endpoint_guides_identity_question_instead_of_mechanical_prompt(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/agent/distributors/chat",
        json={
            "session_id": "session-api-guidance-2",
            "message": "你是谁",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "我是新增经销商信息收集助手" in payload["reply"]
    assert "手机号" in payload["reply"]


def test_chat_endpoint_guides_ability_question_instead_of_mechanical_prompt(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/agent/distributors/chat",
        json={
            "session_id": "session-api-guidance-3",
            "message": "你能干什么",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "新增经销商信息收集助手" in payload["reply"] or "我会帮你分步收集新增经销商必填信息" in payload["reply"]
    assert "经销商名称" in payload["reply"]
