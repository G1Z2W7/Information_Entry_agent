from __future__ import annotations

from app.agent.models import Contact, DistributorStatus, MainInfo, SessionState
from app.agent.state import compute_missing_fields, create_initial_state, refresh_state_flags


def test_initial_state_reports_required_main_info_and_contact_fields() -> None:
    state = create_initial_state("session-1")

    assert "main_info.distributorName" in state.missing_required_fields
    assert "main_info.customerEmail" in state.missing_required_fields
    assert "main_info.distributorLevel" not in state.missing_required_fields
    assert "contacts[0].contactName" in state.missing_required_fields
    assert "contacts[0].wechat" in state.missing_required_fields


def test_second_level_distributor_requires_parent_name() -> None:
    state = SessionState(
        session_id="session-2",
        main_info=MainInfo(distributorLevel=2),
    )

    missing = compute_missing_fields(state)

    assert "main_info.parentDistributorName" in missing


def test_complete_contact_satisfies_contact_requirement() -> None:
    state = SessionState(
        session_id="session-3",
        main_info=MainInfo(
            distributorName="智行汽车",
            customerEmail="zhixing@example.com",
            customerMobile="13800138000",
            belongRegion="华东",
            erpCode="HZ001",
            status=DistributorStatus.NORMAL,
            providePoints=False,
            mainCategory="汽配",
            mainCategoryGrade="国内主流品牌为主",
            businessType="批发B2B",
            cooperationStatus="稳定合作｜已签约",
        ),
        contacts=[
            Contact(
                contactName="王磊",
                position="老板",
                mobile="13900001111",
                wechat="same_as_mobile",
            )
        ],
    )

    refreshed = refresh_state_flags(state)

    assert refreshed.missing_required_fields == []
    assert refreshed.creation_ready is True


def test_partial_contact_reports_only_missing_contact_subfields() -> None:
    state = SessionState(
        session_id="session-4",
        contacts=[Contact(contactName="王磊", position="老板")],
    )

    missing = compute_missing_fields(state)

    assert "contacts[0].mobile" in missing
    assert "contacts[0].wechat" in missing
    assert "contacts[0].contactName" not in missing
    assert "contacts[0].position" not in missing
