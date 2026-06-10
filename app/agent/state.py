from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.agent.address_resolver import parse_explicit_address_components
from app.agent.constants import (
    CONTACT_REQUIRED_FIELDS,
    MAIN_INFO_REQUIRED_FIELDS,
    REQUIRED_VALIDATION_PATHS,
)
from app.agent.models import Contact, FieldMeta, MainInfo, SessionState, Site


def create_initial_state(session_id: str) -> SessionState:
    """Create a new session state with defaults and derived flags."""
    return refresh_state_flags(SessionState(session_id=session_id))


def merge_state(
    state: SessionState,
    patch: dict[str, Any],
    *,
    turn_number: int | None = None,
    source_text: str | None = None,
) -> SessionState:
    """Merge an extracted patch into the existing session state."""
    if not patch:
        return refresh_state_flags(state)

    if "main_info" in patch:
        _merge_main_info(
            state,
            patch["main_info"],
            turn_number=turn_number,
            source_text=source_text,
        )

    if "contacts" in patch:
        _merge_contacts(
            state,
            patch["contacts"],
            turn_number=turn_number,
            source_text=source_text,
        )

    if "sites" in patch:
        _merge_sites(
            state,
            patch["sites"],
            turn_number=turn_number,
            source_text=source_text,
        )

    state.turn_count = max(state.turn_count, turn_number or state.turn_count)
    return refresh_state_flags(state)


def refresh_state_flags(state: SessionState) -> SessionState:
    """Refresh derived state flags after any mutation."""
    state.missing_required_fields = compute_missing_fields(state)
    has_blocking_validation_failure = any(
        not result.valid
        for path, result in state.validation_results.items()
        if path in REQUIRED_VALIDATION_PATHS
    )
    state.creation_ready = (
        not state.missing_required_fields and not has_blocking_validation_failure
    )
    if not state.creation_ready:
        state.awaiting_confirmation = False
    return state


def compute_missing_fields(state: SessionState) -> list[str]:
    """Return required field paths that are still missing from the session state."""
    missing_fields: list[str] = []
    main_info = state.main_info

    for field_name in MAIN_INFO_REQUIRED_FIELDS:
        field_value = getattr(main_info, field_name, None)
        if _is_missing_scalar(field_value):
            missing_fields.append(f"main_info.{field_name}")

    if main_info.distributorLevel == 2 and _is_missing_scalar(
        main_info.parentDistributorName
    ):
        missing_fields.append("main_info.parentDistributorName")

    if not state.contacts:
        return missing_fields + [
            f"contacts[0].{field_name}" for field_name in CONTACT_REQUIRED_FIELDS
        ]

    if any(is_complete_contact(contact) for contact in state.contacts):
        return missing_fields

    best_contact_index, best_contact = _pick_best_contact_candidate(state.contacts)
    return missing_fields + _missing_contact_fields(best_contact, best_contact_index)


def is_complete_contact(contact: Contact) -> bool:
    """A contact counts as valid only when all required contact fields are present."""
    return all(not _is_missing_scalar(getattr(contact, field_name)) for field_name in CONTACT_REQUIRED_FIELDS)


def _merge_main_info(
    state: SessionState,
    incoming_main_info: dict[str, Any],
    *,
    turn_number: int | None,
    source_text: str | None,
) -> None:
    current_data = state.main_info.model_dump()

    for field_name, value in incoming_main_info.items():
        if _is_missing_scalar(value):
            continue
        current_data[field_name] = value
        _set_field_meta(
            state,
            f"main_info.{field_name}",
            value,
            turn_number=turn_number,
            source_text=source_text,
        )

    state.main_info = MainInfo.model_validate(current_data)


