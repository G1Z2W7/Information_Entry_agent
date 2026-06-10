from __future__ import annotations

import re

from app.location_agent.detail_parser import enrich_location_detail
from app.location_agent.models import (
    LocationAdminHints,
    LocationAgentRequest,
    LocationAgentResponse,
    LocationAnalysis,
    LocationCandidate,
    LocationDetail,
    LocationState,
    LocationStatePhase,
    ResolvedLocationAddress,
)
from app.location_agent.tools import CoordinatesProvider, LocationAnalyzer, MapSearcher


class LocationAgentService:
    def __init__(
        self,
        *,
        coordinates_provider: CoordinatesProvider,
        analyzer: LocationAnalyzer,
        map_searcher: MapSearcher,
    ) -> None:
        self.coordinates_provider = coordinates_provider
        self.analyzer = analyzer
        self.map_searcher = map_searcher

    def handle(self, request: LocationAgentRequest) -> LocationAgentResponse:
        state = request.state or LocationState()

        if request.selection_payload is not None:
            return self._resolve_selected_candidate(state, request.selection_payload.candidate_id)

        if request.manual_input_payload is not None and request.manual_input_payload.confirm:
            return self._resolve_user_confirmed_address(state, request.manual_input_payload.full_address)

        analysis = self.analyzer.analyze(request)

        if self._should_use_current_location(request, analysis):
            return self._suggest_nearby_candidates(request.current_coordinates)

        if analysis.address_type == "fuzzy" or analysis.next_step == "need_more_detail":
            return self._request_more_detail(analysis)

        if analysis.address_type == "unknown":
            return self._request_manual_input(analysis)

        if analysis.address_type == "precise":
            return self._search_precise_address(analysis)

        return self._request_manual_input(analysis)

    def _should_use_current_location(
        self,
        request: LocationAgentRequest,
        analysis: LocationAnalysis,
    ) -> bool:
        if analysis.next_step == "use_current":
            return True
        return not (request.user_message or "").strip() and not analysis.raw_address_text

    def _suggest_nearby_candidates(self, current_coordinates) -> LocationAgentResponse:
        coordinates = current_coordinates or self.coordinates_provider.get_current_coordinates()
        candidates = self.map_searcher.nearby(coordinates.latitude, coordinates.longitude)
        return LocationAgentResponse(
            status="need_select",
            message="nearby candidates found",
            suggested_reply="我先按你当前所在位置给你几个附近候选；如果不是这里，请选择“不在当前位置”或直接手工输入地址。",
            candidates=candidates,
            state=LocationState(
                phase=LocationStatePhase.AWAITING_NEARBY_SELECTION,
                candidates=candidates,
                current_coordinates=coordinates,
            ),
        )

    def _request_more_detail(self, analysis: LocationAnalysis) -> LocationAgentResponse:
        missing_parts = "、".join(analysis.missing_parts) if analysis.missing_parts else "路名、门牌号"
        return LocationAgentResponse(
            status="need_more_detail",
            message="more detail required",
            suggested_reply=f"这个位置还不够精确，请补充{missing_parts}。",
            state=LocationState(
                phase=LocationStatePhase.AWAITING_MORE_DETAIL,
                admin_hints=analysis.admin_hints,
            ),
        )

    def _request_manual_input(self, analysis: LocationAnalysis) -> LocationAgentResponse:
        phase = (
            LocationStatePhase.AWAITING_USER_CONFIRMATION
            if analysis.admin_hints is not None
            else LocationStatePhase.AWAITING_MANUAL_INPUT
        )
        return LocationAgentResponse(
            status="need_manual_input",
            message="manual input required",
            suggested_reply="我暂时没法准确识别这个位置，请按“省/市/区（县）+ 路/街道 + 门牌/园区/市场/楼栋”补充。",
            state=LocationState(phase=phase, admin_hints=analysis.admin_hints),
        )

    def _search_precise_address(self, analysis: LocationAnalysis) -> LocationAgentResponse:
        location_detail = _recover_location_detail(
            analysis.raw_address_text,
            enrich_location_detail(analysis.location_detail),
        )
        queries = _build_search_queries(
            raw_address_text=analysis.raw_address_text,
            corrected_queries=analysis.corrected_queries,
            location_detail=location_detail,
        )
        city_hint = analysis.admin_hints.city_name if analysis.admin_hints is not None else None

        candidates_by_key: dict[str, LocationCandidate] = {}
        for index, query in enumerate(queries):
            query_results = self.map_searcher.search(query, city_hint)
            exact_candidate = _find_exact_candidate(query_results, analysis.raw_address_text)
            if index == 0 and exact_candidate is not None:
                return LocationAgentResponse(
                    status="resolved",
                    message="location resolved",
                    suggested_reply=f"已识别到地址：{_compose_full_address(exact_candidate, location_detail)}",
                    resolved_address=_candidate_to_resolved_address(
                        exact_candidate,
                        geo_source="map_precise",
                        location_detail=location_detail,
                    ),
                    state=LocationState(phase=LocationStatePhase.RESOLVED),
                )
            for candidate in query_results:
                key = candidate.candidate_id or candidate.full_address
                candidates_by_key[key] = candidate

        candidates = _normalize_candidates_for_selection(
            list(candidates_by_key.values()),
            raw_address_text=analysis.raw_address_text,
            location_detail=location_detail,
        )
        if len(candidates) == 1:
            return LocationAgentResponse(
                status="resolved",
                message="location resolved",
                suggested_reply=f"已识别到地址：{_compose_full_address(candidates[0], location_detail)}",
                resolved_address=_candidate_to_resolved_address(
                    candidates[0],
                    geo_source="map_precise",
                    location_detail=location_detail,
                ),
                state=LocationState(phase=LocationStatePhase.RESOLVED),
            )

        if len(candidates) > 1:
            detail_text = _detail_raw_text(location_detail)
            detail_hint = (
                f" 已保留你输入的细节“{detail_text}”，请选择它对应的锚点地址。"
                if detail_text
                else " 查到了多个可能的地址，请选择最接近的一项。"
            )
            return LocationAgentResponse(
                status="need_select",
                message="multiple candidates found",
                suggested_reply=f"查到了多个可能的地址，{detail_hint.strip()}",
                candidates=candidates,
                state=LocationState(
                    phase=LocationStatePhase.AWAITING_SEARCH_SELECTION,
                    candidates=candidates,
                    admin_hints=analysis.admin_hints,
                    pending_location_detail=location_detail,
                ),
            )

        return self._request_manual_input(analysis)

    def _resolve_selected_candidate(
        self,
        state: LocationState,
        candidate_id: str,
    ) -> LocationAgentResponse:
        for candidate in state.candidates:
            if candidate.candidate_id == candidate_id:
                return LocationAgentResponse(
                    status="resolved",
                    message="candidate selected",
                    suggested_reply=f"已选择地址：{_compose_full_address(candidate, state.pending_location_detail)}",
                    resolved_address=_candidate_to_resolved_address(
                        candidate,
                        geo_source="map_candidate_selected",
                        location_detail=state.pending_location_detail,
                    ),
                    state=LocationState(phase=LocationStatePhase.RESOLVED),
                )

        return LocationAgentResponse(
            status="need_select",
            message="candidate not found",
            suggested_reply="没有找到你选择的地址，请重新选择候选项。",
            candidates=state.candidates,
            state=state.model_copy(update={"phase": LocationStatePhase.AWAITING_SEARCH_SELECTION}),
        )

    def _resolve_user_confirmed_address(
        self,
        state: LocationState,
        full_address: str,
    ) -> LocationAgentResponse:
        hints = state.admin_hints or LocationAdminHints()
        detail_address = _extract_detail_address(full_address, hints)
        resolved_address = ResolvedLocationAddress(
            province_name=hints.province_name,
            city_name=hints.city_name,
            district_name=hints.district_name,
            detail_address=detail_address,
            full_address=full_address,
            formatted_address=None,
            latitude=None,
            longitude=None,
            geo_source="user_confirmed",
            confidence="low",
        )
        return LocationAgentResponse(
            status="resolved",
            message="user confirmed address",
            suggested_reply=f"已按你确认的地址保存：{full_address}",
            resolved_address=resolved_address,
            state=LocationState(phase=LocationStatePhase.RESOLVED, admin_hints=hints),
        )


