from __future__ import annotations

from app.agent.address_resolver import parse_explicit_address_components


def test_parse_explicit_address_components_extracts_standard_province_city_district() -> None:
    parsed = parse_explicit_address_components("浙江省杭州市西湖区文三路18号")

    assert parsed == {
        "provinceName": "浙江省",
        "cityName": "杭州市",
        "districtName": "西湖区",
    }


def test_parse_explicit_address_components_extracts_municipality_city_and_district() -> None:
    parsed = parse_explicit_address_components("上海市浦东新区张江路88号")

    assert parsed == {
        "provinceName": "上海市",
        "cityName": "上海市",
        "districtName": "浦东新区",
    }


def test_parse_explicit_address_components_returns_empty_when_address_missing() -> None:
    assert parse_explicit_address_components("") == {}
