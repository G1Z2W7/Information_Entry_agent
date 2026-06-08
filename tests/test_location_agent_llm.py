from __future__ import annotations

from dataclasses import dataclass

from app.location_agent.llm import DeepSeekLocationAnalyzer
from app.location_agent.models import (
    CurrentCoordinates,
    LocationDetail,
    LocationAgentRequest,
    LocationState,
    LocationStatePhase,
)


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


def test_deepseek_location_analyzer_parses_structured_json() -> None:
    client = FakeLLMClient(
        """
        {
          "raw_address_text": "杭洲市西胡区文三路18号",
          "address_type": "precise",
          "corrected_queries": [
            "杭州市西湖区文三路18号",
            "浙江省杭州市西湖区文三路18号"
          ],
          "location_detail": {
            "raw_text": "5楼501",
            "detail_type": "unit_detail"
          },
          "admin_hints": {
            "city_name": "杭州市",
            "district_name": "西湖区"
          },
          "missing_parts": [],
          "next_step": "search"
        }
        """
    )
    analyzer = DeepSeekLocationAnalyzer(llm_client=client)

    analysis = analyzer.analyze(
        LocationAgentRequest(
            session_id="location-llm-1",
            user_message="杭洲市西胡区文三路18号",
        )
    )

    assert analysis.address_type == "precise"
    assert analysis.corrected_queries == [
        "杭州市西湖区文三路18号",
        "浙江省杭州市西湖区文三路18号",
    ]
    assert analysis.location_detail == LocationDetail(raw_text="5楼501", detail_type="unit_detail")
    assert analysis.admin_hints is not None
    assert analysis.admin_hints.city_name == "杭州市"
    assert "位置解析 Agent" in client.prompts[0]
    assert "杭洲市西胡区文三路18号" in client.prompts[0]


def test_deepseek_location_analyzer_handles_code_fence_and_state_context() -> None:
    client = FakeLLMClient(
        """```json
        {
          "raw_address_text": "苏州园区那边门店",
          "address_type": "fuzzy",
          "corrected_queries": [],
          "admin_hints": {
            "city_name": "苏州市"
          },
          "missing_parts": ["路名", "门牌号"],
          "next_step": "need_more_detail"
        }
        ```"""
    )
    analyzer = DeepSeekLocationAnalyzer(llm_client=client)

    analysis = analyzer.analyze(
        LocationAgentRequest(
            session_id="location-llm-2",
            user_message="苏州园区那边门店",
            current_coordinates=CurrentCoordinates(latitude=31.3, longitude=120.6),
            state=LocationState(phase=LocationStatePhase.AWAITING_MORE_DETAIL),
        )
    )

    assert analysis.address_type == "fuzzy"
    assert analysis.missing_parts == ["路名", "门牌号"]
    assert analysis.next_step == "need_more_detail"
    assert "awaiting_more_detail" in client.prompts[0]
    assert "31.3" in client.prompts[0]


def test_deepseek_location_analyzer_returns_use_current_for_empty_message_without_llm_call() -> None:
    client = FakeLLMClient('{"address_type":"precise"}')
    analyzer = DeepSeekLocationAnalyzer(llm_client=client)

    analysis = analyzer.analyze(LocationAgentRequest(session_id="location-llm-3", user_message=""))

    assert analysis.address_type == "unknown"
    assert analysis.next_step == "use_current"
    assert client.prompts == []


def test_deepseek_location_analyzer_falls_back_to_unknown_on_invalid_json() -> None:
    client = FakeLLMClient("not json")
    analyzer = DeepSeekLocationAnalyzer(llm_client=client)

    analysis = analyzer.analyze(
        LocationAgentRequest(session_id="location-llm-4", user_message="这边门店")
    )

    assert analysis.address_type == "unknown"
    assert analysis.next_step == "need_manual_input"
