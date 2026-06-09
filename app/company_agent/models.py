from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CompanyCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    company_name: str
    source: str  # "qixin" | "web_search" | "both"
    match_confidence: str  # "high" | "medium" | "low"
    match_reason: str | None = None


class CompanyStatePhase(str, Enum):
    IDLE = "idle"
    AWAITING_SELECTION = "awaiting_selection"
    AWAITING_MANUAL_INPUT = "awaiting_manual_input"
    RESOLVED = "resolved"


class CompanyState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: CompanyStatePhase = CompanyStatePhase.IDLE
    candidates: list[CompanyCandidate] = Field(default_factory=list)
    raw_input: str = ""


class SelectionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str


class ManualInputPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str
    confirm: bool = False


class CompanyResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_input: str = ""
    state: CompanyState | None = None
    selection_payload: SelectionPayload | None = None
    manual_input_payload: ManualInputPayload | None = None


class CompanyResolveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str  # "resolved" | "need_select" | "need_manual_input"
    company_name: str | None = None
    candidates: list[CompanyCandidate] = Field(default_factory=list)
    suggested_reply: str = ""
    state: CompanyState
