from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.models import (
    AddressActionType,
    AddressResolutionRequest,
    Contact,
    CurrentLocation,
    LocationFlowStatus,
    MainInfo,
    SessionStage,
    SessionState,
    Site,
    StructuredPatchRequest,
)


def test_session_state_defaults_are_initialized() -> None:
    state = SessionState(session_id="session-1")

    assert state.stage == SessionStage.COLLECTING
    assert state.main_info.distributorLevel == 1
    assert state.contacts == []
    assert state.sites == []
    assert state.creation_ready is False
    assert state.location_state.status == LocationFlowStatus.IDLE
    assert state.location_state.dismissed is False


def test_invalid_status_value_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MainInfo(status="active")


def test_contact_model_allows_partial_progress_data() -> None:
    contact = Contact(contactName="王磊")

    assert contact.contactName == "王磊"
    assert contact.mobile is None
    assert contact.wechat is None


def test_provide_points_false_forces_ratio_to_zero() -> None:
    main_info = MainInfo(providePoints=False, providePointsRatio=1.0)

    assert main_info.providePoints is False
    assert main_info.providePointsRatio == 0.0


def test_structured_patch_request_accepts_supported_enum_fields() -> None:
    request = StructuredPatchRequest(
        session_id="session-structured-1",
        patch={
            "main_info": {
                "mainCategory": "汽配",
                "status": "normal",
                "providePoints": False,
            }
        },
    )

    assert request.patch["main_info"]["mainCategory"] == "汽配"
    assert request.patch["main_info"]["status"] == "normal"
    assert request.patch["main_info"]["providePoints"] is False


def test_structured_patch_request_rejects_invalid_enum_value() -> None:
    with pytest.raises(ValidationError):
        StructuredPatchRequest(
            session_id="session-structured-2",
            patch={"main_info": {"status": "active"}},
        )


def test_structured_patch_request_accepts_contact_fields() -> None:
    request = StructuredPatchRequest(
        session_id="session-structured-3",
        patch={
            "contacts": [
                {
                    "position": "销售",
                    "wechat": "same_as_mobile",
                }
            ]
        },
    )

    assert request.patch["contacts"][0]["position"] == "销售"
    assert request.patch["contacts"][0]["wechat"] == "same_as_mobile"


def test_site_model_accepts_future_geo_fields() -> None:
    site = Site(
        fullAddress="浙江省杭州市西湖区文三路18号",
        formattedAddress="浙江省杭州市西湖区文三路18号",
        latitude=30.2741,
        longitude=120.1551,
        geoSource="placeholder",
    )

    assert site.formattedAddress == "浙江省杭州市西湖区文三路18号"
    assert site.latitude == 30.2741
    assert site.longitude == 120.1551
    assert site.geoSource == "placeholder"


def test_address_resolution_request_accepts_current_location() -> None:
    request = AddressResolutionRequest(
        session_id="session-address-1",
        full_address="浙江省杭州市西湖区文三路18号",
        current_location=CurrentLocation(
            latitude=30.2741,
            longitude=120.1551,
            accuracyMeters=18.5,
        ),
    )

    assert request.current_location is not None
    assert request.current_location.latitude == 30.2741


def test_address_resolution_request_accepts_confirm_candidate_action() -> None:
    request = AddressResolutionRequest(
        session_id="session-address-2",
        action=AddressActionType.CONFIRM_CANDIDATE,
        candidate_id="cand-1",
    )

    assert request.action == AddressActionType.CONFIRM_CANDIDATE
    assert request.candidate_id == "cand-1"
