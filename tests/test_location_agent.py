from __future__ import annotations

from app.location_agent.models import (
    CurrentCoordinates,
    LocationAdminHints,
    LocationAgentRequest,
    LocationAnalysis,
    LocationCandidate,
    LocationDetail,
    LocationManualInputPayload,
    LocationSelectionPayload,
    LocationState,
    LocationStatePhase,
)
from app.location_agent.service import LocationAgentService


class FakeCoordinatesProvider:
    def get_current_coordinates(self) -> CurrentCoordinates:
        return CurrentCoordinates(latitude=30.2741, longitude=120.1551, accuracy_meters=20.0)


class FakeAnalyzer:
    def __init__(self, analysis: LocationAnalysis) -> None:
        self.analysis = analysis

    def analyze(self, _request: LocationAgentRequest) -> LocationAnalysis:
        return self.analysis


class FakeMapSearcher:
    def __init__(
        self,
        *,
        nearby_candidates: list[LocationCandidate] | None = None,
        search_results: dict[str, list[LocationCandidate]] | None = None,
    ) -> None:
        self.nearby_candidates = nearby_candidates or []
        self.search_results = search_results or {}
        self.search_queries: list[tuple[str, str | None]] = []

    def nearby(self, latitude: float, longitude: float) -> list[LocationCandidate]:
        assert latitude == 30.2741
        assert longitude == 120.1551
        return self.nearby_candidates

    def search(self, query: str, city_hint: str | None = None) -> list[LocationCandidate]:
        self.search_queries.append((query, city_hint))
        return self.search_results.get(query, [])


def _candidate(
    candidate_id: str,
    full_address: str,
    *,
    province: str = "浙江省",
    city: str = "杭州市",
    district: str = "西湖区",
    detail: str = "文三路18号",
) -> LocationCandidate:
    return LocationCandidate(
        candidate_id=candidate_id,
        label=full_address,
        province_name=province,
        city_name=city,
        district_name=district,
        detail_address=detail,
        full_address=full_address,
        formatted_address=full_address,
        latitude=30.2741,
        longitude=120.1551,
    )


def test_location_agent_requests_current_location_candidates_when_user_did_not_provide_address() -> None:
    service = LocationAgentService(
        coordinates_provider=FakeCoordinatesProvider(),
        analyzer=FakeAnalyzer(
            LocationAnalysis(raw_address_text=None, address_type="unknown", next_step="use_current")
        ),
        map_searcher=FakeMapSearcher(
            nearby_candidates=[
                _candidate("nearby-1", "浙江省杭州市西湖区文三路18号"),
                _candidate("nearby-2", "浙江省杭州市西湖区天目山路1号", detail="天目山路1号"),
            ]
        ),
    )

    response = service.handle(LocationAgentRequest(session_id="location-1", user_message=""))

    assert response.status == "need_select"
    assert response.state.phase == LocationStatePhase.AWAITING_NEARBY_SELECTION
    assert len(response.candidates) == 2
    assert "不在当前位置" in response.suggested_reply
    assert "手工输入地址" in response.suggested_reply


def test_location_agent_returns_resolved_address_when_precise_search_hits_single_candidate() -> None:
    service = LocationAgentService(
        coordinates_provider=FakeCoordinatesProvider(),
        analyzer=FakeAnalyzer(
            LocationAnalysis(
                raw_address_text="浙江省杭州市西湖区文三路18号5楼501",
                address_type="precise",
                corrected_queries=["浙江省杭州市西湖区文三路18号"],
                location_detail=LocationDetail(raw_text="5楼501", detail_type="unit_detail"),
                next_step="search",
            )
        ),
        map_searcher=FakeMapSearcher(
            search_results={"浙江省杭州市西湖区文三路18号": [_candidate("search-1", "浙江省杭州市西湖区文三路18号")]}
        ),
    )

    response = service.handle(
        LocationAgentRequest(session_id="location-2", user_message="浙江省杭州市西湖区文三路18号5楼501")
    )

    assert response.status == "resolved"
    assert response.resolved_address is not None
    assert response.resolved_address.full_address == "浙江省杭州市西湖区文三路18号5楼501"
    assert response.resolved_address.detail_address == "文三路18号5楼501"
    assert response.resolved_address.geo_source == "map_precise"
    assert response.resolved_address.confidence == "high"


