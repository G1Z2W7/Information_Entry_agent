from __future__ import annotations

import pytest

from app.location_agent.amap import AMapMapSearcher, AMapSearchError


def test_amap_searcher_maps_regeo_and_nearby_results_into_candidates() -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    def fake_fetch(path: str, params: dict[str, str]) -> dict[str, object]:
        calls.append((path, params))
        if path == "/v3/geocode/regeo":
            return {
                "status": "1",
                "regeocode": {
                    "formatted_address": "浙江省杭州市西湖区文三路18号",
                    "addressComponent": {
                        "province": "浙江省",
                        "city": "杭州市",
                        "district": "西湖区",
                        "township": "",
                        "streetNumber": {"street": "文三路", "number": "18号"},
                    },
                },
            }
        if path == "/v3/place/around":
            return {
                "status": "1",
                "pois": [
                    {
                        "id": "B001",
                        "name": "文三路18号门店",
                        "address": "文三路18号",
                        "pname": "浙江省",
                        "cityname": "杭州市",
                        "adname": "西湖区",
                        "location": "120.1551,30.2741",
                    }
                ],
            }
        raise AssertionError(path)

    searcher = AMapMapSearcher(api_key="test-key", fetch_json=fake_fetch)

    candidates = searcher.nearby(30.2741, 120.1551)

    assert calls[0][0] == "/v3/geocode/regeo"
    assert calls[1][0] == "/v3/place/around"
    assert calls[0][1]["location"] == "120.1551,30.2741"
    assert calls[1][1]["location"] == "120.1551,30.2741"
    assert candidates[0].full_address == "浙江省杭州市西湖区文三路18号"
    assert candidates[0].candidate_id == "regeo:120.1551,30.2741"
    assert candidates[1].candidate_id == "B001"
    assert candidates[1].detail_address == "文三路18号"


def test_amap_searcher_uses_city_hint_for_text_search() -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    def fake_fetch(path: str, params: dict[str, str]) -> dict[str, object]:
        calls.append((path, params))
        return {
            "status": "1",
            "pois": [
                {
                    "id": "B002",
                    "name": "张江路88号",
                    "address": "张江路88号",
                    "pname": "上海市",
                    "cityname": "上海市",
                    "adname": "浦东新区",
                    "location": "121.6000,31.2100",
                }
            ],
        }

    searcher = AMapMapSearcher(api_key="test-key", fetch_json=fake_fetch)

    candidates = searcher.search("张江路88号", city_hint="上海市")

    assert calls == [
        (
            "/v3/place/text",
            {
                "keywords": "张江路88号",
                "offset": "10",
                "page": "1",
                "extensions": "all",
                "city": "上海市",
                "citylimit": "true",
                "key": "test-key",
            },
        )
    ]
    assert candidates[0].full_address == "上海市浦东新区张江路88号"


def test_amap_searcher_raises_readable_error_when_socks_dependency_missing(monkeypatch) -> None:
    searcher = AMapMapSearcher(api_key="test-key")

    def raise_import_error(*args, **kwargs):
        raise ImportError("Using SOCKS proxy, but the 'socksio' package is not installed.")

    monkeypatch.setattr("app.location_agent.amap.httpx.get", raise_import_error)

    with pytest.raises(AMapSearchError) as exc_info:
        searcher.search("文三路18号", city_hint="杭州市")

    assert "socksio" in str(exc_info.value)
