from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent.enums import validate_structured_patch


class SessionStage(str, Enum):
    COLLECTING = "collecting"
    VALIDATING = "validating"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CREATING = "creating"
    COMPLETED = "completed"


class DistributorStatus(str, Enum):
    NORMAL = "normal"
    DISABLED = "disabled"


class NextActionType(str, Enum):
    REQUEST_FIELDS = "request_fields"
    FIX_INVALID_FIELDS = "fix_invalid_fields"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    ACKNOWLEDGE_PROGRESS = "acknowledge_progress"
    GUIDE_USER = "guide_user"


class MainInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distributorName: str | None = None
    distributorLevel: int = 1
    parentDistributorName: str | None = None
    customerEmail: str | None = None
    customerMobile: str | None = None
    salesUserName: str | None = None
    salesManagerName: str | None = None
    salesProductTypeName: str | None = None
    discount: float | None = None
    salesRegion: str | None = None
    provinceCode: str | None = None
    authorizedRegion: str | None = None
    belongRegion: str | None = None
    source: str | None = None
    erpCode: str | None = None
    issueDate: str | None = None
    expiryDate: str | None = None
    status: DistributorStatus | None = None
    providePoints: bool | None = None
    providePointsRatio: float | None = None
    industryLevel1: str | None = None
    industryLevel2: str | None = None
    industryLevel3: str | None = None
    mainCategory: str | None = None
    mainCategoryGrade: str | None = None
    businessType: str | None = None
    cooperationStatus: str | None = None
    ownBrandDisplay: str | None = None
    competitorBrandDisplay: str | None = None
    informationSource: str | None = None
    remark: str | None = None

    @model_validator(mode="after")
    def normalize_defaults(self) -> "MainInfo":
        if self.distributorLevel is None:
            self.distributorLevel = 1

        if self.providePoints is False:
            self.providePointsRatio = 0.0

        return self


class Contact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contactName: str | None = None
    position: str | None = None
    mobile: str | None = None
    wechat: str | None = None
    isPrimary: bool | None = None
    remark: str | None = None


class Site(BaseModel):
    model_config = ConfigDict(extra="forbid")

    siteType: str | None = None
    siteTypeName: str | None = None
    siteSubType: str | None = None
    hasStore: bool | None = None
    storeAreaRange: str | None = None
    fullAddress: str | None = None
    provinceName: str | None = None
    cityName: str | None = None
    districtName: str | None = None
    formattedAddress: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geoSource: str | None = None
    isPrimary: bool | None = None
    remark: str | None = None


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    code: str
    message: str
    raw_response: Any | None = None
    validated_at: datetime | None = None


class FieldMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_turn: int | None = None
    source_text: str | None = None
    normalized_from: str | None = None
    confidence: float | None = None
    updated_at: datetime | None = None


class SessionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    stage: SessionStage = SessionStage.COLLECTING
    main_info: MainInfo = Field(default_factory=MainInfo)
    contacts: list[Contact] = Field(default_factory=list)
    sites: list[Site] = Field(default_factory=list)
    validation_results: dict[str, ValidationResult] = Field(default_factory=dict)
    missing_required_fields: list[str] = Field(default_factory=list)
    awaiting_confirmation: bool = False
    creation_ready: bool = False
    last_asked_fields: list[str] = Field(default_factory=list)
    turn_count: int = 0
    history_summary: str = ""
    field_meta: dict[str, FieldMeta] = Field(default_factory=dict)
    created_result: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    message: str


class StructuredPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    patch: dict[str, Any]

    @model_validator(mode="after")
    def validate_patch(self) -> "StructuredPatchRequest":
        self.patch = validate_structured_patch(self.patch)
        return self


class CurrentLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float
    longitude: float
    accuracyMeters: float | None = None


class AddressResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    site_index: int = 0
    full_address: str | None = None
    current_location: CurrentLocation | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    reply: str
    stage: SessionStage
    missing_required_fields: list[str] = Field(default_factory=list)
    validation_results: dict[str, ValidationResult] = Field(default_factory=dict)
    state_summary: dict[str, Any] = Field(default_factory=dict)
    created_result: dict[str, Any] | None = None


class AddressResolutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    site_index: int = 0
    resolution_status: str
    message: str
    current_location: CurrentLocation | None = None
    full_address: str | None = None
    normalized_site: Site | None = None


class FieldOptionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: Any


class FieldOptionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    input_type: str
    options: list[FieldOptionItem] = Field(default_factory=list)


class FieldOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: dict[str, FieldOptionConfig] = Field(default_factory=dict)


class DialogAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: NextActionType
    fields: list[str] = Field(default_factory=list)
    reason: str = ""
