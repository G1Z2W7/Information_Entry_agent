from __future__ import annotations

import re

from app.agent.constants import REQUIRED_VALIDATION_PATHS
from app.agent.models import DialogAction, NextActionType, SessionStage, SessionState


FIELD_LABELS = {
    "main_info.distributorName": "经销商名称",
    "main_info.distributorLevel": "经销商等级",
    "main_info.parentDistributorName": "上级经销商名称",
    "main_info.customerEmail": "客户邮箱",
    "main_info.customerMobile": "客户手机号",
    "main_info.belongRegion": "所属区域",
    "main_info.erpCode": "关联ERP编码",
    "main_info.status": "经销商状态",
    "main_info.providePoints": "是否发放积分",
    "main_info.providePointsRatio": "积分发放比例",
    "main_info.mainCategory": "主营品类",
    "main_info.mainCategoryGrade": "主营品类档次",
    "main_info.businessType": "经营类型",
    "main_info.cooperationStatus": "合作状态",
    "contacts[0].contactName": "联系人姓名",
    "contacts[0].position": "联系人职位",
    "contacts[0].mobile": "联系人电话",
    "contacts[0].wechat": "联系人微信",
    "main_info.salesUserName": "所属销售",
    "main_info.salesManagerName": "所属经理",
    "main_info.authorizedRegion": "授权区域",
    "main_info.issueDate": "签发日期",
    "main_info.expiryDate": "到期日期",
    "main_info.informationSource": "信息来源",
    "main_info.discount": "折扣",
    "main_info.ownBrandDisplay": "自有品牌",
    "main_info.competitorBrandDisplay": "竞品品牌",
    "contacts[0].remark": "联系人备注",
    "sites[0].siteType": "场地类型",
    "sites[0].siteTypeName": "场地名称",
    "sites[0].siteSubType": "场地子类型",
    "sites[0].hasStore": "是否门店",
    "sites[0].storeAreaRange": "门店面积",
    "sites[0].fullAddress": "详细地址",
    "sites[0].provinceName": "省份",
    "sites[0].cityName": "城市",
    "sites[0].districtName": "区县",
}

MISSING_FIELD_PRIORITY = [
    "main_info.distributorName",
    "main_info.customerMobile",
    "main_info.customerEmail",
    "main_info.erpCode",
    "main_info.belongRegion",
    "main_info.mainCategory",
    "main_info.mainCategoryGrade",
    "main_info.businessType",
    "main_info.cooperationStatus",
    "main_info.status",
    "main_info.providePoints",
    "main_info.providePointsRatio",
    "main_info.parentDistributorName",
    "contacts[0].contactName",
    "contacts[0].position",
    "contacts[0].mobile",
    "contacts[0].wechat",
]

CATEGORY_LABELS = {
    "main": "主体信息",
    "business": "经营信息",
    "contact": "联系人信息",
    "site": "场地信息",
}

CATEGORY_ORDER = ["main", "business", "contact", "site"]

OPTIONAL_FIELD_GROUPS = {
    "main": [
        "main_info.salesUserName",
        "main_info.salesManagerName",
        "main_info.authorizedRegion",
        "main_info.issueDate",
        "main_info.expiryDate",
        "main_info.informationSource",
    ],
    "business": [
        "main_info.discount",
        "main_info.ownBrandDisplay",
        "main_info.competitorBrandDisplay",
    ],
    "contact": [
        "contacts[0].remark",
    ],
    "site": [
        "sites[0].siteType",
        "sites[0].siteTypeName",
        "sites[0].siteSubType",
        "sites[0].hasStore",
        "sites[0].storeAreaRange",
        "sites[0].fullAddress",
        "sites[0].provinceName",
        "sites[0].cityName",
        "sites[0].districtName",
    ],
}

GREETING_PATTERN = re.compile(r"^\s*(你好|您好|哈喽|嗨|hello|hi|在吗)\s*[!！。.？?]*\s*$", re.IGNORECASE)
IDENTITY_PATTERN = re.compile(r"(你是谁|你是干嘛的|你是做什么的|你能做什么|你能干什么|你是什么助手)")
HELP_PATTERN = re.compile(r"(怎么填|需要哪些字段|要准备什么|怎么新增|怎么创建|需要准备哪些信息|要填什么)")
OFF_TOPIC_PATTERN = re.compile(r"(天气|讲笑话|股票|写代码|翻译|写邮件|做ppt|做ppt|查新闻|电影)")
TASK_CONTEXT_PATTERN = re.compile(
    r"(经销商|客户|联系人|手机号|手机|邮箱|微信|erp|主营品类|经营类型|合作状态|所属区域|上级经销商|新增|创建)",
    re.IGNORECASE,
)