def _merge_contacts(
    state: SessionState,
    incoming_contacts: list[dict[str, Any]],
    *,
    turn_number: int | None,
    source_text: str | None,
) -> None:
    is_modification = _looks_like_modification_text(source_text)
    for incoming_contact_data in incoming_contacts:
        incoming_contact = Contact.model_validate(incoming_contact_data)
        matched_index = _find_contact_match_index(
            state.contacts,
            incoming_contact,
            is_modification=is_modification,
        )

        if matched_index is None:
            state.contacts.append(incoming_contact)
            matched_index = len(state.contacts) - 1
        else:
            merged_contact_data = state.contacts[matched_index].model_dump()
            for field_name, value in incoming_contact.model_dump().items():
                if _is_missing_scalar(value):
                    continue
                merged_contact_data[field_name] = value
            state.contacts[matched_index] = Contact.model_validate(merged_contact_data)

        _resolve_contact_wechat_alias(state, matched_index)

        resolved_contact = state.contacts[matched_index]
        for field_name, value in resolved_contact.model_dump().items():
            if _is_missing_scalar(value):
                continue
            _set_field_meta(
                state,
                f"contacts[{matched_index}].{field_name}",
                value,
                turn_number=turn_number,
                source_text=source_text,
            )

        if incoming_contact.isPrimary is True:
            _set_primary_contact(state, matched_index)

    _ensure_default_primary_contact(state)


def _merge_sites(
    state: SessionState,
    incoming_sites: list[dict[str, Any]],
    *,
    turn_number: int | None,
    source_text: str | None,
) -> None:
    is_modification = _looks_like_modification_text(source_text)
    for incoming_site_data in incoming_sites:
        enriched_site_data = _enrich_site_address_fields(incoming_site_data)
        incoming_site = Site.model_validate(enriched_site_data)
        matched_index = _find_site_match_index(
            state.sites,
            incoming_site,
            is_modification=is_modification,
        )

        if matched_index is None:
            state.sites.append(incoming_site)
            matched_index = len(state.sites) - 1
        else:
            merged_site_data = state.sites[matched_index].model_dump()
            for field_name, value in incoming_site.model_dump().items():
                if _is_missing_scalar(value):
                    continue
                merged_site_data[field_name] = value
            state.sites[matched_index] = Site.model_validate(merged_site_data)

        for field_name, value in incoming_site.model_dump().items():
            if _is_missing_scalar(value):
                continue
            _set_field_meta(
                state,
                f"sites[{matched_index}].{field_name}",
                value,
                turn_number=turn_number,
                source_text=source_text,
            )

        if incoming_site.isPrimary is True:
            _set_primary_site(state, matched_index)


def _missing_contact_fields(contact: Contact, index: int) -> list[str]:
    return [
        f"contacts[{index}].{field_name}"
        for field_name in CONTACT_REQUIRED_FIELDS
        if _is_missing_scalar(getattr(contact, field_name))
    ]


def _pick_best_contact_candidate(contacts: list[Contact]) -> tuple[int, Contact]:
    best_index = 0
    best_contact = contacts[0]
    best_score = _contact_completeness_score(best_contact)

    for index, contact in enumerate(contacts[1:], start=1):
        score = _contact_completeness_score(contact)
        if score > best_score:
            best_index = index
            best_contact = contact
            best_score = score

    return best_index, best_contact


def _contact_completeness_score(contact: Contact) -> int:
    return sum(
        1 for field_name in CONTACT_REQUIRED_FIELDS if not _is_missing_scalar(getattr(contact, field_name))
    )


def _find_contact_match_index(
    existing_contacts: list[Contact],
    incoming_contact: Contact,
    *,
    is_modification: bool = False,
) -> int | None:
    if incoming_contact.contactName:
        matching_indexes = [
            index
            for index, contact in enumerate(existing_contacts)
            if contact.contactName == incoming_contact.contactName
        ]
        if len(matching_indexes) == 1:
            return matching_indexes[0]

    if incoming_contact.mobile:
        matching_indexes = [
            index
            for index, contact in enumerate(existing_contacts)
            if contact.mobile == incoming_contact.mobile
        ]
        if len(matching_indexes) == 1:
            return matching_indexes[0]

    if incoming_contact.position:
        matching_indexes = [
            index
            for index, contact in enumerate(existing_contacts)
            if contact.position == incoming_contact.position
        ]
        if len(matching_indexes) == 1:
            return matching_indexes[0]

    if not incoming_contact.contactName and not incoming_contact.mobile:
        if len(existing_contacts) == 1:
            return 0

        primary_indexes = [
            index for index, contact in enumerate(existing_contacts) if contact.isPrimary is True
        ]
        if len(primary_indexes) == 1:
            return primary_indexes[0]

    if is_modification:
        if len(existing_contacts) == 1 and not _contact_looks_like_new_addition(incoming_contact):
            return 0

        primary_indexes = [
            index for index, contact in enumerate(existing_contacts) if contact.isPrimary is True
        ]
        if len(primary_indexes) == 1 and not _contact_looks_like_new_addition(incoming_contact):
            return primary_indexes[0]

    return None


