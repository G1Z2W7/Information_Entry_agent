from __future__ import annotations

import json
import os
import re
from typing import Any

from langchain_openai import ChatOpenAI

from app.agent.models import SessionState
from app.agent.prompts import build_incremental_extraction_prompt, build_intent_classification_prompt

EMAIL_PATTERN = re.compile(
    r"(?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
)
MOBILE_PATTERN = re.compile(r"(?<!\d)(?P<mobile>1[3-9]\d{9})(?!\d)")
ERP_PATTERN = re.compile(
    r"(?:ERP编码|erp编码|ERP|erp)\s*(?:编码)?\s*(?:是|为|[:：])?\s*(?P<erp>[A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
DATE_FIELD_PATTERNS = {
    "issueDate": re.compile(
        r"(?:签发日期|签发时间|签发日|签发)\s*(?:是|为|[:：])?\s*(?P<date>(?:\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)|\d{4}-\d{1,2}-\d{1,2})"
    ),
    "expiryDate": re.compile(
        r"(?:到期时间|到期日期|有效期截止日期|有效期截止日|截止日期|到期日)\s*(?:是|为|[:：])?\s*(?P<date>(?:\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)|\d{4}-\d{1,2}-\d{1,2})"
    ),
}
DISCOUNT_PATTERN = re.compile(
    r"(?:(?:折扣(?:按|是|为)?|给的是|给|按)\s*)?(?P<discount>\d+(?:\.\d+)?)\s*(?:折|%)"
)
CUSTOMER_EMAIL_PATTERN = re.compile(
    r"(?:客户)?邮箱\s*(?:是|为|[:：])?\s*(?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
    re.IGNORECASE,
)
CUSTOMER_MOBILE_PATTERN = re.compile(
    r"(?:客户)?手机(?:号)?\s*(?:是|为|[:：])?\s*(?P<mobile>1[3-9]\d{9})"
)
POINTS_RATIO_PATTERN = re.compile(
    r"(?:积分比例|积分按)\s*(?:是|为|[:：])?\s*(?P<ratio>\d+(?:\.\d+)?)"
)
POSITION_TOKENS = (
    "老板",
    "总经理",
    "门店负责人",
    "销售负责人",
    "采购",
    "财务",
    "经理",
    "店长",
    "负责人",
)
INTENT_LABELS = {
    "greeting",
    "identity_query",
    "help_query",
    "off_topic",
    "task_input",
    "task_modify",
    "confirm_create",
    "unknown",
}


def extract_rule_based_patch(message: str) -> dict[str, Any]:
    """Extract a deterministic patch from stable text patterns."""
    patch: dict[str, Any] = {}
    main_info = _extract_main_info(message)
    contacts = _extract_contacts(message)

    if main_info:
        patch["main_info"] = main_info
    if contacts:
        patch["contacts"] = contacts

    return patch


def extract_llm_incremental_patch(
    message: str,
    state: SessionState,
    *,
    llm_client: Any | None = None,
) -> dict[str, Any]:
    """Use an LLM to extract semantic fields from the current user turn only."""
    prompt = build_incremental_extraction_prompt(
        state_summary=_build_state_summary(state),
        missing_fields=state.missing_required_fields,
        user_message=message,
    )
    client = llm_client or build_llm_client()
    response = client.invoke(prompt)
    parsed = _parse_llm_response_to_json(response)
    if not isinstance(parsed, dict):
        return {}
    return _sanitize_patch(parsed)


def classify_llm_intent(
    message: str,
    state: SessionState,
    *,
    llm_client: Any | None = None,
) -> str | None:
    """Use an LLM to classify the user turn intent before extraction."""
    prompt = build_intent_classification_prompt(
        state_summary=_build_state_summary(state),
        missing_fields=state.missing_required_fields,
        user_message=message,
    )
    client = llm_client or build_llm_client(
        model_env_names=("DS_INTENT_MODEL", "DS_MODEL"),
        max_tokens_env="LLM_INTENT_MAX_TOKENS",
    )
    response = client.invoke(prompt)
    parsed = _parse_llm_response_to_json(response)
    if isinstance(parsed, dict):
        intent = parsed.get("intent")
        if isinstance(intent, str) and intent in INTENT_LABELS:
            return intent

    raw_text = _response_to_text(response).strip().strip("`")
    if raw_text in INTENT_LABELS:
        return raw_text
    return None


def build_llm_client(
    *,
    model_env_names: tuple[str, ...] = ("DS_MODEL",),
    max_tokens_env: str = "LLM_EXTRACTION_MAX_TOKENS",
) -> ChatOpenAI:
    model = _first_env_value(model_env_names)
    if not model:
        raise RuntimeError(
            f"Missing required environment variable from candidates: {', '.join(model_env_names)}"
        )
    api_key = _require_env("DS_API_KEY")
    base_url = os.getenv("DS_BASE_URL") or None
    temperature = float(os.getenv("DS_TEMPERATURE", os.getenv("OPENAI_TEMPERATURE", "0")))
    max_tokens = int(
        os.getenv(max_tokens_env, os.getenv("LLM_EXTRACTION_MAX_TOKENS", "800"))
    )

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=60,
        max_retries=0,
    )


