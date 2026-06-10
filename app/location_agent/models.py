from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class LocationStatePhase(str, Enum):
    IDLE = "idle"
    AWAITING_NEARBY_SELECTION = "awaiting_nearby_selection"
    AWAITING_SEARCH_SELECTION = "awaiting_search_selection"
    AWAITING_MORE_DETAIL = "awaiting_more_detail"
    AWAITING_MANUAL_INPUT = "awaiting_manual_input"
    AWAITING_USER_CONFIRMATION = "awaiting_user_confirmation"
    RESOLVED = "resolved"


class CurrentCoordinates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float
    longitude: float
    accuracy_meters: float | None = None


class LocationAdminHints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    province_name: str | None = None
    city_name: str | None = None
    district_name: str | None = None


class LocationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    label: str
    province_name: str | None = None
    city_name: str | None = None
    district_name: str | None = None
    detail_address: str | None = None
    full_address: str
    formatted_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class LocationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str
    detail_type: str
    floor_text: str | None = None
    room_text: str | None = None
    building_text: str | None = None
    direction: str | None = None
    distance_meters: int | None = None
    entrance_text: str | None = None
    path_instruction: str | None = None
    ordinal_text: str | None = None


class ResolvedLocationAddress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    province_name: str | None = None
    city_name: str | None = None
    district_name: str | None = None
    anchor_address: str | None = None
    location_detail_raw: str | None = None
    location_detail_type: str | None = None
    detail_address: str | None = None
    full_address: str
    formatted_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geo_source: str
    confidence: str


class LocationState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: LocationStatePhase = LocationStatePhase.IDLE
    candidates: list[LocationCandidate] = Field(default_factory=list)
    current_coordinates: CurrentCoordinates | None = None
    admin_hints: LocationAdminHints | None = None
    pending_location_detail: LocationDetail | None = None


class LocationSelectionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str


class LocationManualInputPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_address: str
    confirm: bool = False


class LocationAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_address_text: str | None = None
    address_type: str
    corrected_queries: list[str] = Field(default_factory=list)
    location_detail: LocationDetail | None = None
    admin_hints: LocationAdminHints | None = None
    missing_parts: list[str] = Field(default_factory=list)
    next_step: str | None = None


class LocationAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    user_message: str | None = None
    current_coordinates: CurrentCoordinates | None = None
    state: LocationState | None = None
    selection_payload: LocationSelectionPayload | None = None
    manual_input_payload: LocationManualInputPayload | None = None


class LocationAgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    message: str
    suggested_reply: str
    candidates: list[LocationCandidate] = Field(default_factory=list)
    resolved_address: ResolvedLocationAddress | None = None
    state: LocationState = Field(default_factory=LocationState)


class LocationCandidatesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[LocationCandidate] = Field(default_factory=list)


class LocationSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    city_hint: str | None = None


class LocationAgentConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    js_api_key: str | None = None
    web_service_enabled: bool = False