def test_location_agent_returns_candidate_selection_when_precise_search_has_multiple_matches() -> None:
    service = LocationAgentService(
        coordinates_provider=FakeCoordinatesProvider(),
        analyzer=FakeAnalyzer(
            LocationAnalysis(
                raw_address_text="五角场万达广场5楼501",
                address_type="precise",
                corrected_queries=["五角场万达广场"],
                location_detail=LocationDetail(raw_text="5楼501", detail_type="unit_detail"),
                next_step="search",
            )
        ),
        map_searcher=FakeMapSearcher(
            search_results={
                "五角场万达广场": [
                    _candidate(
                        "search-1",
                        "上海市杨浦区国宾路18号万达广场A栋",
                        province="上海市",
                        city="上海市",
                        district="杨浦区",
                        detail="国宾路18号万达广场A栋",
                    ),
                    _candidate(
                        "search-2",
                        "上海市杨浦区国宾路58号万达广场B栋3层",
                        province="上海市",
                        city="上海市",
                        district="杨浦区",
                        detail="国宾路58号万达广场B栋3层",
                    ),
                ]
            },
        ),
    )

    response = service.handle(
        LocationAgentRequest(session_id="location-3", user_message="五角场万达广场5楼501")
    )

    assert response.status == "need_select"
    assert response.state.phase == LocationStatePhase.AWAITING_SEARCH_SELECTION
    assert response.state.pending_location_detail is not None
    assert response.state.pending_location_detail.raw_text == "5楼501"
    assert [candidate.candidate_id for candidate in response.candidates] == ["search-1", "search-2"]
    assert "5楼501" in response.suggested_reply


def test_location_agent_resolves_selected_candidate_from_previous_search_state() -> None:
    service = LocationAgentService(
        coordinates_provider=FakeCoordinatesProvider(),
        analyzer=FakeAnalyzer(
            LocationAnalysis(raw_address_text="ignored", address_type="unknown", next_step="ignored")
        ),
        map_searcher=FakeMapSearcher(),
    )

    response = service.handle(
        LocationAgentRequest(
            session_id="location-4",
            state=LocationState(
                phase=LocationStatePhase.AWAITING_SEARCH_SELECTION,
                pending_location_detail=LocationDetail(raw_text="5楼501", detail_type="unit_detail"),
                candidates=[
                    _candidate(
                        "search-1",
                        "上海市杨浦区国宾路18号万达广场A栋",
                        province="上海市",
                        city="上海市",
                        district="杨浦区",
                        detail="国宾路18号万达广场A栋",
                    ),
                    _candidate(
                        "search-2",
                        "上海市杨浦区国宾路58号万达广场B栋3层",
                        province="上海市",
                        city="上海市",
                        district="杨浦区",
                        detail="国宾路58号万达广场B栋3层",
                    ),
                ],
            ),
            selection_payload=LocationSelectionPayload(candidate_id="search-2"),
        )
    )

    assert response.status == "resolved"
    assert response.resolved_address is not None
    assert response.resolved_address.full_address == "上海市杨浦区国宾路58号万达广场B栋5楼501"
    assert response.resolved_address.detail_address == "国宾路58号万达广场B栋5楼501"
    assert response.resolved_address.geo_source == "map_candidate_selected"


def test_location_agent_resolves_selected_anchor_with_relative_location_detail() -> None:
    service = LocationAgentService(
        coordinates_provider=FakeCoordinatesProvider(),
        analyzer=FakeAnalyzer(
            LocationAnalysis(raw_address_text="ignored", address_type="unknown", next_step="ignored")
        ),
        map_searcher=FakeMapSearcher(),
    )

    response = service.handle(
        LocationAgentRequest(
            session_id="location-4b",
            state=LocationState(
                phase=LocationStatePhase.AWAITING_SEARCH_SELECTION,
                pending_location_detail=LocationDetail(
                    raw_text="右侧两百米",
                    detail_type="relative_distance_detail",
                    direction="右侧",
                    distance_meters=200,
                ),
                candidates=[
                    _candidate(
                        "search-1",
                        "上海市浦东新区凌桥路123号中国石油加油站（凌桥第一站）",
                        province="上海市",
                        city="上海市",
                        district="浦东新区",
                        detail="凌桥路123号中国石油加油站（凌桥第一站）",
                    ),
                ],
            ),
            selection_payload=LocationSelectionPayload(candidate_id="search-1"),
        )
    )

    assert response.status == "resolved"
    assert response.resolved_address is not None
    assert response.resolved_address.location_detail_raw == "右侧两百米"
    assert response.resolved_address.location_detail_type == "relative_distance_detail"
    assert response.resolved_address.full_address == "上海市浦东新区凌桥路123号中国石油加油站（凌桥第一站）右侧两百米"


