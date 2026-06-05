from __future__ import annotations

from abc import ABC, abstractmethod
import re

from app.agent.models import (
    AddressResolutionRequest,
    AddressResolutionResponse,
)


class AddressResolver(ABC):
    @abstractmethod
    def resolve(self, request: AddressResolutionRequest) -> AddressResolutionResponse:
        raise NotImplementedError


class PlaceholderAddressResolver(AddressResolver):
    """Placeholder resolver kept for future mobile GPS + geocoding integration."""

    def resolve(self, request: AddressResolutionRequest) -> AddressResolutionResponse:
        return AddressResolutionResponse(
            session_id=request.session_id,
            site_index=request.site_index,
            resolution_status="not_implemented",
            message=(
                "地址解析接口占位已保留，当前未接入真实定位/地理编码服务。"
                "后续可将移动端当前位置和原始地址文本一并传入该接口。"
            ),
            current_location=request.current_location,
            full_address=request.full_address,
        )


MUNICIPALITIES = {"北京市", "天津市", "上海市", "重庆市"}


def parse_explicit_address_components(full_address: str | None) -> dict[str, str]:
    if not full_address:
        return {}

    text = full_address.strip()
    if not text:
        return {}

    result: dict[str, str] = {}

    province_match = re.match(
        r"^(北京市|天津市|上海市|重庆市|[^省]+省|[^区]+自治区|[^特]+特别行政区)",
        text,
    )
    remainder = text
    if province_match:
        province = province_match.group(1)
        result["provinceName"] = province
        remainder = text[len(province) :]
        if province in MUNICIPALITIES:
            result["cityName"] = province

    if "cityName" not in result:
        city_match = re.match(r"^([^市]+市|[^州]+州|[^地]+地区|[^盟]+盟)", remainder)
        if city_match:
            city = city_match.group(1)
            result["cityName"] = city
            remainder = remainder[len(city) :]

    district_match = re.match(r"^(.+?(?:区|县|旗|市))", remainder)
    if district_match:
        district = district_match.group(1)
        if len(district) <= 12:
            result["districtName"] = district

    return result