def decide_next_action(state: SessionState) -> DialogAction:
    """Choose the next user-facing action based on the current state."""
    invalid_fields = _get_invalid_required_validation_fields(state)
    if invalid_fields:
        state.stage = SessionStage.VALIDATING
        state.awaiting_confirmation = False
        return DialogAction(
            action_type=NextActionType.FIX_INVALID_FIELDS,
            fields=invalid_fields,
            reason="required_validation_failed",
        )

    if state.creation_ready:
        state.stage = SessionStage.AWAITING_CONFIRMATION
        state.awaiting_confirmation = True
        return DialogAction(
            action_type=NextActionType.AWAITING_CONFIRMATION,
            reason="all_required_fields_ready",
        )

    state.stage = SessionStage.COLLECTING
    state.awaiting_confirmation = False
    prioritized_missing_fields = _prioritize_missing_fields(state.missing_required_fields)
    if prioritized_missing_fields:
        state.last_asked_fields = prioritized_missing_fields
        return DialogAction(
            action_type=NextActionType.REQUEST_FIELDS,
            fields=state.last_asked_fields,
            reason="required_fields_missing",
        )

    return DialogAction(
        action_type=NextActionType.ACKNOWLEDGE_PROGRESS,
        reason="no_immediate_follow_up",
    )


def classify_guidance_intent(message: str) -> str | None:
    normalized_message = message.strip()
    if not normalized_message:
        return "greeting"
    if TASK_CONTEXT_PATTERN.search(normalized_message):
        return None
    if GREETING_PATTERN.search(normalized_message):
        return "greeting"
    if IDENTITY_PATTERN.search(normalized_message):
        return "identity_query"
    if HELP_PATTERN.search(normalized_message):
        return "help_query"
    if OFF_TOPIC_PATTERN.search(normalized_message):
        return "off_topic"
    if _looks_like_small_talk(normalized_message):
        return "off_topic"
    return None


def build_guidance_action(intent: str) -> DialogAction:
    return DialogAction(
        action_type=NextActionType.GUIDE_USER,
        reason=intent,
    )


def render_reply(state: SessionState, action: DialogAction) -> str:
    """Render a compact user-facing reply from the selected action."""
    if action.action_type == NextActionType.GUIDE_USER:
        return _render_guidance_reply(state, action.reason)

    if action.action_type == NextActionType.FIX_INVALID_FIELDS:
        fields_text = "、".join(_field_label(field) for field in action.fields)
        details = []
        for field in action.fields:
            validation = state.validation_results.get(field)
            if validation:
                details.append(f"{_field_label(field)}：{validation.message}")
        detail_text = "；".join(details)
        return f"以下字段校验未通过，请先修正：{fields_text}。{detail_text}".strip()

    if action.action_type == NextActionType.AWAITING_CONFIRMATION:
        summary = _render_state_summary(state)
        optional_summary = _render_optional_missing_summary(state)
        if optional_summary:
            return (
                "信息已经收集完整，请检查是否需要补充或修改。\n\n"
                f"{summary}\n\n"
                f"{optional_summary}\n\n"
                "如果没有问题，请回复“确认创建”。"
            )
        return f"信息已经收集完整，请检查是否需要补充或修改。\n\n{summary}\n\n如果没有问题，请回复“确认创建”。"

    if action.action_type == NextActionType.REQUEST_FIELDS:
        return _render_grouped_request_reply(state, action.fields)

    return "信息已记录，你可以继续补充经销商资料。"


def _get_invalid_required_validation_fields(state: SessionState) -> list[str]:
    return [
        field_path
        for field_path in REQUIRED_VALIDATION_PATHS
        if field_path in state.validation_results
        and not state.validation_results[field_path].valid
    ]


def _prioritize_missing_fields(missing_fields: list[str]) -> list[str]:
    order_map = {field_path: index for index, field_path in enumerate(MISSING_FIELD_PRIORITY)}
    return sorted(
        missing_fields,
        key=lambda field_path: (order_map.get(_normalize_field_path_for_display(field_path), 999), field_path),
    )