def test_location_agent_requests_more_detail_for_fuzzy_location() -> None:
    service = LocationAgentService(
        coordinates_provider=FakeCoordinatesProvider(),
        analyzer=FakeAnalyzer(
            LocationAnalysis(
                raw_address_text="杭州西湖边那个店",
                address_type="fuzzy",
                missing_parts=["路名", "门牌号"],
                next_step="need_more_detail",
            )
        ),
        map_searcher=FakeMapSearcher(),
    )

    response = service.handle(LocationAgentRequest(session_id="location-5", user_message="杭州西湖边那个店"))

    assert response.status == "need_more_detail"
    assert response.state.phase == LocationStatePhase.AWAITING_MORE_DETAIL
    assert "路名" in response.suggested_reply
    assert "门牌号" in response.suggested_reply


def test_location_agent_uses_corrected_queries_before_asking_user_to_select() -> None:
    service = LocationAgentService(
        coordinates_provider=FakeCoordinatesProvider(),
        analyzer=FakeAnalyzer(
            LocationAnalysis(
                raw_address_text="杭洲市西胡区文三路18号",
                address_type="precise",
                corrected_queries=["杭州市西湖区文三路18号", "浙江省杭州市西湖区文三路18号"],
                admin_hints=LocationAdminHints(city_name="杭州市"),
                next_step="search",
            )
        ),
        map_searcher=FakeMapSearcher(
            search_results={
                "杭州市西湖区文三路18号": [_candidate("search-1", "浙江省杭州市西湖区文三路18号")],
                "浙江省杭州市西湖区文三路18号": [
                    _candidate("search-1", "浙江省杭州市西湖区文三路18号"),
                    _candidate("search-2", "浙江省杭州市西湖区文三路18号1幢", detail="文三路18号1幢"),
                ],
            }
        ),
    )

    response = service.handle(
        LocationAgentRequest(session_id="location-6", user_message="杭洲市西胡区文三路18号")
    )

    assert response.status == "need_select"
    assert service.map_searcher.search_queries == [
        ("杭州市西湖区文三路18号", "杭州市"),
        ("浙江省杭州市西湖区文三路18号", "杭州市"),
    ]
    assert len(response.candidates) == 2


def test_location_agent_returns_user_confirmed_address_when_manual_confirmation_is_provided() -> None:
    service = LocationAgentService(
        coordinates_provider=FakeCoordinatesProvider(),
        analyzer=FakeAnalyzer(
            LocationAnalysis(raw_address_text="ignored", address_type="unknown", next_step="ignored")
        ),
        map_searcher=FakeMapSearcher(),
    )

    response = service.handle(
        LocationAgentRequest(
            session_id="location-7",
            state=LocationState(
                phase=LocationStatePhase.AWAITING_USER_CONFIRMATION,
                admin_hints=LocationAdminHints(
                    province_name="江苏省",
                    city_name="苏州市",
                    district_name="吴中区",
                ),
            ),
            manual_input_payload=LocationManualInputPayload(
                full_address="江苏省苏州市吴中区木渎镇金桥开发区5号仓旁边门面",
                confirm=True,
            ),
        )
    )

    assert response.status == "resolved"
    assert response.resolved_address is not None
    assert response.resolved_address.province_name == "江苏省"
    assert response.resolved_address.city_name == "苏州市"
    assert response.resolved_address.district_name == "吴中区"
    assert response.resolved_address.detail_address == "木渎镇金桥开发区5号仓旁边门面"
    assert response.resolved_address.geo_source == "user_confirmed"
    assert response.resolved_address.confidence == "low"
