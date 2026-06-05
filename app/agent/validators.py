from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from app.agent.constants import REQUIRED_VALIDATION_PATHS
from app.agent.models import SessionState, ValidationResult
from app.agent.state import refresh_state_flags


class ValidationService(ABC):
    @abstractmethod
    def validate_distributor_name(self, name: str) -> ValidationResult:
        raise NotImplementedError

    @abstractmethod
    def validate_mobile(self, mobile: str) -> ValidationResult:
        raise NotImplementedError

    @abstractmethod
    def validate_email(self, email: str) -> ValidationResult:
        raise NotImplementedError


class MockValidationService(ValidationService):
    """Mock validation logic used before real backend integration."""

    def __init__(
        self,
        *,
        invalid_names: set[str] | None = None,
        invalid_mobiles: set[str] | None = None,
        invalid_emails: set[str] | None = None,
    ) -> None:
        self.invalid_names = invalid_names or set()
        self.invalid_mobiles = invalid_mobiles or set()
        self.invalid_emails = invalid_emails or set()

    def validate_distributor_name(self, name: str) -> ValidationResult:
        candidate = name.strip()
        if candidate in self.invalid_names:
            return _build_result(False, "NAME_REJECTED", "mock rejected distributor name")
        if len(candidate) < 2:
            return _build_result(False, "NAME_TOO_SHORT", "distributor name is too short")
        return _build_result(True, "OK", "validated by mock")

    def validate_mobile(self, mobile: str) -> ValidationResult:
        candidate = mobile.strip()
        if candidate in self.invalid_mobiles:
            return _build_result(False, "MOBILE_REJECTED", "mock rejected mobile")
        if not re.fullmatch(r"1[3-9]\d{9}", candidate):
            return _build_result(False, "INVALID_MOBILE", "mobile format is invalid")
        return _build_result(True, "OK", "validated by mock")

    def validate_email(self, email: str) -> ValidationResult:
        candidate = email.strip()
        if candidate in self.invalid_emails:
            return _build_result(False, "EMAIL_REJECTED", "mock rejected email")
        if not re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", candidate):
            return _build_result(False, "INVALID_EMAIL", "email format is invalid")
        return _build_result(True, "OK", "validated by mock")


def validate_changed_fields(
    state: SessionState,
    changed_paths: list[str] | set[str] | tuple[str, ...],
    *,
    validation_service: ValidationService | None = None,
) -> SessionState:
    """Validate strong fields that were added or changed in the current turn."""
    service = validation_service or MockValidationService()
    changed_set = set(changed_paths)

    for field_path in REQUIRED_VALIDATION_PATHS:
        if changed_set and field_path not in changed_set:
            continue
        value = _get_field_value(state, field_path)
        if value in (None, ""):
            state.validation_results.pop(field_path, None)
            continue
        state.validation_results[field_path] = _dispatch_validation(service, field_path, value)

    return refresh_state_flags(state)


def validate_required_fields(
    state: SessionState,
    *,
    validation_service: ValidationService | None = None,
) -> SessionState:
    """Validate all present strong fields regardless of whether they changed."""
    return validate_changed_fields(
        state,
        REQUIRED_VALIDATION_PATHS,
        validation_service=validation_service,
    )


def _dispatch_validation(
    service: ValidationService,
    field_path: str,
    value: str,
) -> ValidationResult:
    if field_path == "main_info.distributorName":
        return service.validate_distributor_name(value)
    if field_path == "main_info.customerMobile":
        return service.validate_mobile(value)
    if field_path == "main_info.customerEmail":
        return service.validate_email(value)
    raise ValueError(f"Unsupported validation field path: {field_path}")


def _get_field_value(state: SessionState, field_path: str) -> Any:
    _, field_name = field_path.split(".", 1)
    return getattr(state.main_info, field_name)


def _build_result(valid: bool, code: str, message: str) -> ValidationResult:
    return ValidationResult(
        valid=valid,
        code=code,
        message=message,
        raw_response={"provider": "mock"},
        validated_at=datetime.now(timezone.utc),
    )
