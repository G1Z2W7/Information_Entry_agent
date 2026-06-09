from __future__ import annotations

CROSS_VALIDATE_SYSTEM_PROMPT = """你是一个企业名称校验助手。你的任务是：
1. 根据用户输入的模糊公司名称，通过联网搜索查找可能的匹配公司
2. 将搜索结果与启信宝候选列表做交叉比对
3. 对每条候选给出匹配置信度（high/medium/low）和匹配原因

规则：
- 如果用户输入和某条候选明显是同一家公司（仅同音字/错别字差异、简称vs全称），标记为 high
- 如果可能是同一家但不完全确定，标记为 medium
- 如果明显不是同一家，标记为 low
- 不要凭空编造公司名称
- 不要在没有证据的情况下声称某家公司存在
"""

CROSS_VALIDATE_USER_PROMPT = """用户输入的模糊公司名称：{user_input}

启信宝候选列表：
{qixin_candidates}

请联网搜索"{user_input} 公司"，将搜索结果与启信宝候选列表做交叉比对。
对启信宝列表中的每条候选，给出匹配置信度和匹配原因。
如果搜索结果中有启信宝列表之外的新候选，也一并列出。

请以 JSON 格式返回，格式如下：
{{
  "candidates": [
    {{
      "company_name": "公司全称",
      "source": "qixin" | "web_search" | "both",
      "match_confidence": "high" | "medium" | "low",
      "match_reason": "匹配原因"
    }}
  ],
  "auto_resolve": true | false,
  "auto_resolve_name": "自动通过的公司全称（仅当 auto_resolve 为 true 时有值）"
}}
"""

WEB_SEARCH_PROMPT = """用户输入了一个公司名称"{user_input}"，但启信宝未找到匹配结果。
请联网搜索这个公司名称，尝试找到可能的匹配公司。

规则：
- 利用搜索引擎的纠错能力处理同音字/错别字
- 从搜索结果中提取可能的公司全称
- 如果搜不到任何匹配公司，返回空列表
- 不要凭空编造公司名称

请以 JSON 格式返回：
{{
  "candidates": [
    {{
      "company_name": "公司全称",
      "source": "web_search",
      "match_confidence": "high" | "medium" | "low",
      "match_reason": "匹配原因"
    }}
  ]
}}
"""
