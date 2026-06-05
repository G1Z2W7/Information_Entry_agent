from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "evals" / "cases" / "extraction_non_enum_5x50.jsonl"

REGIONS = ["华东", "华南", "华北", "华中", "西南"]
SOURCES = ["老客户介绍", "销售开发", "市场活动线索", "朋友推荐", "历史存量客户"]
SALES_PRODUCTS = ["五金", "刀具", "轴承", "设备", "劳保"]
POSITIONS = ["老板", "总经理", "采购", "财务", "店长"]
PERSON_NAMES = ["王磊", "刘芳", "赵敏", "陈涛", "李静", "周凯", "孙倩", "吴迪", "郑浩", "何琳"]
CITIES = [
    ("浙江省", "杭州市", "西湖区"),
    ("江苏省", "苏州市", "工业园区"),
    ("广东省", "深圳市", "龙岗区"),
    ("山东省", "青岛市", "黄岛区"),
    ("四川省", "成都市", "武侯区"),
]
STREETS = ["文三路", "金鸡湖大道", "坂田大道", "长江中路", "天府大道"]


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    cases = []
    cases.extend(build_company_core_cases())
    cases.extend(build_relationship_sales_cases())
    cases.extend(build_contact_cases())
    cases.extend(build_dates_discount_site_cases())
    cases.extend(build_modification_cases())

    if len(cases) != 250:
        raise RuntimeError(f"Expected 250 cases, got {len(cases)}")

    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")

    print(f"Wrote {len(cases)} cases to {OUTPUT_PATH}")


def build_company_core_cases() -> list[dict]:
    cases = []
    for index in range(50):
        company = f"远航汽配{index + 1}号店"
        email = f"yuanhang{index + 1:02d}@example.com"
        mobile = f"1380000{index + 1:04d}"
        erp_code = f"YH{index + 1:03d}"
        belong_region = REGIONS[index % len(REGIONS)]
        source = SOURCES[index % len(SOURCES)]
        patterns = [
            f"新增经销商，名字叫{company}，客户邮箱是{email}，客户手机号{mobile}，ERP编码{erp_code}，所属区域{belong_region}，来源{source}。",
            f"{company} 这家客户准备新建，邮箱 {email}，手机 {mobile}，erp 是 {erp_code}，归属 {belong_region}，客户来源是{source}。",
            f"帮我录一个经销商：{company}。联系方式邮箱 {email}，客户电话 {mobile}，ERP 编码为 {erp_code}，属于{belong_region}，来源是{source}。",
            f"经销商名称填 {company}，客户邮箱填 {email}，客户手机号填 {mobile}，ERP 号 {erp_code}，所属区域填{belong_region}，来源填{source}。",
            f"要新增的客户是{company}，邮箱 {email}，电话 {mobile}，ERP编码是{erp_code}，区域在{belong_region}，这条线索来自{source}。",
        ]
        message = patterns[index % len(patterns)]
        cases.append(
            {
                "case_id": f"company_core_{index + 1:03d}",
                "scene": "company_core",
                "message": message,
                "expected_patch": {
                    "main_info": {
                        "distributorName": company,
                        "customerEmail": email,
                        "customerMobile": mobile,
                        "erpCode": erp_code,
                        "belongRegion": belong_region,
                        "source": source,
                    }
                },
                "tags": ["company_core", "main_info", "non_enum"],
            }
        )
    return cases


def build_relationship_sales_cases() -> list[dict]:
    cases = []
    for index in range(50):
        parent = f"联诚工具中心{index + 1}"
        sales_user = PERSON_NAMES[index % len(PERSON_NAMES)]
        sales_manager = PERSON_NAMES[(index + 3) % len(PERSON_NAMES)]
        sales_product = SALES_PRODUCTS[index % len(SALES_PRODUCTS)]
        authorized_region = f"{['杭州', '苏州', '深圳', '青岛', '成都'][index % 5]}及周边"
        patterns = [
            f"这是二级经销商，上级经销商挂在{parent}下面，所属销售是{sales_user}，经理是{sales_manager}，销售产品类型做{sales_product}，授权区域{authorized_region}。",
            f"请按二级经销商录入，上级名称填{parent}；销售同事是{sales_user}，对应经理{sales_manager}，产品线按{sales_product}，授权范围是{authorized_region}。",
            f"这家需要挂到上级经销商 {parent}，负责销售 {sales_user}，上级经理 {sales_manager}，销售产品类型 {sales_product}，授权区域覆盖{authorized_region}。",
            f"二级客户，挂靠 {parent}。所属销售 {sales_user}，销售经理 {sales_manager}，产品类型偏{sales_product}，授权区域写{authorized_region}。",
            f"把上级经销商记成{parent}，销售归{sales_user}，经理是{sales_manager}，产品类型做{sales_product}，授权区域是{authorized_region}。",
        ]
        message = patterns[index % len(patterns)]
        cases.append(
            {
                "case_id": f"relationship_sales_{index + 1:03d}",
                "scene": "relationship_sales",
                "initial_patch": {"main_info": {"distributorLevel": 2}},
                "message": message,
                "expected_patch": {
                    "main_info": {
                        "parentDistributorName": parent,
                        "salesUserName": sales_user,
                        "salesManagerName": sales_manager,
                        "salesProductTypeName": sales_product,
                        "authorizedRegion": authorized_region,
                    }
                },
                "tags": ["relationship_sales", "main_info", "non_enum"],
            }
        )
    return cases


