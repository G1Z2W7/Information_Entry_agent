from __future__ import annotations

from app.location_agent.detail_parser import enrich_location_detail
from app.location_agent.models import LocationDetail


def test_enrich_location_detail_extracts_floor_and_room() -> None:
    detail = enrich_location_detail(LocationDetail(raw_text="5楼501", detail_type="unit_detail"))

    assert detail.detail_type == "unit_detail"
    assert detail.floor_text == "5楼"
    assert detail.room_text == "501"


def test_enrich_location_detail_extracts_direction_and_distance() -> None:
    detail = enrich_location_detail(
        LocationDetail(raw_text="右侧两百米", detail_type="relative_distance_detail")
    )

    assert detail.detail_type == "relative_distance_detail"
    assert detail.direction == "右侧"
    assert detail.distance_meters == 200
