from __future__ import annotations

import json
import os
from typing import Any

from langchain_openai import ChatOpenAI

from app.company_agent.models import CompanyCandidate
from app.company_agent.prompts import (
    CROSS_VALIDATE_SYSTEM_PROMPT,
    CROSS_VALIDATE_USER_PROMPT,
    DISCOVER_SYSTEM_PROMPT,
    DISCOVER_USER_PROMPT,
    WEB_SEARCH_PROMPT,
)


def _build_qwen_web_client() -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv(
        "OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    model = os.getenv("OPENAI_MODEL", "qwen-plus")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.0,
        timeout=60,
        max_retries=0,
    )


def _parse_llm_json(response: Any) -> dict[str, Any]:
    content = response.content if hasattr(response, "content") else ""
    if isinstance(content, str):
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}
    return {}


def cross_validate_with_web_search(
    user_input: str,
    qixin_candidates: list[CompanyCandidate],
) -> dict[str, Any]:
    client = _build_qwen_web_client()
    qixin_text = "\n".join(
        f"- {c.company_name}" for c in qixin_candidates
    )
    response = client.invoke(
        [
            {"role": "system", "content": CROSS_VALIDATE_SYSTEM_PROMPT},
            {"role": "user", "content": CROSS_VALIDATE_USER_PROMPT.format(
                user_input=user_input,
                qixin_candidates=qixin_text,
            )},
        ],
        extra_body={"enable_search": True},
    )
    return _parse_llm_json(response)


def discover_candidates_from_web_search(user_input: str) -> dict[str, Any]:
    client = _build_qwen_web_client()
    response = client.invoke(
        [
            {"role": "system", "content": DISCOVER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": DISCOVER_USER_PROMPT.format(user_input=user_input),
            },
        ],
        extra_body={"enable_search": True},
    )
    return _parse_llm_json(response)


def web_search_candidates(user_input: str) -> dict[str, Any]:
    client = _build_qwen_web_client()
    response = client.invoke(
        [
            {"role": "system", "content": WEB_SEARCH_PROMPT},
            {"role": "user", "content": f'请搜索"{user_input}"并返回可能的匹配公司'},
        ],
        extra_body={"enable_search": True},
    )
    return _parse_llm_json(response)


def build_candidates_from_llm_result(
    result: dict[str, Any],
    default_source: str = "web_search",
) -> list[CompanyCandidate]:
    candidates: list[CompanyCandidate] = []
    for idx, item in enumerate(result.get("candidates", [])):
        candidates.append(CompanyCandidate(
            candidate_id=f"{default_source}_{idx}",
            company_name=item.get("company_name", ""),
            source=item.get("source", default_source),
            match_confidence=item.get("match_confidence", "medium"),
            match_reason=item.get("match_reason"),
        ))
    return candidates