def build_contact_cases() -> list[dict]:
    cases = []
    for index in range(50):
        primary_name = PERSON_NAMES[index % len(PERSON_NAMES)]
        primary_mobile = f"1390000{index + 1:04d}"
        secondary_name = PERSON_NAMES[(index + 4) % len(PERSON_NAMES)]
        secondary_mobile = f"1370000{index + 1:04d}"
        primary_position = POSITIONS[index % len(POSITIONS)]
        secondary_position = POSITIONS[(index + 2) % len(POSITIONS)]
        primary_wechat = "same_as_mobile" if index % 2 == 0 else f"wl_{index + 1:02d}"
        secondary_wechat = f"lf_{index + 1:02d}"
        is_primary = index % 3 != 0

        if index % 2 == 0:
            message = (
                f"联系人这块，{primary_position}{primary_name}，电话{primary_mobile}，微信同手机号，"
                f"{'是主联系人。' if is_primary else '先记上。'}"
                f"另外 {secondary_position}{secondary_name}，电话{secondary_mobile}，微信{secondary_wechat}。"
            )
        else:
            message = (
                f"主要对接的是{primary_name}，职位{primary_position}，手机号 {primary_mobile}，微信 {primary_wechat}。"
                f"还有一个联系人 {secondary_name}，做{secondary_position}，电话 {secondary_mobile}，微信 {secondary_wechat}。"
            )

        expected_contacts = [
            {
                "contactName": primary_name,
                "position": primary_position,
                "mobile": primary_mobile,
                "wechat": primary_wechat,
            },
            {
                "contactName": secondary_name,
                "position": secondary_position,
                "mobile": secondary_mobile,
                "wechat": secondary_wechat,
            },
        ]
        if is_primary:
            expected_contacts[0]["isPrimary"] = True

        cases.append(
            {
                "case_id": f"contacts_{index + 1:03d}",
                "scene": "contacts",
                "message": message,
                "expected_patch": {"contacts": expected_contacts},
                "tags": ["contacts", "multi_contact", "non_enum"],
            }
        )
    return cases


def build_dates_discount_site_cases() -> list[dict]:
    cases = []
    for index in range(50):
        year = 2026 + (index % 2)
        month = (index % 12) + 1
        day = (index % 28) + 1
        issue_date = f"{year:04d}-{month:02d}-{day:02d}"
        expiry_year = year + 1
        expiry_date = f"{expiry_year:04d}-{month:02d}-{day:02d}"
        discount = round(0.55 + (index % 10) * 0.03, 2)
        raw_discount = f"{int(discount * 100)}%" if index % 2 == 0 else f"{discount * 10:.1f}折"
        province, city, district = CITIES[index % len(CITIES)]
        street = STREETS[index % len(STREETS)]
        address = f"{province}{city}{district}{street}{index + 18}号"
        remark = f"仓库和门店在一起{index + 1}"

        patterns = [
            (
                f"签发日期是{year}年{month}月{day}日，到期日期到{expiry_year}/{month}/{day}，折扣给{raw_discount}。"
                f"门店地址在{address}，备注{remark}。"
            ),
            (
                f"这家客户从 {issue_date} 开始生效，截止到 {expiry_date}，折扣按 {raw_discount}。"
                f"详细地址写{address}，备注是{remark}。"
            ),
            (
                f"签发时间 {issue_date}，有效期到 {expiry_date}，经销商折扣 {raw_discount}，"
                f"地址在{address}，补充说明{remark}。"
            ),
            (
                f"起始日期 {year}年{month}月{day}日，结束日期 {expiry_year}年{month}月{day}日，"
                f"给的折扣是 {raw_discount}，场地完整地址 {address}，备注填{remark}。"
            ),
            (
                f"签发日就记 {issue_date}，到期日 {expiry_date}，折扣 {raw_discount}，"
                f"店面在{address}，备注说明 {remark}。"
            ),
        ]
        message = patterns[index % len(patterns)]

        cases.append(
            {
                "case_id": f"dates_discount_site_{index + 1:03d}",
                "scene": "dates_discount_site",
                "message": message,
                "expected_patch": {
                    "main_info": {
                        "issueDate": issue_date,
                        "expiryDate": expiry_date,
                        "discount": discount,
                        "remark": remark,
                    },
                    "sites": [
                        {
                            "fullAddress": address,
                            "provinceName": province,
                            "cityName": city,
                            "districtName": district,
                        }
                    ],
                },
                "tags": ["dates_discount_site", "mixed_fields", "non_enum"],
            }
        )
    return cases


