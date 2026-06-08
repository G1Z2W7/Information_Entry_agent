from __future__ import annotations

import json
from typing import Any


def build_location_analysis_prompt(
    *,
    user_message: str,
    state_summary: dict[str, Any],
    current_coordinates: dict[str, float | None] | None,
) -> str:
    return f"""
你是一个位置解析 Agent，负责分析用户输入中的位置语义，输出严格 JSON。

任务目标：
1. 判断用户这轮是否提供了位置信息
2. 提取原始地址片段
3. 判断地址类型是 precise / fuzzy / unknown
4. 如有错别字，输出 corrected_queries
5. 如果用户输入里有依附在锚点上的具体位置细节，输出 location_detail
6. location_detail 不只限于楼层房号，也包括方向、距离、入口、路径描述
7. 尽量抽取省市区提示 admin_hints
8. 如果信息不足，指出 missing_parts
9. 输出下一步 next_step，只能是 search / use_current / need_more_detail / need_manual_input

当前位置坐标：
{json.dumps(current_coordinates, ensure_ascii=False)}

当前位置子状态摘要：
{json.dumps(state_summary, ensure_ascii=False)}

本轮用户输入：
{user_message}

输出要求：
- 只能输出 JSON，不要解释
- admin_hints 字段名必须是 province_name / city_name / district_name
- 如果没有可用值，填 null 或空数组
- corrected_queries 只保留适合直接检索的 query
- precise 表示可直接搜索的较明确地址
- fuzzy 表示有地点意图但缺路名、门牌、园区、楼栋等
- unknown 表示无法识别出可靠位置

输出 JSON 结构：
{{
  "raw_address_text": "string or null",
  "address_type": "precise | fuzzy | unknown",
  "corrected_queries": ["string"],
  "location_detail": {{
    "raw_text": "string",
    "detail_type": "unit_detail | relative_distance_detail | entrance_detail | path_detail | landmark_relation_detail"
  }},
  "admin_hints": {{
    "province_name": "string or null",
    "city_name": "string or null",
    "district_name": "string or null"
  }},
  "missing_parts": ["string"],
  "next_step": "search | use_current | need_more_detail | need_manual_input"
}}
""".strip()
