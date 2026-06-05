from __future__ import annotations

from dataclasses import dataclass

from app.agent.extractor import classify_llm_intent
from app.agent.models import SessionState
from app.agent.service import AgentService


@dataclass
class FakeResponse:
    content: object


class FakeIntentLLMClient:
    def __init__(self, response_content: object) -> None:
        self.response_content = response_content
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> FakeResponse:
        self.prompts.append(prompt)
        return FakeResponse(content=self.response_content)


def test_classify_llm_intent_parses_json_result() -> None:
    state = SessionState(session_id="intent-1")
    client = FakeIntentLLMClient('{"intent": "help_query"}')

    intent = classify_llm_intent("你能干什么", state, llm_client=client)

    assert intent == "help_query"
    assert "你能干什么" in client.prompts[0]
    assert "允许的 intent" in client.prompts[0]


def test_classify_llm_intent_parses_raw_label_result() -> None:
    state = SessionState(session_id="intent-2")
    client = FakeIntentLLMClient("identity_query")

    intent = classify_llm_intent("你是谁", state, llm_client=client)

    assert intent == "identity_query"


def test_classify_llm_intent_returns_none_for_invalid_output() -> None:
    state = SessionState(session_id="intent-3")
    client = FakeIntentLLMClient("something else")

    intent = classify_llm_intent("你好", state, llm_client=client)

    assert intent is None


def test_agent_service_prefers_llm_intent_for_ability_question(
    monkeypatch,
) -> None:
    monkeypatch.setenv("LLM_EXTRACTION_ENABLED", "false")
    monkeypatch.setenv("LLM_INTENT_ENABLED", "true")
    service = AgentService(intent_llm_client=FakeIntentLLMClient('{"intent": "help_query"}'))

    response = service.process_chat("intent-4", "你能干什么")

    assert "新增经销商信息收集助手" in response.reply or "我会帮你分步收集新增经销商必填信息" in response.reply
    assert "经销商名称" in response.reply