def build_modification_cases() -> list[dict]:
    cases = []
    for index in range(50):
        base_company = f"星驰工具{index + 1}"
        next_company = f"星驰工业{index + 1}"
        base_mobile = f"1360000{index + 1:04d}"
        next_mobile = f"1350000{index + 1:04d}"
        base_email = f"xingchi{index + 1:02d}@old.com"
        next_email = f"xingchi{index + 1:02d}@new.com"
        base_erp = f"XCOLD{index + 1:03d}"
        next_erp = f"XCNEW{index + 1:03d}"
        base_region = REGIONS[index % len(REGIONS)]
        next_region = REGIONS[(index + 1) % len(REGIONS)]
        base_contact = PERSON_NAMES[(index + 2) % len(PERSON_NAMES)]
        next_contact_mobile = f"1880000{index + 1:04d}"
        province, city, district = CITIES[index % len(CITIES)]
        new_address = f"{province}{city}{district}{STREETS[(index + 1) % len(STREETS)]}{index + 66}号"

        patterns = [
            (
                f"经销商名称改成{next_company}，客户手机号改成{next_mobile}，客户邮箱换成{next_email}，"
                f"ERP编码改为{next_erp}，所属区域不是{base_region}，改成{next_region}。"
            ),
            (
                f"刚才信息不对，名称换成{next_company}，手机改{next_mobile}，邮箱改{next_email}，"
                f"erp 更新成{next_erp}，区域改为{next_region}。"
            ),
            (
                f"把公司名改成{next_company}，客户电话改成{next_mobile}，邮箱改成{next_email}，"
                f"ERP 改成 {next_erp}，所属区域换到{next_region}。"
            ),
            (
                f"不是原来的信息，经销商名称用{next_company}，手机号换{next_mobile}，"
                f"客户邮箱更新为{next_email}，ERP编码调整成{next_erp}，区域写{next_region}。"
            ),
            (
                f"更新一下：公司改{next_company}，电话改{next_mobile}，邮箱改{next_email}，"
                f"erp 改 {next_erp}，区域从{base_region}调到{next_region}。"
            ),
        ]

        contact_message = (
            f"{base_contact} 的电话改成 {next_contact_mobile}，门店地址改到{new_address}。"
        )
        message = f"{patterns[index % len(patterns)]}{contact_message}"

        cases.append(
            {
                "case_id": f"modifications_{index + 1:03d}",
                "scene": "modifications",
                "initial_patch": {
                    "main_info": {
                        "distributorName": base_company,
                        "customerMobile": base_mobile,
                        "customerEmail": base_email,
                        "erpCode": base_erp,
                        "belongRegion": base_region,
                    },
                    "contacts": [
                        {
                            "contactName": base_contact,
                            "position": "老板",
                            "mobile": base_mobile,
                            "wechat": "same_as_mobile",
                        }
                    ],
                    "sites": [
                        {
                            "fullAddress": f"{province}{city}{district}{STREETS[index % len(STREETS)]}{index + 8}号"
                        }
                    ],
                },
                "message": message,
                "expected_patch": {
                    "main_info": {
                        "distributorName": next_company,
                        "customerMobile": next_mobile,
                        "customerEmail": next_email,
                        "erpCode": next_erp,
                        "belongRegion": next_region,
                    },
                    "contacts": [
                        {
                            "contactName": base_contact,
                            "mobile": next_contact_mobile,
                        }
                    ],
                    "sites": [
                        {
                            "fullAddress": new_address,
                            "provinceName": province,
                            "cityName": city,
                            "districtName": district,
                        }
                    ],
                },
                "tags": ["modifications", "override", "non_enum"],
            }
        )
    return cases


if __name__ == "__main__":
    main()
