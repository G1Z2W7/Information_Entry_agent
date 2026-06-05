from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"

USER_INPUT = (
    "新增一个二级经销商，名称叫智行汽车，挂在上级经销商杭州汇诚工具下面。"
    "ERP编码是HZ001，客户邮箱是zhixing@example.com，客户手机号是13800138000，所属销售是张晨，经理是李峰。"
    "他们主要做汽配批发，主营品类是汽配，主营品类档次偏国内主流品牌为主，经营类型是批发B2B，"
    "合作状态是稳定合作已签约，折扣按58折，授权区域是杭州和绍兴，所属区域华东，来源是老客户介绍，"
    "信息来源是销售拜访，签发日期是2026-06-01，到期时间2027-12-31，状态正常，发积分，积分比例1。"
    "联系人方面，老板王磊，电话13900001111，微信同手机号，是主联系人；采购刘芳，电话13700002222，"
    "微信lf采购，以后采购对接直接找她。场地方面，主门店在浙江省杭州市西湖区文三路，属于临街主道，"
    "大概一百多平；办公地在浙江省杭州市滨江区江南大道。"
)

PROMPT = """你是字段抽取助手。

根据输入文本提取字段，输出 JSON，且只能输出 JSON。
没有提到的字段不要输出。

输出结构：
{{
  "main_info": {{
    "distributorName": "",
    "distributorLevel": 0,
    "parentDistributorName": "",
    "customerEmail": "",
    "customerMobile": "",
    "salesUserName": "",
    "salesManagerName": "",
    "salesProductTypeName": "",
    "discount": 0.0,
    "authorizedRegion": "",
    "belongRegion": "",
    "source": "",
    "erpCode": "",
    "issueDate": "",
    "expiryDate": "",
    "status": "",
    "providePoints": false,
    "providePointsRatio": 0.0,
    "mainCategory": "",
    "mainCategoryGrade": "",
    "businessType": "",
    "cooperationStatus": "",
    "informationSource": ""
  }},
  "contacts": [
    {{
      "contactName": "",
      "position": "",
      "mobile": "",
      "wechat": "",
      "isPrimary": false,
      "remark": ""
    }}
  ],
  "sites": [
    {{
      "siteType": "",
      "siteTypeName": "",
      "siteSubType": "",
      "hasStore": false,
      "storeAreaRange": "",
      "fullAddress": "",
      "provinceName": "",
      "cityName": "",
      "districtName": "",
      "isPrimary": false,
      "remark": ""
    }}
  ]
}}

规则：
1. discount 统一成小数，58折输出 0.58。
2. providePoints 输出 true 或 false。
3. providePointsRatio 输出数字。
4. issueDate、expiryDate 统一为 YYYY-MM-DD。
5. status 只输出 normal 或 disabled。
6. mainCategory 尽量归一化到字段定义中的标准值。
7. siteType 只输出 store、office、repairShop。
8. 微信同手机号时，wechat 输出 same_as_mobile。

输入文本：
{user_input}
"""

MODEL_CONFIG = {
    "provider": "deepseek",
    "api_key_env": "DS_API_KEY",
    "base_url_env": "DS_BASE_URL",
    "model_env": "DS_MODEL",
}


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=require_env(MODEL_CONFIG["model_env"]),
        api_key=require_env(MODEL_CONFIG["api_key_env"]),
        base_url=require_env(MODEL_CONFIG["base_url_env"]),
        temperature=0,
        timeout=60,
        max_retries=0,
    )


def call_model() -> dict[str, Any]:
    llm = build_llm()
    prompt = PROMPT.format(user_input=USER_INPUT)

    started_at = time.perf_counter()
    response = llm.invoke(prompt)
    elapsed = time.perf_counter() - started_at

    content = response.content
    if isinstance(content, list):
        content = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )

    parsed: Any
    try:
        parsed = json.loads(content)
    except Exception:
        parsed = {"raw_text": content}

    return {
        "provider": MODEL_CONFIG["provider"],
        "model": require_env(MODEL_CONFIG["model_env"]),
        "elapsed_seconds": round(elapsed, 3),
        "output": parsed,
    }


def main() -> None:
    load_dotenv(ENV_FILE)

    print(f"Running provider={MODEL_CONFIG['provider']}...", flush=True)
    try:
        result = call_model()
        print(
            f"Finished provider={MODEL_CONFIG['provider']}, elapsed={result['elapsed_seconds']}s",
            flush=True,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "provider": MODEL_CONFIG["provider"],
                    "model": os.getenv(MODEL_CONFIG["model_env"], ""),
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