def _candidate_to_resolved_address(
    candidate: LocationCandidate,
    *,
    geo_source: str,
    location_detail: LocationDetail | None = None,
) -> ResolvedLocationAddress:
    anchor_address = _prepare_anchor_detail_address(candidate.detail_address or candidate.full_address, location_detail)
    detail_address = _compose_detail_address(anchor_address, location_detail)
    full_address = _join_full_address(candidate, detail_address)
    return ResolvedLocationAddress(
        province_name=candidate.province_name,
        city_name=candidate.city_name,
        district_name=candidate.district_name,
        anchor_address=anchor_address,
        location_detail_raw=_detail_raw_text(location_detail),
        location_detail_type=location_detail.detail_type if location_detail is not None else None,
        detail_address=detail_address,
        full_address=full_address,
        formatted_address=full_address,
        latitude=candidate.latitude,
        longitude=candidate.longitude,
        geo_source=geo_source,
        confidence="high",
    )


def _extract_detail_address(full_address: str, hints: LocationAdminHints) -> str:
    detail = full_address
    for prefix in (hints.province_name, hints.city_name, hints.district_name):
        if prefix and detail.startswith(prefix):
            detail = detail[len(prefix) :]
    return detail or full_address


def _compose_full_address(candidate: LocationCandidate, location_detail: LocationDetail | None) -> str:
    anchor_address = _prepare_anchor_detail_address(candidate.detail_address or candidate.full_address, location_detail)
    detail_address = _compose_detail_address(anchor_address, location_detail)
    return _join_full_address(candidate, detail_address)


