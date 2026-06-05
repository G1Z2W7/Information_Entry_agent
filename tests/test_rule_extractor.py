from __future__ import annotations

from app.agent.extractor import extract_rule_based_patch


def test_rule_extractor_parses_main_info_and_contacts() -> None:
    message = (
        "新增一个二级经销商，ERP编码是HZ001，客户邮箱是zhixing@example.com，"
        "客户手机号是13800138000，折扣按58折，签发日期是2026年6月1日，"
        "到期时间2027-12-31，状态正常，发积分，积分比例1。"
        "老板王磊，电话13900001111，微信同手机号，是主联系人；"
        "采购刘芳，电话13700002222，微信lf采购。"
    )

    patch = extract_rule_based_patch(message)

    assert patch["main_info"]["distributorLevel"] == 2
    assert patch["main_info"]["erpCode"] == "HZ001"
    assert patch["main_info"]["customerEmail"] == "zhixing@example.com"
    assert patch["main_info"]["customerMobile"] == "13800138000"
    assert patch["main_info"]["discount"] == 0.58
    assert patch["main_info"]["issueDate"] == "2026-06-01"
    assert patch["main_info"]["expiryDate"] == "2027-12-31"
    assert patch["main_info"]["status"] == "normal"
    assert patch["main_info"]["providePoints"] is True
    assert patch["main_info"]["providePointsRatio"] == 1.0
    assert patch["contacts"][0]["contactName"] == "王磊"
    assert patch["contacts"][0]["position"] == "老板"
    assert patch["contacts"][0]["mobile"] == "13900001111"
    assert patch["contacts"][0]["wechat"] == "same_as_mobile"
    assert patch["contacts"][0]["isPrimary"] is True
    assert patch["contacts"][1]["contactName"] == "刘芳"
    assert patch["contacts"][1]["position"] == "采购"
    assert patch["contacts"][1]["mobile"] == "13700002222"
    assert patch["contacts"][1]["wechat"] == "lf采购"


def test_rule_extractor_handles_no_points_case() -> None:
    message = "客户邮箱 foo@example.com，不发积分，状态禁用。"

    patch = extract_rule_based_patch(message)

    assert patch["main_info"]["customerEmail"] == "foo@example.com"
    assert patch["main_info"]["providePoints"] is False
    assert patch["main_info"]["providePointsRatio"] == 0.0
    assert patch["main_info"]["status"] == "disabled"
