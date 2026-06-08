from __future__ import annotations

import json
import os
import re
from typing import Any

from langchain_openai import ChatOpenAI

from app.location_agent.models import (
    LocationAdminHints,
    LocationDetail,
    LocationAgentRequest,
    LocationAnalysis,
)
from app.location_agent.prompts import build_location_analysis_prompt

LOCATION_NEXT_STEPS = {
    "search",
    "use_current",
    "need_more_detail",
    "need_manual_input",
}
LOCATION_ADDRESS_TYPES = {"precise", "fuzzy", "unknown"}


class DeepSeekLocationAnalyzer:
    def __init__(self, *, llm_client: Any | None = None) -> None:
        self.llm_client = llm_client

    def analyze(self, request: LocationAgentRequest) -> LocationAnalysis:
        message = (request.user_message or "").strip()
        if not message:
            return LocationAnalysis(
                raw_address_text=None,
                address_type="unknown",
                corrected_queries=[],
                location_detail=None,
                admin_hints=None,
                missing_parts=[],
                next_step="use_current",
            )

        prompt = build_location_analysis_prompt(
            user_message=message,
            state_summary=_build_state_summary(request),
            current_coordinates=_build_coordinates_summary(request),
        )
        client = self.llm_client or build_location_llm_client()
        response = client.invoke(prompt)
        parsed = _parse_llm_response_to_json(response)
        if not isinstance(parsed, dict):
            return _unknown_analysis(message)
        return _sanitize_location_analysis(parsed, fallback_text=message)


def build_location_llm_client() -> ChatOpenAI:
    model = _first_env_value(("DS_LOCATION_MODEL", "DS_MODEL"))
    if not model:
        raise RuntimeError("Missing required environment variable: DS_LOCATION_MODEL or DS_MODEL")

    api_key = _require_env("DS_API_KEY")
    base_url = os.getenv("DS_BASE_URL") or None
    temperature = float(os.getenv("DS_TEMPERATURE", os.getenv("OPENAI_TEMPERATURE", "0")))
    max_tokens = int(os.getenv("DS_LOCATION_MAX_TOKENS", os.getenv("LLM_EXTRACTION_MAX_TOKENS", "800")))

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=60,
        max_retries=0,
    )


def _sanitize_location_analysis(parsed: dict[str, Any], *, fallback_text: str) -> LocationAnalysis:
    address_type = parsed.get("address_type")
    if address_type not in LOCATION_ADDRESS_TYPES:
        address_type = "unknown"

    next_step = parsed.get("next_step")
    if next_step not in LOCATION_NEXT_STEPS:
        next_step = "need_manual_input" if address_type != "unknown" else "need_manual_input"

    corrected_queries = [
        value.strip()
        for value in parsed.get("corrected_queries", [])
        if isinstance(value, str) and value.strip()
    ]
    missing_parts = [
        value.strip()
        for value in parsed.get("missing_parts", [])
        if isinstance(value, str) and value.strip()
    ]

    location_detail = None
    raw_location_detail = parsed.get("location_detail")
    if isinstance(raw_location_detail, dict):
        raw_text = _normalize_string(raw_location_detail.get("raw_text"))
        detail_type = _normalize_string(raw_location_detail.get("detail_type"))
        if raw_text and detail_type:
            location_detail = LocationDetail(raw_text=raw_text, detail_type=detail_type)

    admin_hints = None
    raw_admin_hints = parsed.get("admin_hints")
    if isinstance(raw_admin_hints, dict):
        admin_hints = LocationAdminHints(
            province_name=_normalize_string(raw_admin_hints.get("province_name")),
            city_name=_normalize_string(raw_admin_hints.get("city_name")),
            district_name=_normalize_string(raw_admin_hints.get("district_name")),
        )
        if not any(
            (admin_hints.province_name, admin_hints.city_name, admin_hints.district_name)
        ):
            admin_hints = None

    raw_address_text = _normalize_string(parsed.get("raw_address_text")) or fallback_text
    if address_type == "unknown" and next_step == "search":
        next_step = "need_manual_input"

    return LocationAnalysis(
        raw_address_text=raw_address_text,
        address_type=address_type,
        corrected_queries=corrected_queries,
        location_detail=location_detail,
        admin_hints=admin_hints,
        missing_parts=missing_parts,
        next_step=next_step,
    )


def _unknown_analysis(message: str) -> LocationAnalysis:
    return LocationAnalysis(
        raw_address_text=message,
        address_type="unknown",
        corrected_queries=[],
        location_detail=None,
        admin_hints=None,
        missing_parts=[],
        next_step="need_manual_input",
    )


def _build_state_summary(request: LocationAgentRequest) -> dict[str, Any]:
    state = request.state
    if state is None:
        return {"phase": "idle", "candidate_count": 0}
    return {
        "phase": state.phase.value,
        "candidate_count": len(state.candidates),
        "admin_hints": state.admin_hints.model_dump() if state.admin_hints is not None else None,
    }


def _build_coordinates_summary(
    request: LocationAgentRequest,
) -> dict[str, float | None] | None:
    coordinates = request.current_coordinates or (request.state.current_coordinates if request.state else None)
    if coordinates is None:
        return None
    return {
        "latitude": coordinates.latitude,
        "longitude": coordinates.longitude,
        "accuracy_meters": coordinates.accuracy_meters,
    }


def _parse_llm_response_to_json(response: Any) -> Any:
    if isinstance(response, dict):
        return response

    content = getattr(response, "content", response)
    if isinstance(content, dict):
        return content
    if not isinstance(content, (str, list)):
        return {}

    text = _response_to_text(response).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except Exception:
        return {}


def _response_to_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def _normalize_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _require_env(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _first_env_value(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.getenv(name, "")
        if value:
            return value
    return ""