def _extract_main_info(message: str) -> dict[str, Any]:
    main_info: dict[str, Any] = {}

    customer_email_match = CUSTOMER_EMAIL_PATTERN.search(message)
    if customer_email_match:
        main_info["customerEmail"] = customer_email_match.group("email")
    else:
        first_email = EMAIL_PATTERN.search(message)
        if first_email:
            main_info["customerEmail"] = first_email.group("email")

    customer_mobile_match = CUSTOMER_MOBILE_PATTERN.search(message)
    if customer_mobile_match:
        main_info["customerMobile"] = customer_mobile_match.group("mobile")

    erp_match = ERP_PATTERN.search(message)
    if erp_match:
        main_info["erpCode"] = erp_match.group("erp")

    discount_match = DISCOUNT_PATTERN.search(message)
    if discount_match:
        raw_discount = discount_match.group("discount")
        normalized_discount = _normalize_discount(raw_discount, discount_match.group(0))
        if normalized_discount is not None:
            main_info["discount"] = normalized_discount

    for field_name, pattern in DATE_FIELD_PATTERNS.items():
        date_match = pattern.search(message)
        if date_match:
            normalized_date = _normalize_date(date_match.group("date"))
            if normalized_date:
                main_info[field_name] = normalized_date

    if re.search(r"(?:不发积分|不给积分|不积分)", message):
        main_info["providePoints"] = False
        main_info["providePointsRatio"] = 0.0
    elif re.search(r"(?:发积分|给积分)", message):
        main_info["providePoints"] = True

    points_ratio_match = POINTS_RATIO_PATTERN.search(message)
    if points_ratio_match:
        main_info["providePointsRatio"] = float(points_ratio_match.group("ratio"))
    elif "双倍积分" in message:
        main_info["providePointsRatio"] = 2.0

    if re.search(r"(?:状态)?(?:正常|启用)", message):
        main_info["status"] = "normal"
    elif re.search(r"(?:状态)?(?:禁用|关闭)", message):
        main_info["status"] = "disabled"

    if re.search(r"二级经销商", message):
        main_info["distributorLevel"] = 2
    elif re.search(r"一级经销商", message):
        main_info["distributorLevel"] = 1

    return main_info


def _build_state_summary(state: SessionState) -> dict[str, Any]:
    return {
        "main_info": {
            key: value
            for key, value in state.main_info.model_dump().items()
            if value is not None and value != ""
        },
        "contacts": [
            {
                key: value
                for key, value in contact.model_dump().items()
                if value is not None and value != ""
            }
            for contact in state.contacts
        ],
        "sites": [
            {
                key: value
                for key, value in site.model_dump().items()
                if value is not None and value != ""
            }
            for site in state.sites
        ],
    }


