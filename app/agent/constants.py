"""Shared constants for distributor agent state and validation."""

from __future__ import annotations

from typing import Final


MAIN_INFO_REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "distributorName",
    "distributorLevel",
    "customerEmail",
    "customerMobile",
    "belongRegion",
    "erpCode",
    "status",
    "providePoints",
    "providePointsRatio",
    "mainCategory",
    "mainCategoryGrade",
    "businessType",
    "cooperationStatus",
)

CONTACT_REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "contactName",
    "position",
    "mobile",
    "wechat",
)

CONTACT_REQUIRED_FIELD_PATHS: Final[tuple[str, ...]] = tuple(
    f"contacts[0].{field_name}" for field_name in CONTACT_REQUIRED_FIELDS
)

REQUIRED_VALIDATION_PATHS: Final[tuple[str, ...]] = (
    "main_info.distributorName",
    "main_info.customerMobile",
    "main_info.customerEmail",
)

