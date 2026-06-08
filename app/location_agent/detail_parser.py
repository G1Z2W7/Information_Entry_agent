from __future__ import annotations

import re

from app.location_agent.models import LocationDetail


CHINESE_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def enrich_location_detail(detail: LocationDetail | None) -> LocationDetail | None:
    if detail is None:
        return None

    raw_text = detail.raw_text.strip()
    if not raw_text:
        return None

    if detail.detail_type == "unit_detail":
        return detail.model_copy(update=_parse_unit_detail(raw_text))

    if detail.detail_type == "relative_distance_detail":
        return detail.model_copy(update=_parse_relative_distance_detail(raw_text))

    return detail.model_copy(update=_parse_common_location_detail(raw_text))


def _parse_unit_detail(raw_text: str) -> dict[str, str | None]:
    update: dict[str, str | None] = {}

    floor_match = re.search(r"([A-Za-z]?\d+楼|[A-Za-z]?\d+层|地下\d+层|负\d+层)", raw_text)
    if floor_match:
        update["floor_text"] = floor_match.group(1)

    room_match = re.search(r"(?<!\d)(\d{2,5}[室号]?|[A-Za-z]-?\d{2,5})(?!\d)", raw_text)
    if room_match:
        update["room_text"] = room_match.group(1)

    building_match = re.search(r"([A-Za-z一二三四五六七八九十]+座|[A-Za-z一二三四五六七八九十]+馆|[A-Za-z]区)", raw_text)
    if building_match:
        update["building_text"] = building_match.group(1)

    return update


def _parse_relative_distance_detail(raw_text: str) -> dict[str, str | int | None]:
    update: dict[str, str | int | None] = _parse_common_location_detail(raw_text)

    direction_match = re.search(r"(左侧|右侧|左边|右边|前方|后方|前面|后面|旁边|对面|东侧|西侧|南侧|北侧)", raw_text)
    if direction_match:
        update["direction"] = direction_match.group(1)

    distance_match = re.search(r"(\d+)\s*米", raw_text)
    if distance_match:
        update["distance_meters"] = int(distance_match.group(1))
    else:
        chinese_distance_match = re.search(r"([一二两三四五六七八九十百零]+)米", raw_text)
        if chinese_distance_match:
            parsed = _parse_chinese_number(chinese_distance_match.group(1))
            if parsed is not None:
                update["distance_meters"] = parsed

    return update


def _parse_common_location_detail(raw_text: str) -> dict[str, str | None]:
    update: dict[str, str | None] = {}

    entrance_match = re.search(r"(东门|西门|南门|北门|正门|侧门|后门|入口|出口)", raw_text)
    if entrance_match:
        update["entrance_text"] = entrance_match.group(1)

    ordinal_match = re.search(r"(第[一二两三四五六七八九十\d]+家|第[一二两三四五六七八九十\d]+个)", raw_text)
    if ordinal_match:
        update["ordinal_text"] = ordinal_match.group(1)

    if any(token in raw_text for token in ("左转", "右转", "进去", "往前", "直走", "过了", "穿过")):
        update["path_instruction"] = raw_text

    return update


def _parse_chinese_number(value: str) -> int | None:
    if not value:
        return None

    total = 0
    current = 0
    unit = 1
    for char in reversed(value):
        if char == "十":
            unit = 10
            if current == 0:
                current = 1
        elif char == "百":
            unit = 100
            if current == 0:
                current = 1
        elif char in CHINESE_DIGITS:
            total += CHINESE_DIGITS[char] * unit
            current = CHINESE_DIGITS[char]
        else:
            return None

    return total or current or None
