from __future__ import annotations

import os
from typing import Any, Callable

import httpx

from app.location_agent.models import (
    CurrentCoordinates,
    LocationAdminHints,
    LocationAgentRequest,
    LocationAnalysis,
    LocationCandidate,
)


AMAP_BASE_URL = "https://restapi.amap.com"
MUNICIPALITIES = {"北京市", "天津市", "上海市", "重庆市"}


class AMapSearchError(RuntimeError):
    pass


JsonFetcher = Callable[[str, dict[str, str]], dict[str, Any]]


class AMapMapSearcher:
    def __init__(
        self,
        *,
        api_key: str,
        fetch_json: JsonFetcher | None = None,
        base_url: str = AMAP_BASE_URL,
        timeout_seconds: float = 10.0,
    ) -> None:
        if not api_key:
            raise AMapSearchError("AMAP_WEB_SERVICE_KEY is not configured.")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.fetch_json = fetch_json or self._fetch_json

    def nearby(self, latitude: float, longitude: float) -> list[LocationCandidate]:
        location = _serialize_location(latitude, longitude)
        regeo_payload = self._request(
            "/v3/geocode/regeo",
            {
                "location": location,
                "extensions": "all",
                "radius": "1000",
            },
        )
        around_payload = self._request(
            "/v3/place/around",
            {
                "location": location,
                "radius": "1000",
                "offset": "10",
                "page": "1",
                "extensions": "all",
            },
        )

        candidates: list[LocationCandidate] = []
        regeo_candidate = _candidate_from_regeo(location, regeo_payload)
        if regeo_candidate is not None:
            candidates.append(regeo_candidate)

        seen_ids = {candidate.candidate_id for candidate in candidates}
        for poi in around_payload.get("pois", []):
            candidate = _candidate_from_poi(poi)
            if candidate is None or candidate.candidate_id in seen_ids:
                continue
            seen_ids.add(candidate.candidate_id)
            candidates.append(candidate)
        return candidates

    def search(self, query: str, city_hint: str | None = None) -> list[LocationCandidate]:
        params = {
            "keywords": query,
            "offset": "10",
            "page": "1",
            "extensions": "all",
        }
        if city_hint:
            params["city"] = city_hint
            params["citylimit"] = "true"
        payload = self._request("/v3/place/text", params)
        return [candidate for poi in payload.get("pois", []) if (candidate := _candidate_from_poi(poi))]

    def _request(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        payload = self.fetch_json(path, {**params, "key": self.api_key})
        if str(payload.get("status")) != "1":
            info = str(payload.get("info") or payload.get("infocode") or "Unknown AMap error")
            raise AMapSearchError(info)
        return payload

    def _fetch_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        try:
            response = httpx.get(
                f"{self.base_url}{path}",
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except ImportError as exc:
            raise AMapSearchError(
                "SOCKS proxy support is missing in the container. Install socksio or httpx[socks]."
            ) from exc
        except httpx.TimeoutException as exc:
            raise AMapSearchError("AMap request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise AMapSearchError(f"AMap request failed with HTTP {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise AMapSearchError("AMap request failed.") from exc

        payload = response.json()
        if not isinstance(payload, dict):
            raise AMapSearchError("AMap returned an invalid response payload.")
        return payload


class HeuristicLocationAnalyzer:
    vague_markers = ("附近", "那边", "旁边", "边上", "那个", "这边", "周边")

    def analyze(self, request: LocationAgentRequest) -> LocationAnalysis:
        text = (request.user_message or "").strip()
        if not text:
            return LocationAnalysis(raw_address_text=None, address_type="unknown", next_step="use_current")

        admin_hints = _extract_admin_hints(text)
        if any(marker in text for marker in self.vague_markers):
            return LocationAnalysis(
                raw_address_text=text,
                address_type="fuzzy",
                admin_hints=admin_hints,
                missing_parts=["路名", "门牌号"],
                next_step="need_more_detail",
            )

        corrected_queries = [text]
        if admin_hints.city_name and not text.startswith(admin_hints.city_name):
            corrected_queries.append(f"{admin_hints.city_name}{text}")

        return LocationAnalysis(
            raw_address_text=text,
            address_type="precise",
            corrected_queries=_dedupe_strings(corrected_queries),
            admin_hints=admin_hints,
            next_step="search",
        )


class MissingCoordinatesProvider:
    def get_current_coordinates(self) -> CurrentCoordinates:
        raise RuntimeError("Current coordinates are required for nearby location lookup.")


def build_amap_map_searcher_from_env() -> AMapMapSearcher:
    return AMapMapSearcher(api_key=os.getenv("AMAP_WEB_SERVICE_KEY", "").strip())


def get_amap_js_api_key_from_env() -> str | None:
    value = os.getenv("AMAP_JS_API_KEY", "").strip()
    return value or None


def _candidate_from_regeo(location: str, payload: dict[str, Any]) -> LocationCandidate | None:
    regeocode = payload.get("regeocode")
    if not isinstance(regeocode, dict):
        return None

    formatted_address = _as_string(regeocode.get("formatted_address"))
    component = regeocode.get("addressComponent")
    if not isinstance(component, dict) or not formatted_address:
        return None

    province_name = _as_string(component.get("province"))
    city_name = _normalize_city_name(component.get("city"), province_name)
    district_name = _as_string(component.get("district"))
    detail_address = _detail_from_full_address(formatted_address, province_name, city_name, district_name)
    longitude, latitude = _parse_location(location)

    return LocationCandidate(
        candidate_id=f"regeo:{location}",
        label=formatted_address,
        province_name=province_name,
        city_name=city_name,
        district_name=district_name,
        detail_address=detail_address,
        full_address=formatted_address,
        formatted_address=formatted_address,
        latitude=latitude,
        longitude=longitude,
    )


def _candidate_from_poi(poi: Any) -> LocationCandidate | None:
    if not isinstance(poi, dict):
        return None

    candidate_id = _as_string(poi.get("id")) or _as_string(poi.get("location")) or _as_string(poi.get("name"))
    name = _as_string(poi.get("name")) or _as_string(poi.get("address"))
    if not candidate_id or not name:
        return None

    province_name = _as_string(poi.get("pname"))
    city_name = _normalize_city_name(poi.get("cityname"), province_name)
    district_name = _as_string(poi.get("adname"))
    detail_address = _as_string(poi.get("address")) or name
    full_address = _join_address_parts(province_name, city_name, district_name, detail_address)
    longitude, latitude = _parse_location(_as_string(poi.get("location")))

    return LocationCandidate(
        candidate_id=candidate_id,
        label=full_address,
        province_name=province_name,
        city_name=city_name,
        district_name=district_name,
        detail_address=detail_address,
        full_address=full_address,
        formatted_address=full_address,
        latitude=latitude,
        longitude=longitude,
    )


def _normalize_city_name(value: Any, province_name: str | None) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    city_name = _as_string(value)
    if city_name:
        return city_name
    if province_name in MUNICIPALITIES:
        return province_name
    return None


def _join_address_parts(
    province_name: str | None,
    city_name: str | None,
    district_name: str | None,
    detail_address: str | None,
) -> str:
    parts: list[str] = []
    for value in (province_name, city_name, district_name):
        if value and value not in parts:
            parts.append(value)
    if detail_address:
        parts.append(detail_address)
    return "".join(parts)


def _detail_from_full_address(
    full_address: str,
    province_name: str | None,
    city_name: str | None,
    district_name: str | None,
) -> str:
    detail = full_address
    for prefix in (province_name, city_name, district_name):
        if prefix and detail.startswith(prefix):
            detail = detail[len(prefix) :]
    return detail or full_address


def _extract_admin_hints(text: str) -> LocationAdminHints | None:
    province_name = None
    city_name = None
    district_name = None

    for suffix in ("省", "自治区", "特别行政区", "市"):
        index = text.find(suffix)
        if index > 0:
            value = text[: index + len(suffix)]
            if suffix == "市":
                city_name = value
            else:
                province_name = value
            break

    if "市" in text:
        city_index = text.find("市")
        if city_index > 0:
            city_name = text[: city_index + 1]

    for suffix in ("区", "县", "旗", "市"):
        index = text.find(suffix)
        if index > 0:
            district_name = text[: index + 1]
            break

    if not any((province_name, city_name, district_name)):
        return None
    return LocationAdminHints(
        province_name=province_name,
        city_name=city_name,
        district_name=district_name,
    )


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _serialize_location(latitude: float, longitude: float) -> str:
    return f"{longitude},{latitude}"


def _parse_location(location: str | None) -> tuple[float | None, float | None]:
    if not location:
        return None, None
    pieces = location.split(",", maxsplit=1)
    if len(pieces) != 2:
        return None, None
    try:
        return float(pieces[0]), float(pieces[1])
    except ValueError:
        return None, None


def _as_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None
