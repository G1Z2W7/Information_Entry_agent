from __future__ import annotations

from fastapi.testclient import TestClient

from app.location_agent.models import (
    LocationAgentRequest,
    LocationAgentResponse,
    LocationCandidate,
    LocationState,
    LocationStatePhase,
)
from app.main import app


class FakeMapSearcher:
    def __init__(self) -> None:
        self.nearby_calls: list[tuple[float, float]] = []
        self.search_calls: list[tuple[str, str | None]] = []

    def nearby(self, latitude: float, longitude: float) -> list[LocationCandidate]:
        self.nearby_calls.append((latitude, longitude))
        return [
            LocationCandidate(
                candidate_id="nearby-1",
                label="浙江省杭州市西湖区文三路18号",
                province_name="浙江省",
                city_name="杭州市",
                district_name="西湖区",
                detail_address="文三路18号",
                full_address="浙江省杭州市西湖区文三路18号",
                formatted_address="浙江省杭州市西湖区文三路18号",
                latitude=latitude,
                longitude=longitude,
            )
        ]

    def search(self, query: str, city_hint: str | None = None) -> list[LocationCandidate]:
        self.search_calls.append((query, city_hint))
        return [
            LocationCandidate(
                candidate_id="search-1",
                label="上海市浦东新区张江路88号",
                province_name="上海市",
                city_name="上海市",
                district_name="浦东新区",
                detail_address="张江路88号",
                full_address="上海市浦东新区张江路88号",
                formatted_address="上海市浦东新区张江路88号",
                latitude=31.21,
                longitude=121.6,
            )
        ]


class FakeLocationAgentService:
    def __init__(self) -> None:
        self.requests: list[LocationAgentRequest] = []

    def handle(self, request: LocationAgentRequest) -> LocationAgentResponse:
        self.requests.append(request)
        return LocationAgentResponse(
            status="resolved",
            message="ok",
            suggested_reply="已识别到地址。",
            resolved_address=None,
            state=LocationState(phase=LocationStatePhase.RESOLVED),
        )


def test_location_agent_api_nearby_endpoint_uses_request_coordinates() -> None:
    from app.api.location_agent import get_location_map_searcher

    fake_searcher = FakeMapSearcher()
    app.dependency_overrides[get_location_map_searcher] = lambda: fake_searcher

    with TestClient(app) as client:
        response = client.post(
            "/api/location-agent/nearby",
            json={"latitude": 30.2741, "longitude": 120.1551},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_searcher.nearby_calls == [(30.2741, 120.1551)]
    assert response.json()["candidates"][0]["full_address"] == "浙江省杭州市西湖区文三路18号"


def test_location_agent_api_search_endpoint_uses_query_and_city_hint() -> None:
    from app.api.location_agent import get_location_map_searcher

    fake_searcher = FakeMapSearcher()
    app.dependency_overrides[get_location_map_searcher] = lambda: fake_searcher

    with TestClient(app) as client:
        response = client.post(
            "/api/location-agent/search",
            json={"query": "张江路88号", "city_hint": "上海市"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_searcher.search_calls == [("张江路88号", "上海市")]
    assert response.json()["candidates"][0]["district_name"] == "浦东新区"


def test_location_agent_api_resolve_endpoint_uses_standalone_service() -> None:
    from app.api.location_agent import get_location_agent_service

    fake_service = FakeLocationAgentService()
    app.dependency_overrides[get_location_agent_service] = lambda: fake_service

    with TestClient(app) as client:
        response = client.post(
            "/api/location-agent/resolve",
            json={"session_id": "location-api-1", "user_message": "浙江省杭州市西湖区文三路18号"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(fake_service.requests) == 1
    assert fake_service.requests[0].user_message == "浙江省杭州市西湖区文三路18号"
    assert response.json()["status"] == "resolved"
