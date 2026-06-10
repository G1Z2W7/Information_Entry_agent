from __future__ import annotations

from abc import ABC, abstractmethod
import os
import re

import httpx

from app.agent.models import (
    AddressActionType,
    AddressResolutionRequest,
    AddressResolutionResponse,
    CurrentLocation,
    LocationCandidate,
    LocationFlowStatus,
    Site,
)


class AddressResolver(ABC):
    @abstractmethod
    def resolve(self, request: AddressResolutionRequest) -> AddressResolutionResponse:
        raise NotImplementedError


class PlaceholderAddressResolver(AddressResolver):
    """Fallback resolver kept for environments without configured map services."""

    def resolve(self, request: AddressResolutionRequest) -> AddressResolutionResponse:
        return AddressResolutionResponse(
            session_id=request.session_id,
            site_index=request.site_index,
            resolution_status="not_implemented",
            message=(
                "地址解析接口占位已保留，当前未接入真实定位/地理编码服务。"
                "后续可将移动端当前位置和原始地址文本一并传入该接口。"
            ),
            suggested_reply="当前未接入真实定位/地理编码服务。",
            current_location=request.current_location,
            full_address=request.full_address,
        )


class AMapAddressResolver(AddressResolver):
    def __init__(
        self,
        *,
        web_service_key: str,
        http_client: httpx.Client | None = None,
        base_url: str = "https://restapi.amap.com",
    ) -> None:
        self.web_service_key = web_service_key
        self.http_client = http_client or httpx.Client(base_url=base_url, timeout=10)

    def resolve(self, request: AddressResolutionRequest) -> AddressResolutionResponse:
        if request.action == AddressActionType.RESOLVE_TEXT:
            return self._resolve_text(request)
        if request.action == AddressActionType.USE_CURRENT_LOCATION:
            return self._resolve_current_location(request)
        raise ValueError(f"Unsupported address resolver action: {request.action}")

    def _resolve_text(self, request: AddressResolutionRequest) -> AddressResolutionResponse:
        full_address = (request.full_address or "").strip()
        geocodes = self._geocode_address(full_address)
        if geocodes:
            candidates = [
                _candidate_from_site(
                    _site_from_geocode(geocode, geo_source="amap_geocode"),
                    candidate_id=f"geo-{index + 1}",
                    confidence="high" if len(geocodes) == 1 else "medium",
                )
                for index, geocode in enumerate(geocodes[:5])
            ]
            normalized_site = _candidate_to_site(candidates[0])
            message = "已识别到地址候选，请确认。"
            return AddressResolutionResponse(
                session_id=request.session_id,
                site_index=request.site_index,
                resolution_status=LocationFlowStatus.AWAITING_USER_CONFIRMATION,
                message=message,
                suggested_reply=message,
                full_address=full_address,
                candidates=candidates,
                normalized_site=normalized_site,
            )

        parsed = parse_explicit_address_components(full_address)
        if parsed:
            fallback_site = Site(
                fullAddress=full_address,
                provinceName=parsed.get("provinceName"),
                cityName=parsed.get("cityName"),
                districtName=parsed.get("districtName"),
                geoSource="user_confirmed",
            )
            fallback_candidate = _candidate_from_site(
                fallback_site,
                candidate_id="user-confirmed-1",
                confidence="low",
            )
            message = "地图未找到完全匹配地址，请确认是否按用户输入地址保存。"
            return AddressResolutionResponse(
                session_id=request.session_id,
                site_index=request.site_index,
                resolution_status=LocationFlowStatus.AWAITING_USER_CONFIRMATION,
                message=message,
                suggested_reply=message,
                full_address=full_address,
                candidates=[fallback_candidate],
                normalized_site=fallback_site,
            )

        message = "当前地址还不够完整，请补充省市区、路名或门牌号。"
        return AddressResolutionResponse(
            session_id=request.session_id,
            site_index=request.site_index,
            resolution_status=LocationFlowStatus.AWAITING_MANUAL_INPUT,
            message=message,
            suggested_reply=message,
            full_address=full_address,
        )

    def _resolve_current_location(self, request: AddressResolutionRequest) -> AddressResolutionResponse:
        if request.current_location is None:
            raise ValueError("current_location is required for USE_CURRENT_LOCATION")

        regeocode = self._reverse_geocode(request.current_location)
        candidates = _candidates_from_regeocode(regeocode)
        message = "已根据当前位置找到附近候选地址，请确认。"
        return AddressResolutionResponse(
            session_id=request.session_id,
            site_index=request.site_index,
            resolution_status=LocationFlowStatus.AWAITING_NEARBY_SELECTION,
            message=message,
            suggested_reply=message,
            current_location=request.current_location,
            candidates=candidates,
            normalized_site=_candidate_to_site(candidates[0]) if candidates else None,
        )

    def _geocode_address(self, address: str) -> list[dict]:
        response = self.http_client.get(
            "/v3/geocode/geo",
            params={
                "key": self.web_service_key,
                "address": address,
            },
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("geocodes", []) if payload.get("status") == "1" else []

    def _reverse_geocode(self, current_location: CurrentLocation) -> dict:
        response = self.http_client.get(
            "/v3/geocode/regeo",
            params={
                "key": self.web_service_key,
                "location": f"{current_location.longitude},{current_location.latitude}",
                "extensions": "all",
            },
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("regeocode", {}) if payload.get("status") == "1" else {}


MUNICIPALITIES = {"北京市", "天津市", "上海市", "重庆市"}


def build_address_resolver_from_env() -> AddressResolver:
    web_service_key = os.getenv("AMAP_WEB_SERVICE_KEY", "").strip()
    if not web_service_key:
        return PlaceholderAddressResolver()
    return AMapAddressResolver(web_service_key=web_service_key)


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


def _site_from_geocode(geocode: dict, *, geo_source: str) -> Site:
    latitude, longitude = _parse_location(geocode.get("location"))
    city_value = geocode.get("city")
    if isinstance(city_value, list):
        city_value = city_value[0] if city_value else geocode.get("province")
    return Site(
        fullAddress=geocode.get("formatted_address"),
        provinceName=geocode.get("province"),
        cityName=city_value,
        districtName=geocode.get("district"),
        formattedAddress=geocode.get("formatted_address"),
        latitude=latitude,
        longitude=longitude,
        geoSource=geo_source,
    )


def _candidate_from_site(site: Site, *, candidate_id: str, confidence: str) -> LocationCandidate:
    return LocationCandidate(
        candidate_id=candidate_id,
        fullAddress=site.fullAddress or "",
        provinceName=site.provinceName,
        cityName=site.cityName,
        districtName=site.districtName,
        formattedAddress=site.formattedAddress or site.fullAddress,
        latitude=site.latitude,
        longitude=site.longitude,
        geoSource=site.geoSource,
        confidence=confidence,
    )


def _candidate_to_site(candidate: LocationCandidate) -> Site:
    return Site(
        fullAddress=candidate.fullAddress,
        provinceName=candidate.provinceName,
        cityName=candidate.cityName,
        districtName=candidate.districtName,
        formattedAddress=candidate.formattedAddress or candidate.fullAddress,
        latitude=candidate.latitude,
        longitude=candidate.longitude,
        geoSource=candidate.geoSource,
    )


def _candidates_from_regeocode(regeocode: dict) -> list[LocationCandidate]:
    address_component = regeocode.get("addressComponent", {})
    province = address_component.get("province")
    city = address_component.get("city")
    if isinstance(city, list):
        city = city[0] if city else province
    district = address_component.get("district")
    candidates: list[LocationCandidate] = []
    for index, poi in enumerate(regeocode.get("pois", [])[:5]):
        latitude, longitude = _parse_location(poi.get("location"))
        detail = poi.get("address") or poi.get("name") or ""
        full_address = "".join(filter(None, [province, city, district, detail]))
        candidates.append(
            LocationCandidate(
                candidate_id=poi.get("id") or f"nearby-{index + 1}",
                name=poi.get("name"),
                fullAddress=full_address,
                provinceName=province,
                cityName=city,
                districtName=district,
                formattedAddress=full_address,
                latitude=latitude,
                longitude=longitude,
                geoSource="amap_nearby",
                confidence="medium",
            )
        )

    if candidates:
        return candidates

    formatted_address = regeocode.get("formatted_address")
    if formatted_address:
        return [
            LocationCandidate(
                candidate_id="nearby-fallback-1",
                fullAddress=formatted_address,
                provinceName=province,
                cityName=city,
                districtName=district,
                formattedAddress=formatted_address,
                geoSource="amap_regeo",
                confidence="medium",
            )
        ]
    return []


def _parse_location(raw_location: str | None) -> tuple[float | None, float | None]:
    if not raw_location or "," not in raw_location:
        return None, None
    longitude_text, latitude_text = raw_location.split(",", 1)
    try:
        return float(latitude_text), float(longitude_text)
    except ValueError:
        return None, None