def _compose_detail_address(anchor_address: str, location_detail: LocationDetail | None) -> str:
    detail_text = _detail_raw_text(location_detail)
    if not detail_text:
        return anchor_address
    if detail_text in anchor_address:
        return anchor_address
    if (
        location_detail is not None
        and location_detail.building_text
        and location_detail.building_text in anchor_address
        and detail_text.startswith(location_detail.building_text)
    ):
        return f"{anchor_address}{detail_text[len(location_detail.building_text):]}"
    return f"{anchor_address}{detail_text}"


def _join_full_address(candidate: LocationCandidate, detail_address: str) -> str:
    parts: list[str] = []
    for value in (candidate.province_name, candidate.city_name, candidate.district_name):
        if value and value not in parts:
            parts.append(value)
    parts.append(detail_address)
    return "".join(parts)


def _normalize_anchor_detail_address(detail_address: str) -> str:
    normalized = detail_address.strip()
    normalized = re.sub(r"\([^)]*\)$", "", normalized)
    normalized = re.sub(r"(地下?\d+层.*)$", "", normalized)
    normalized = re.sub(r"(\d+楼.*)$", "", normalized)
    normalized = re.sub(r"(\d+层.*)$", "", normalized)
    return normalized.strip() or detail_address.strip()


def _prepare_anchor_detail_address(detail_address: str, location_detail: LocationDetail | None) -> str:
    normalized = _normalize_anchor_detail_address(detail_address)
    if location_detail is None or not location_detail.building_text:
        return normalized

    match = re.search(
        r"^(.*?)(\d+号楼|\d+栋|\d+幢|[A-Za-z一二三四五六七八九十]+座|[A-Za-z一二三四五六七八九十]+馆|[A-Za-z]区)$",
        normalized,
    )
    if match is None:
        return normalized

    anchor_building = match.group(2)
    if anchor_building == location_detail.building_text:
        return normalized

    return match.group(1).strip() or normalized


def _detail_raw_text(location_detail: LocationDetail | None) -> str | None:
    if location_detail is None:
        return None
    raw_text = location_detail.raw_text.strip()
    return raw_text or None


def _recover_location_detail(
    raw_address_text: str | None,
    location_detail: LocationDetail | None,
) -> LocationDetail | None:
    if location_detail is None or not raw_address_text:
        return location_detail

    raw_text = _detail_raw_text(location_detail)
    if not raw_text or not raw_address_text.endswith(raw_text):
        return location_detail

    prefix = raw_address_text[: -len(raw_text)].strip()
    building_prefix = _extract_building_suffix(prefix)
    if not building_prefix:
        return location_detail

    if raw_text.startswith(building_prefix):
        return location_detail

    return enrich_location_detail(location_detail.model_copy(update={"raw_text": f"{building_prefix}{raw_text}"}))


