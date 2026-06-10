from __future__ import annotations

import json

import httpx

from app.agent.address_resolver import AMapAddressResolver, parse_explicit_address_components
from app.agent.models import AddressActionType, AddressResolutionRequest, CurrentLocation


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


def test_amap_resolver_returns_confirmation_for_single_text_hit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/geocode/geo"
        assert request.url.params["address"] == "浙江省杭州市西湖区文三路18号"
        payload = {
            "status": "1",
            "geocodes": [
                {
                    "formatted_address": "浙江省杭州市西湖区文三路18号",
                    "province": "浙江省",
                    "city": "杭州市",
                    "district": "西湖区",
                    "location": "120.1551,30.2741",
                }
            ],
        }
        return httpx.Response(200, json=payload)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://restapi.amap.com",
    )
    resolver = AMapAddressResolver(web_service_key="test-key", http_client=client)

    response = resolver.resolve(
        AddressResolutionRequest(
            session_id="session-amap-1",
            action=AddressActionType.RESOLVE_TEXT,
            full_address="浙江省杭州市西湖区文三路18号",
        )
    )

    assert response.resolution_status == "awaiting_user_confirmation"
    assert response.normalized_site is not None
    assert response.normalized_site.fullAddress == "浙江省杭州市西湖区文三路18号"
    assert len(response.candidates) == 1
    assert response.candidates[0].candidate_id.startswith("geo-")


def test_amap_resolver_returns_nearby_candidates_for_current_location() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/geocode/regeo"
        assert request.url.params["location"] == "120.1551,30.2741"
        payload = {
            "status": "1",
            "regeocode": {
                "formatted_address": "浙江省杭州市西湖区文三路18号",
                "addressComponent": {
                    "province": "浙江省",
                    "city": "杭州市",
                    "district": "西湖区",
                    "township": "翠苑街道",
                    "streetNumber": {
                        "street": "文三路",
                        "number": "18号",
                    },
                },
                "pois": [
                    {
                        "id": "B001",
                        "name": "文三路18号门店",
                        "address": "文三路18号",
                        "location": "120.1551,30.2741",
                    },
                    {
                        "id": "B002",
                        "name": "科技园西门",
                        "address": "文三路20号",
                        "location": "120.1555,30.2745",
                    },
                ],
            },
        }
        return httpx.Response(200, json=payload)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://restapi.amap.com",
    )
    resolver = AMapAddressResolver(web_service_key="test-key", http_client=client)

    response = resolver.resolve(
        AddressResolutionRequest(
            session_id="session-amap-2",
            action=AddressActionType.USE_CURRENT_LOCATION,
            current_location=CurrentLocation(latitude=30.2741, longitude=120.1551),
        )
    )

    assert response.resolution_status == "awaiting_nearby_selection"
    assert response.current_location is not None
    assert response.current_location.latitude == 30.2741
    assert len(response.candidates) == 2
    assert response.candidates[0].fullAddress.startswith("浙江省杭州市西湖区")
