from __future__ import annotations

from dataclasses import dataclass

from app.agent.extractor import extract_llm_incremental_patch
from app.agent.models import Contact, MainInfo, SessionState
from app.agent.prompts import build_incremental_extraction_prompt


@dataclass
class FakeResponse:
    content: object


class FakeLLMClient:
    def __init__(self, response_content: object) -> None:
        self.response_content = response_content
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> FakeResponse:
        self.prompts.append(prompt)
        return FakeResponse(content=self.response_content)


def test_llm_extractor_parses_structured_json_patch() -> None:
    state = SessionState(
        session_id="session-llm-1",
        main_info=MainInfo(distributorName="智行汽车"),
        contacts=[Contact(contactName="王磊", position="老板")],
        missing_required_fields=["main_info.mainCategory", "main_info.businessType"],
    )
    client = FakeLLMClient(
        """
        {
          "main_info": {
            "mainCategory": "汽配",
            "businessType": "批发B2B"
          }
        }
        """
    )

    patch = extract_llm_incremental_patch("他们主要做汽配批发。", state, llm_client=client)

    assert patch == {
        "main_info": {
            "mainCategory": "汽配",
            "businessType": "批发B2B",
        }
    }
    assert "当前已收集状态摘要" in client.prompts[0]
    assert "他们主要做汽配批发。" in client.prompts[0]


def test_llm_extractor_handles_code_fence_and_contact_update() -> None:
    state = SessionState(session_id="session-llm-2")
    client = FakeLLMClient(
        """```json
        {
          "contacts": [
            {
              "contactName": "王磊",
              "position": "老板",
              "mobile": "13900001111",
              "wechat": "same_as_mobile"
            }
          ]
        }
        ```"""
    )

    patch = extract_llm_incremental_patch("老板叫王磊，微信同手机号。", state, llm_client=client)

    assert patch["contacts"][0]["contactName"] == "王磊"
    assert patch["contacts"][0]["wechat"] == "same_as_mobile"


def test_llm_extractor_returns_empty_patch_on_invalid_json() -> None:
    state = SessionState(session_id="session-llm-3")
    client = FakeLLMClient("not json")

    patch = extract_llm_incremental_patch("手机号改成13800138000", state, llm_client=client)

    assert patch == {}


def test_incremental_prompt_emphasizes_modification_only_outputs_changed_fields() -> None:
    prompt = build_incremental_extraction_prompt(
        state_summary={"contacts": [{"contactName": "王磊", "mobile": "13900001111"}]},
        missing_fields=[],
        user_message="王磊电话改成18800000001",
    )

    assert "只输出本轮被修改的字段" in prompt
    assert "不要新增重复联系人" in prompt
    assert "不要新增重复场地" in prompt
    assert "不要因为补了一个新地址就新建场地" in prompt
    assert "provinceName" in prompt
    assert "如果用户原话里明确出现了省、市、区/县" in prompt
    assert "留给后续地址解析接口补充" in prompt
