from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException

from app.location_agent.amap import (
    AMapSearchError,
    MissingCoordinatesProvider,
    build_amap_map_searcher_from_env,
    get_amap_js_api_key_from_env,
)
from app.location_agent.llm import DeepSeekLocationAnalyzer
from app.location_agent.models import (
    CurrentCoordinates,
    LocationAgentConfigResponse,
    LocationAgentRequest,
    LocationAgentResponse,
    LocationCandidatesResponse,
    LocationSearchRequest,
)
from app.location_agent.runtime_facade import LocationAgentRuntimeFacade
from app.location_agent.service import LocationAgentService
from app.location_agent.tools import MapSearcher


router = APIRouter(prefix="/api/location-agent", tags=["location-agent"])


def get_location_map_searcher() -> MapSearcher:
    return build_amap_map_searcher_from_env()


def get_location_agent_service(
    map_searcher: MapSearcher = Depends(get_location_map_searcher),
) -> LocationAgentRuntimeFacade:
    legacy_service = LocationAgentService(
        coordinates_provider=MissingCoordinatesProvider(),
        analyzer=DeepSeekLocationAnalyzer(),
        map_searcher=map_searcher,
    )
    return LocationAgentRuntimeFacade(
        legacy_service=legacy_service,
    )


@router.get("/config", response_model=LocationAgentConfigResponse)
def get_location_agent_config() -> LocationAgentConfigResponse:
    js_api_key = get_amap_js_api_key_from_env()
    web_service_enabled = bool(os.getenv("AMAP_WEB_SERVICE_KEY", "").strip())
    return LocationAgentConfigResponse(
        js_api_key=js_api_key,
        web_service_enabled=web_service_enabled,
    )


@router.post("/nearby", response_model=LocationCandidatesResponse)
def nearby_locations(
    request: CurrentCoordinates,
    map_searcher: MapSearcher = Depends(get_location_map_searcher),
) -> LocationCandidatesResponse:
    try:
        candidates = map_searcher.nearby(request.latitude, request.longitude)
    except (AMapSearchError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return LocationCandidatesResponse(candidates=candidates)


@router.post("/search", response_model=LocationCandidatesResponse)
def search_locations(
    request: LocationSearchRequest,
    map_searcher: MapSearcher = Depends(get_location_map_searcher),
) -> LocationCandidatesResponse:
    try:
        candidates = map_searcher.search(request.query, request.city_hint)
    except (AMapSearchError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return LocationCandidatesResponse(candidates=candidates)


@router.post("/resolve", response_model=LocationAgentResponse)
def resolve_location(
    request: LocationAgentRequest,
    service: LocationAgentRuntimeFacade = Depends(get_location_agent_service),
) -> LocationAgentResponse:
    try:
        return service.handle(request)
    except (AMapSearchError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