def _find_site_match_index(
    existing_sites: list[Site],
    incoming_site: Site,
    *,
    is_modification: bool = False,
) -> int | None:
    for index, site in enumerate(existing_sites):
        if incoming_site.siteType and incoming_site.fullAddress:
            if (
                site.siteType == incoming_site.siteType
                and site.fullAddress == incoming_site.fullAddress
            ):
                return index

    if incoming_site.fullAddress:
        matching_indexes = [
            index
            for index, site in enumerate(existing_sites)
            if site.fullAddress == incoming_site.fullAddress
        ]
        if len(matching_indexes) == 1:
            return matching_indexes[0]

    if incoming_site.siteType:
        matching_indexes = [
            index
            for index, site in enumerate(existing_sites)
            if site.siteType == incoming_site.siteType
        ]
        if len(matching_indexes) == 1:
            return matching_indexes[0]

    if is_modification:
        if len(existing_sites) == 1:
            return 0

        primary_indexes = [
            index for index, site in enumerate(existing_sites) if site.isPrimary is True
        ]
        if len(primary_indexes) == 1:
            return primary_indexes[0]

    return None


def _set_field_meta(
    state: SessionState,
    field_path: str,
    value: Any,
    *,
    turn_number: int | None,
    source_text: str | None,
) -> None:
    state.field_meta[field_path] = FieldMeta(
        source_turn=turn_number,
        source_text=source_text,
        normalized_from=str(value),
        updated_at=datetime.now(timezone.utc),
    )


def _set_primary_contact(state: SessionState, primary_index: int) -> None:
    for index, contact in enumerate(state.contacts):
        state.contacts[index] = contact.model_copy(update={"isPrimary": index == primary_index})


def _ensure_default_primary_contact(state: SessionState) -> None:
    if not state.contacts:
        return
    if any(contact.isPrimary for contact in state.contacts):
        return
    state.contacts[0] = state.contacts[0].model_copy(update={"isPrimary": True})


def _set_primary_site(state: SessionState, primary_index: int) -> None:
    for index, site in enumerate(state.sites):
        state.sites[index] = site.model_copy(update={"isPrimary": index == primary_index})


def _resolve_contact_wechat_alias(state: SessionState, contact_index: int) -> None:
    contact = state.contacts[contact_index]
    if contact.wechat != "same_as_mobile":
        return
    if _is_missing_scalar(contact.mobile):
        return
    state.contacts[contact_index] = contact.model_copy(update={"wechat": contact.mobile})


def _enrich_site_address_fields(site_data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(site_data, dict):
        return site_data

    normalized = dict(site_data)
    parsed_components = parse_explicit_address_components(normalized.get("fullAddress"))
    for field_name, value in parsed_components.items():
        if _is_missing_scalar(normalized.get(field_name)):
            normalized[field_name] = value
    return normalized


def _is_missing_scalar(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _looks_like_modification_text(source_text: str | None) -> bool:
    if not source_text:
        return False
    return bool(
        re.search(r"(改成|改到|修改|换成|换到|更新|不是这个|写错|不对|调整成|改为)", source_text)
    )


def _contact_looks_like_new_addition(incoming_contact: Contact) -> bool:
    return bool(incoming_contact.contactName and incoming_contact.position)