def _field_label(field_path: str) -> str:
    normalized_path = _normalize_field_path_for_display(field_path)
    return FIELD_LABELS.get(normalized_path, normalized_path)


def _normalize_contact_field_path(field_path: str) -> str:
    return _normalize_field_path_for_display(field_path)


def _render_state_summary(state: SessionState) -> str:
    lines = ["已收集信息如下："]
    main_info = state.main_info

    if main_info.distributorName:
        lines.append(f"经销商名称：{main_info.distributorName}")
    lines.append(f"经销商等级：{main_info.distributorLevel}")
    if main_info.parentDistributorName:
        lines.append(f"上级经销商：{main_info.parentDistributorName}")
    if main_info.customerMobile:
        lines.append(f"客户手机号：{main_info.customerMobile}")
    if main_info.customerEmail:
        lines.append(f"客户邮箱：{main_info.customerEmail}")
    if main_info.belongRegion:
        lines.append(f"所属区域：{main_info.belongRegion}")
    if main_info.erpCode:
        lines.append(f"ERP编码：{main_info.erpCode}")
    if main_info.mainCategory:
        lines.append(f"主营品类：{main_info.mainCategory}")
    if main_info.mainCategoryGrade:
        lines.append(f"主营品类档次：{main_info.mainCategoryGrade}")
    if main_info.businessType:
        lines.append(f"经营类型：{main_info.businessType}")
    if main_info.cooperationStatus:
        lines.append(f"合作状态：{main_info.cooperationStatus}")
    if main_info.status:
        lines.append(f"状态：{main_info.status.value}")
    if main_info.providePoints is not None:
        points_text = "发积分" if main_info.providePoints else "不发积分"
        lines.append(
            f"积分规则：{points_text}，比例 {main_info.providePointsRatio}"
        )

    if state.contacts:
        for index, contact in enumerate(state.contacts, start=1):
            if not any(
                [contact.contactName, contact.position, contact.mobile, contact.wechat]
            ):
                continue
            parts = [f"联系人{index}"]
            if contact.contactName:
                parts.append(contact.contactName)
            if contact.position:
                parts.append(contact.position)
            if contact.mobile:
                parts.append(contact.mobile)
            if contact.wechat:
                parts.append(f"微信 {_render_contact_wechat(contact)}")
            lines.append("：".join([parts[0], "，".join(parts[1:])]))

    return "\n".join(lines)


def _render_guidance_reply(state: SessionState, intent: str) -> str:
    role_text = "我是新增经销商信息收集助手，负责帮你收集、校验并确认新增经销商资料。"
    guidance_text = _build_guidance_follow_up(state)

    if intent == "greeting":
        return f"你好，{role_text} {guidance_text}"
    if intent == "identity_query":
        return f"{role_text} 你可以直接告诉我经销商名称、手机号、邮箱、联系人或主营品类等信息。{guidance_text}"
    if intent == "help_query":
        return f"我会帮你分步收集新增经销商必填信息，并在信息完整后整理给你确认创建。{guidance_text}"
    return f"我当前只负责新增经销商资料收集。{guidance_text}"


def _build_guidance_follow_up(state: SessionState) -> str:
    if state.creation_ready:
        return "当前信息已经基本齐全，如果没有问题，你可以直接回复“确认创建”。"

    prioritized_missing_fields = _prioritize_missing_fields(state.missing_required_fields)
    if prioritized_missing_fields:
        category_lines = _build_required_category_lines(prioritized_missing_fields)
        if category_lines:
            return "你可以按类别补充信息，例如：\n" + "\n".join(category_lines)

    return "你可以直接继续补充经销商资料。"


def _looks_like_small_talk(message: str) -> bool:
    stripped = message.strip()
    if len(stripped) <= 6 and stripped.endswith(("?", "？")):
        return True
    if stripped in {"嗯", "哦", "好的", "行", "知道了"}:
        return True
    return False


def _render_contact_wechat(contact) -> str:
    if contact.wechat != "same_as_mobile":
        return contact.wechat
    if contact.mobile:
        return contact.mobile
    return "同联系人电话"


