from __future__ import annotations

from app.agent.models import DistributorStatus, MainInfo, SessionState
from app.agent.validators import MockValidationService, validate_changed_fields


def test_mock_validator_accepts_valid_required_fields() -> None:
    state = SessionState(
        session_id="session-validator-1",
        main_info=MainInfo(
            distributorName="智行汽车",
            customerMobile="13800138000",
            customerEmail="zhixing@example.com",
            belongRegion="华东",
            erpCode="HZ001",
            status=DistributorStatus.NORMAL,
            providePoints=False,
            mainCategory="汽配",
            mainCategoryGrade="国内主流品牌为主",
            businessType="批发B2B",
            cooperationStatus="稳定合作｜已签约",
        ),
    )

    validate_changed_fields(
        state,
        [
            "main_info.distributorName",
            "main_info.customerMobile",
            "main_info.customerEmail",
        ],
    )

    assert state.validation_results["main_info.distributorName"].valid is True
    assert state.validation_results["main_info.customerMobile"].valid is True
    assert state.validation_results["main_info.customerEmail"].valid is True


def test_mock_validator_rejects_invalid_mobile_and_email() -> None:
    state = SessionState(
        session_id="session-validator-2",
        main_info=MainInfo(
            distributorName="智行汽车",
            customerMobile="123456",
            customerEmail="bad-email",
        ),
    )

    validate_changed_fields(
        state,
        ["main_info.customerMobile", "main_info.customerEmail"],
    )

    assert state.validation_results["main_info.customerMobile"].valid is False
    assert state.validation_results["main_info.customerMobile"].code == "INVALID_MOBILE"
    assert state.validation_results["main_info.customerEmail"].valid is False
    assert state.validation_results["main_info.customerEmail"].code == "INVALID_EMAIL"


def test_mock_validator_allows_forced_name_failure_and_blocks_creation() -> None:
    state = SessionState(
        session_id="session-validator-3",
        main_info=MainInfo(
            distributorName="测试禁用公司",
            customerMobile="13800138000",
            customerEmail="zhixing@example.com",
            belongRegion="华东",
            erpCode="HZ001",
            status=DistributorStatus.NORMAL,
            providePoints=False,
            mainCategory="汽配",
            mainCategoryGrade="国内主流品牌为主",
            businessType="批发B2B",
            cooperationStatus="稳定合作｜已签约",
        ),
    )
    service = MockValidationService(invalid_names={"测试禁用公司"})

    validate_changed_fields(
        state,
        ["main_info.distributorName"],
        validation_service=service,
    )

    assert state.validation_results["main_info.distributorName"].valid is False
    assert state.creation_ready is False


def test_validate_changed_fields_only_revalidates_requested_paths() -> None:
    state = SessionState(
        session_id="session-validator-4",
        main_info=MainInfo(
            distributorName="智行汽车",
            customerMobile="13800138000",
            customerEmail="zhixing@example.com",
        ),
    )

    validate_changed_fields(state, ["main_info.customerMobile"])

    assert "main_info.customerMobile" in state.validation_results
    assert "main_info.customerEmail" not in state.validation_results
    assert "main_info.distributorName" not in state.validation_results
