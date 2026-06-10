from __future__ import annotations

from copy import deepcopy
from typing import Any


FieldOptionValue = str | int | float | bool


FIELD_OPTION_DEFINITIONS: dict[str, dict[str, Any]] = {
    "main_info.distributorLevel": {
        "label": "经销商等级",
        "input_type": "select",
        "options": [
            {"label": "一级经销商", "value": 1},
            {"label": "二级经销商", "value": 2},
        ],
    },
    "main_info.mainCategory": {
        "label": "主营品类",
        "input_type": "select",
        "options": [
            {"label": "五金工具", "value": "五金工具"},
            {"label": "设备 & 机床", "value": "设备 & 机床"},
            {"label": "模具配件", "value": "模具配件"},
            {"label": "标准件", "value": "标准件"},
            {"label": "轴承 & 导轨", "value": "轴承 & 导轨"},
            {"label": "化工胶水", "value": "化工胶水"},
            {"label": "建材劳保", "value": "建材劳保"},
            {"label": "油品", "value": "油品"},
            {"label": "电子电器", "value": "电子电器"},
            {"label": "刀具量具", "value": "刀具量具"},
            {"label": "汽配", "value": "汽配"},
            {"label": "其他", "value": "其他"},
        ],
    },
    "main_info.mainCategoryGrade": {
        "label": "主营品类档次",
        "input_type": "select",
        "options": [
            {"label": "国际品牌为主", "value": "国际品牌为主"},
            {"label": "国内主流品牌为主", "value": "国内主流品牌为主"},
            {"label": "国内非主流品牌为主", "value": "国内非主流品牌为主"},
            {"label": "无法判断", "value": "无法判断"},
        ],
    },
    "main_info.businessType": {
        "label": "经营类型",
        "input_type": "select",
        "options": [
            {"label": "零售B2C", "value": "零售B2C"},
            {"label": "贸易B2F", "value": "贸易B2F"},
            {"label": "批发B2B", "value": "批发B2B"},
            {"label": "综合类B2B+B2C", "value": "综合类B2B+B2C"},
            {"label": "综合类B2B+B2F", "value": "综合类B2B+B2F"},
            {"label": "综合类B2F+B2C", "value": "综合类B2F+B2C"},
            {"label": "综合类均有", "value": "综合类均有"},
        ],
    },
    "main_info.cooperationStatus": {
        "label": "合作状态",
        "input_type": "select",
        "options": [
            {"label": "稳定合作｜已签约", "value": "稳定合作｜已签约"},
            {"label": "已供货｜未签约", "value": "已供货｜未签约"},
            {"label": "已接触｜待跟进", "value": "已接触｜待跟进"},
            {"label": "未合作｜仅线索", "value": "未合作｜仅线索"},
        ],
    },
    "main_info.status": {
        "label": "经销商状态",
        "input_type": "select",
        "options": [
            {"label": "正常", "value": "normal"},
            {"label": "禁用", "value": "disabled"},
        ],
    },
    "main_info.informationSource": {
        "label": "信息来源",
        "input_type": "select",
        "options": [
            {"label": "经销商推荐", "value": "经销商推荐"},
            {"label": "销售拜访", "value": "销售拜访"},
            {"label": "市场走访", "value": "市场走访"},
            {"label": "市场活动", "value": "市场活动"},
            {"label": "展会/会议", "value": "展会/会议"},
            {"label": "线上线索", "value": "线上线索"},
            {"label": "历史存量", "value": "历史存量"},
            {"label": "其他", "value": "其他"},
        ],
    },
    "main_info.providePoints": {
        "label": "是否发放积分",
        "input_type": "select",
        "options": [
            {"label": "发积分", "value": True},
            {"label": "不发积分", "value": False},
        ],
    },
    "main_info.providePointsRatio": {
        "label": "积分发放比例",
        "input_type": "select",
        "options": [
            {"label": "0.5", "value": 0.5},
            {"label": "1.0", "value": 1.0},
            {"label": "2.0", "value": 2.0},
        ],
    },
    "contacts[0].position": {
        "label": "联系人职位",
        "input_type": "select",
        "options": [
            {"label": "销售", "value": "销售"},
            {"label": "老板", "value": "老板"},
            {"label": "总经理", "value": "总经理"},
            {"label": "采购", "value": "采购"},
            {"label": "财务", "value": "财务"},
            {"label": "店长", "value": "店长"},
            {"label": "负责人", "value": "负责人"},
        ],
    },
    "contacts[0].wechat": {
        "label": "联系人微信",
        "input_type": "select",
        "options": [
            {"label": "同手机号", "value": "same_as_mobile"},
        ],
    },
}


def get_field_options_payload() -> dict[str, dict[str, Any]]:
    return deepcopy(FIELD_OPTION_DEFINITIONS)


def validate_structured_patch(patch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(patch, dict) or not patch:
        raise ValueError("patch must be a non-empty object")

    unsupported_sections = [key for key in patch if key not in {"main_info", "contacts"}]
    if unsupported_sections:
        unsupported = ", ".join(sorted(unsupported_sections))
        raise ValueError(f"Unsupported structured patch sections: {unsupported}")

    normalized_patch: dict[str, Any] = {}

    main_info = patch.get("main_info")
    if main_info is not None:
        if not isinstance(main_info, dict) or not main_info:
            raise ValueError("patch.main_info must be a non-empty object")
        normalized_patch["main_info"] = {}
        for field_name, value in main_info.items():
            path = f"main_info.{field_name}"
            config = FIELD_OPTION_DEFINITIONS.get(path)
            if config is None:
                raise ValueError(f"Unsupported structured field: {path}")
            if not _is_allowed_option_value(config["options"], value):
                raise ValueError(f"Invalid value for {path}: {value!r}")
            normalized_patch["main_info"][field_name] = value

    contacts = patch.get("contacts")
    if contacts is not None:
        if not isinstance(contacts, list) or not contacts:
            raise ValueError("patch.contacts must be a non-empty list")
        normalized_contacts: list[dict[str, Any]] = []
        for index, item in enumerate(contacts):
            if not isinstance(item, dict) or not item:
                raise ValueError(f"patch.contacts[{index}] must be a non-empty object")
            normalized_contact: dict[str, Any] = {}
            for field_name, value in item.items():
                path = f"contacts[0].{field_name}"
                config = FIELD_OPTION_DEFINITIONS.get(path)
                if config is None:
                    raise ValueError(f"Unsupported structured field: {path}")
                if not _is_allowed_option_value(config["options"], value):
                    raise ValueError(f"Invalid value for {path}: {value!r}")
                normalized_contact[field_name] = value
            normalized_contacts.append(normalized_contact)
        normalized_patch["contacts"] = normalized_contacts

    if not normalized_patch:
        raise ValueError("patch must include at least one supported section")

    return normalized_patch


def _is_allowed_option_value(
    options: list[dict[str, FieldOptionValue]],
    candidate: Any,
) -> bool:
    candidate_key = _normalize_option_value(candidate)
    return any(_normalize_option_value(option["value"]) == candidate_key for option in options)


def _normalize_option_value(value: Any) -> tuple[str, Any]:
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        return ("number", round(float(value), 4))
    if isinstance(value, str):
        return ("string", value)
    return (type(value).__name__, value)