def _render_grouped_request_reply(state: SessionState, field_paths: list[str]) -> str:
    lines = ["我还需要你按类别补充这些信息："]
    lines.extend(_build_required_category_lines(field_paths))

    optional_lines = _build_optional_category_lines(state, include_only_categories=_categories_from_fields(field_paths))
    if optional_lines:
        lines.append("")
        lines.append("如果你方便，也可以一并补充这些非必填信息：")
        lines.extend(optional_lines)

    lines.append("")
    lines.append("你可以一次把同一类信息尽量说全，我会一起整理。")
    return "\n".join(lines)


def _render_optional_missing_summary(state: SessionState) -> str:
    optional_lines = _build_optional_category_lines(state)
    if not optional_lines:
        return ""

    lines = ["当前还可以补充这些非必填信息："]
    lines.extend(optional_lines)
    return "\n".join(lines)


def _build_required_category_lines(field_paths: list[str]) -> list[str]:
    grouped_fields = _group_fields_by_category(field_paths)
    lines: list[str] = []
    for category in CATEGORY_ORDER:
        fields = grouped_fields.get(category, [])
        if not fields:
            continue
        label = CATEGORY_LABELS[category]
        field_text = "、".join(_field_label(field) for field in fields)
        if category == "contact":
            lines.append(f"- {label}（至少 1 位，必填）：{field_text}")
            continue
        lines.append(f"- {label}（必填）：{field_text}")
    return lines


def _build_optional_category_lines(
    state: SessionState,
    *,
    include_only_categories: set[str] | None = None,
) -> list[str]:
    grouped_optional = _compute_optional_missing_by_category(state)
    lines: list[str] = []
    for category in CATEGORY_ORDER:
        if include_only_categories is not None and category not in include_only_categories:
            continue
        fields = grouped_optional.get(category, [])
        if not fields:
            continue
        label = CATEGORY_LABELS[category]
        field_text = "、".join(_field_label(field) for field in fields)
        if category == "site":
            lines.append(f"- {label}：{field_text}")
            continue
        lines.append(f"- {label}：{field_text}")
    return lines


def _compute_optional_missing_by_category(state: SessionState) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}

    for category, field_paths in OPTIONAL_FIELD_GROUPS.items():
        category_missing: list[str] = []
        for field_path in field_paths:
            if _is_field_path_missing(state, field_path):
                category_missing.append(field_path)
        if category_missing:
            result[category] = category_missing

    return result


def _group_fields_by_category(field_paths: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for field_path in field_paths:
        category = _field_category(field_path)
        grouped.setdefault(category, [])
        normalized_path = _normalize_field_path_for_display(field_path)
        if normalized_path not in grouped[category]:
            grouped[category].append(normalized_path)
    return grouped


def _categories_from_fields(field_paths: list[str]) -> set[str]:
    return {_field_category(field_path) for field_path in field_paths}


def _field_category(field_path: str) -> str:
    normalized_path = _normalize_field_path_for_display(field_path)
    if normalized_path.startswith("contacts[0]."):
        return "contact"
    if normalized_path.startswith("sites[0]."):
        return "site"
    if normalized_path in {
        "main_info.status",
        "main_info.providePoints",
        "main_info.providePointsRatio",
        "main_info.mainCategory",
        "main_info.mainCategoryGrade",
        "main_info.businessType",
        "main_info.cooperationStatus",
        "main_info.discount",
        "main_info.ownBrandDisplay",
        "main_info.competitorBrandDisplay",
    }:
        return "business"
    return "main"


def _normalize_field_path_for_display(field_path: str) -> str:
    normalized_path = re.sub(r"contacts\[\d+\]", "contacts[0]", field_path)
    normalized_path = re.sub(r"sites\[\d+\]", "sites[0]", normalized_path)
    return normalized_path


def _is_field_path_missing(state: SessionState, field_path: str) -> bool:
    normalized_path = _normalize_field_path_for_display(field_path)
    if normalized_path.startswith("main_info."):
        field_name = normalized_path.removeprefix("main_info.")
        value = getattr(state.main_info, field_name, None)
        return _is_missing_value(value)

    if normalized_path.startswith("contacts[0]."):
        field_name = normalized_path.removeprefix("contacts[0].")
        if not state.contacts:
            return True
        value = getattr(state.contacts[0], field_name, None)
        return _is_missing_value(value)

    if normalized_path.startswith("sites[0]."):
        field_name = normalized_path.removeprefix("sites[0].")
        if not state.sites:
            return True
        value = getattr(state.sites[0], field_name, None)
        return _is_missing_value(value)

    return False


def _is_missing_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False
