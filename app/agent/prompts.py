from __future__ import annotations

import json
from typing import Any


EXTRACTION_SCHEMA_EXAMPLE = {
    "main_info": {
        "distributorName": "",
        "distributorLevel": 0,
        "parentDistributorName": "",
        "customerEmail": "",
        "customerMobile": "",
        "salesUserName": "",
        "salesManagerName": "",
        "discount": 0.0,
        "authorizedRegion": "",
        "belongRegion": "",
        "erpCode": "",
        "issueDate": "",
        "expiryDate": "",
        "status": "",
        "providePoints": False,
        "providePointsRatio": 0.0,
        "mainCategory": "",
        "mainCategoryGrade": "",
        "businessType": "",
        "cooperationStatus": "",
        "informationSource": "",
    },
    "contacts": [
        {
            "contactName": "",
            "position": "",
            "mobile": "",
            "wechat": "",
            "isPrimary": False,
            "remark": "",
        }
    ],
    "sites": [
        {
            "siteType": "",
            "siteTypeName": "",
            "siteSubType": "",
            "hasStore": False,
            "storeAreaRange": "",
            "fullAddress": "",
            "provinceName": "",
            "cityName": "",
            "districtName": "",
            "isPrimary": False,
            "remark": "",
        }
    ],
}


def build_incremental_extraction_prompt(
    *,
    state_summary: dict[str, Any],
    missing_fields: list[str],
    user_message: str,
) -> str:
    """Build the prompt for incremental semantic extraction."""
    return """你是经销商新增流程的字段抽取助手。

任务：只根据“本轮用户输入”提取新增信息或修改信息，输出 JSON，且只能输出 JSON。
不要重复输出当前状态里已经确认、且本轮没有提到的字段。
没有提到的字段不要输出。
如果用户表达的是修改，输出修改后的值。

当前已收集状态摘要：
{state_summary}

当前仍缺失的关键字段：
{missing_fields}

允许输出的 JSON 结构示例：
{schema_example}

规则：
1. 只抽取本轮用户明确表达的信息。
2. `status` 只能输出 `normal` 或 `disabled`。
3. `mainCategory` 尽量归一化为标准名称，例如“五金工具”“汽配”。
4. `businessType`、`cooperationStatus`、`mainCategoryGrade` 尽量归一化为标准业务值。
5. `wechat` 如果表达为“同手机号”，输出 `same_as_mobile`。
6. `discount` 统一成小数，例如 58 折输出 0.58。
7. `customerEmail`、`customerMobile`、`erpCode`、联系人、场地等如果本轮提到，也要一并输出。
8. 如果用户在表达“改成”“换成”“不是这个”“更新一下”等修改意图，只输出本轮被修改的字段，不要重复输出未修改字段。
9. 修改联系人时，优先输出命中已有联系人的变化字段，不要新增重复联系人；不要因为补了一个手机号或微信就新建联系人。
10. 修改场地时，优先输出命中已有场地的变化字段，不要新增重复场地；不要因为补了一个新地址就新建场地。
11. 地址字段优先保留用户原始表达的 `fullAddress`，尽量不要截断；如果用户原话里明确出现了省、市、区/县，尽量同步输出 `provinceName`、`cityName`、`districtName`；如果没有把握，再留给后续地址解析接口补充。
12. 如果本轮没有新信息，输出空 JSON：{{}}。

本轮用户输入：
{user_message}
""".format(
        state_summary=json.dumps(state_summary, ensure_ascii=False, indent=2),
        missing_fields=json.dumps(missing_fields, ensure_ascii=False),
        schema_example=json.dumps(EXTRACTION_SCHEMA_EXAMPLE, ensure_ascii=False, indent=2),
        user_message=user_message,
    )


def build_intent_classification_prompt(
    *,
    state_summary: dict[str, Any],
    missing_fields: list[str],
    user_message: str,
) -> str:
    """Build the prompt for intent classification before extraction."""
    return """你是经销商新增流程的对话意图识别助手。

你的任务：判断“本轮用户输入”属于哪一种意图，并输出 JSON，且只能输出 JSON。

允许的 intent 只有这些：
- greeting：问候
- identity_query：询问你是谁、你能做什么
- help_query：询问需要哪些资料、怎么填、怎么创建
- off_topic：与新增经销商任务无关的话题
- task_input：提供经销商新增相关信息
- task_modify：修改已提供的经销商信息
- confirm_create：确认创建
- unknown：无法判断

输出格式：
{{
  "intent": "greeting"
}}

判断原则：
1. 如果用户在提供经销商、联系人、手机号、邮箱、主营品类、ERP、合作状态等业务信息，判断为 `task_input`。
2. 如果用户在表达“改成”“修改”“不是这个”“换成”，判断为 `task_modify`。
3. 如果用户在表达“确认创建”“提交吧”“创建吧”，判断为 `confirm_create`。
4. 如果用户问“你是谁”“你能干什么”“你能做什么”，判断为 `identity_query`。
5. 如果用户问“需要哪些字段”“怎么填”“要准备什么”，判断为 `help_query`。
6. 如果用户只是闲聊、寒暄、或询问天气/笑话/新闻等与任务无关内容，判断为 `greeting` 或 `off_topic`。
7. 不要因为当前缺字段就强行把无关消息判成 `task_input`。

当前已收集状态摘要：
{state_summary}

当前缺失字段：
{missing_fields}

本轮用户输入：
{user_message}
""".format(
        state_summary=json.dumps(state_summary, ensure_ascii=False, indent=2),
        missing_fields=json.dumps(missing_fields, ensure_ascii=False),
        user_message=user_message,
    )