def _extract_contacts(message: str) -> list[dict[str, Any]]:
    contacts: list[dict[str, Any]] = []
    clauses = _split_clauses(message)

    for clause in clauses:
        if not _looks_like_contact_clause(clause):
            continue

        position, contact_name = _extract_position_and_name(clause)
        mobile_match = MOBILE_PATTERN.search(clause)
        wechat_value = _extract_wechat(clause)
        is_primary = bool(re.search(r"(?:主联系人|主要联系)", clause))

        contact: dict[str, Any] = {}
        if contact_name:
            contact["contactName"] = contact_name
        if position:
            contact["position"] = position
        if mobile_match:
            contact["mobile"] = mobile_match.group("mobile")
        if wechat_value:
            contact["wechat"] = wechat_value
        if is_primary:
            contact["isPrimary"] = True

        if contact:
            contacts.append(contact)

    return contacts


def _split_clauses(message: str) -> list[str]:
    return [part.strip() for part in re.split(r"[；;。]", message) if part.strip()]


def _looks_like_contact_clause(clause: str) -> bool:
    if "联系人" in clause or "电话" in clause or "微信" in clause:
        return True
    return any(token in clause for token in POSITION_TOKENS)


def _extract_position_and_name(clause: str) -> tuple[str | None, str | None]:
    for position in POSITION_TOKENS:
        pattern = re.compile(rf"{re.escape(position)}(?P<name>[\u4e00-\u9fa5]{{1,6}})")
        match = pattern.search(clause)
        if match:
            return position, match.group("name")

    contact_name_match = re.search(r"联系人(?:是|叫)?(?P<name>[\u4e00-\u9fa5]{2,6})", clause)
    if contact_name_match:
        return None, contact_name_match.group("name")

    return None, None


def _extract_wechat(clause: str) -> str | None:
    if re.search(r"微信(?:同手机号|同手机|就是电话|就是手机号)", clause):
        return "same_as_mobile"

    wechat_match = re.search(
        r"微信(?:号)?\s*(?:是|为|[:：])?\s*(?P<wechat>[A-Za-z0-9_\-\u4e00-\u9fa5]+)",
        clause,
    )
    if not wechat_match:
        return None

    candidate = wechat_match.group("wechat")
    if candidate in {"同手机号", "同手机", "就是电话", "就是手机号"}:
        return "same_as_mobile"
    return candidate


def _normalize_discount(raw_value: str, raw_text: str) -> float | None:
    try:
        value = float(raw_value)
    except ValueError:
        return None

    if "%" in raw_text:
        return round(value / 100, 4)
    if "折" in raw_text:
        divisor = 100 if value >= 10 else 10
        return round(value / divisor, 4)
    return round(value, 4)


def _normalize_date(raw_date: str) -> str | None:
    date_match = re.search(
        r"(?P<year>\d{4})[-/年](?P<month>\d{1,2})[-/月](?P<day>\d{1,2})日?",
        raw_date,
    )
    if not date_match:
        return None

    year = int(date_match.group("year"))
    month = int(date_match.group("month"))
    day = int(date_match.group("day"))
    return f"{year:04d}-{month:02d}-{day:02d}"


def _parse_llm_response_to_json(response: Any) -> Any:
    if isinstance(response, dict):
        return response

    content = getattr(response, "content", response)
    if isinstance(content, dict):
        return content

    if not isinstance(content, (str, list)):
        return {}

    content = _response_to_text(response).strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

    try:
        return json.loads(content)
    except Exception:
        return {}


def _sanitize_patch(parsed: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}

    if isinstance(parsed.get("main_info"), dict):
        main_info = {
            key: value
            for key, value in parsed["main_info"].items()
            if value is not None and value != ""
        }
        if main_info:
            patch["main_info"] = main_info

    if isinstance(parsed.get("contacts"), list):
        contacts = []
        for item in parsed["contacts"]:
            if not isinstance(item, dict):
                continue
            contact = {
                key: value for key, value in item.items() if value is not None and value != ""
            }
            if contact:
                contacts.append(contact)
        if contacts:
            patch["contacts"] = contacts

    if isinstance(parsed.get("sites"), list):
        sites = []
        for item in parsed["sites"]:
            if not isinstance(item, dict):
                continue
            site = {
                key: value for key, value in item.items() if value is not None and value != ""
            }
            if site:
                sites.append(site)
        if sites:
            patch["sites"] = sites

    return patch


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