def _build_search_queries(
    *,
    raw_address_text: str | None,
    corrected_queries: list[str],
    location_detail: LocationDetail | None,
) -> list[str]:
    queries: list[str] = []
    detail_text = _detail_raw_text(location_detail)
    if raw_address_text and detail_text and raw_address_text not in corrected_queries:
        queries.append(raw_address_text)
    queries.extend(corrected_queries)
    if not queries and raw_address_text:
        queries.append(raw_address_text)

    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = query.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _find_exact_candidate(
    candidates: list[LocationCandidate],
    raw_address_text: str | None,
) -> LocationCandidate | None:
    if not raw_address_text:
        return None

    normalized_query = _normalize_address_text(raw_address_text)
    for candidate in candidates:
        for value in (candidate.full_address, candidate.formatted_address, candidate.detail_address):
            if value and _normalize_address_text(value) == normalized_query:
                return candidate
    return None


def _normalize_candidates_for_selection(
    candidates: list[LocationCandidate],
    *,
    raw_address_text: str | None,
    location_detail: LocationDetail | None,
) -> list[LocationCandidate]:
    if not candidates or location_detail is None:
        return candidates

    parent_hint = _extract_parent_anchor_hint(raw_address_text, location_detail)
    normalized_candidates: list[LocationCandidate] = []
    seen_addresses: set[str] = set()
    for candidate in candidates:
        normalized_candidate = _normalize_candidate_anchor(candidate, parent_hint)
        key = normalized_candidate.full_address
        if key in seen_addresses:
            continue
        seen_addresses.add(key)
        normalized_candidates.append(normalized_candidate)
    return normalized_candidates


def _normalize_candidate_anchor(candidate: LocationCandidate, parent_hint: str | None) -> LocationCandidate:
    detail_address = candidate.detail_address or candidate.full_address
    normalized_detail = _normalize_anchor_from_detail(detail_address, parent_hint)
    if normalized_detail == detail_address:
        return candidate

    full_address = _join_full_address(candidate, normalized_detail)
    return candidate.model_copy(
        update={
            "label": full_address,
            "detail_address": normalized_detail,
            "full_address": full_address,
            "formatted_address": full_address,
        }
    )


def _normalize_anchor_from_detail(detail_address: str, parent_hint: str | None) -> str:
    normalized = _normalize_anchor_detail_address(detail_address)
    if parent_hint:
        match = _find_longest_common_substring(parent_hint, normalized)
        if match and len(match) >= 2:
            index = normalized.find(match)
            if index >= 0:
                prefix = normalized[: index + len(match)].strip()
                if prefix:
                    return prefix
    return normalized


def _extract_parent_anchor_hint(
    raw_address_text: str | None,
    location_detail: LocationDetail | None,
) -> str | None:
    if not raw_address_text:
        return None

    detail_text = _detail_raw_text(location_detail)
    parent_text = raw_address_text
    if detail_text and raw_address_text.endswith(detail_text):
        parent_text = raw_address_text[: -len(detail_text)].strip()

    if not parent_text:
        return None

    landmark_match = re.search(
        r"([A-Za-z0-9\u4e00-\u9fa5]+(?:合生汇|广场|中心|大厦|大楼|天地|园区|创意园|创业园|商场|商城|万达广场|万象城|mall|Mall|MALL))$",
        parent_text,
    )
    if landmark_match is not None:
        return landmark_match.group(1)
    return parent_text


def _extract_building_suffix(text: str) -> str | None:
    match = re.search(
        r"(\d+号楼|\d+栋|\d+幢|[A-Za-z一二三四五六七八九十]+座|[A-Za-z]区)$",
        text,
    )
    if match is None:
        return None
    return match.group(1)


def _normalize_address_text(value: str) -> str:
    return re.sub(r"[\s()（）-]", "", value).lower()


def _find_longest_common_substring(left: str, right: str) -> str | None:
    best = ""
    left_length = len(left)
    for start in range(left_length):
        for end in range(start + 2, left_length + 1):
            candidate = left[start:end]
            if candidate in right and len(candidate) > len(best):
                best = candidate
    return best or None
