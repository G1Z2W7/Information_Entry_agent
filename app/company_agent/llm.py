from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from app.company_agent.models import CompanyCandidate
from app.company_agent.prompts import (
    CROSS_VALIDATE_SYSTEM_PROMPT,
    CROSS_VALIDATE_USER_PROMPT,
    WEB_SEARCH_PROMPT,
)


def _build_llm_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    return OpenAI(api_key=api_key, base_url=base_url)


def _parse_llm_json(response: Any) -> dict[str, Any]:
    content = response.choices[0].message.content
    if isinstance(content, str):
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(content)
    return {}


def cross_validate_with_web_search(
    user_input: str,
    qixin_candidates: list[CompanyCandidate],
) -> dict[str, Any]:
    client = _build_llm_client()
    qixin_text = "\n".join(
        f"- {c.company_name}" for c in qixin_candidates
    )
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": CROSS_VALIDATE_SYSTEM_PROMPT},
            {"role": "user", "content": CROSS_VALIDATE_USER_PROMPT.format(
                user_input=user_input,
                qixin_candidates=qixin_text,
            )},
        ],
        temperature=0.1,
    )
    return _parse_llm_json(response)


def web_search_candidates(user_input: str) -> dict[str, Any]:
    client = _build_llm_client()
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": WEB_SEARCH_PROMPT},
            {"role": "user", "content": f'请搜索"{user_input}"并返回可能的匹配公司'},
        ],
        temperature=0.1,
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
