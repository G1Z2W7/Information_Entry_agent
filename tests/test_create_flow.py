from __future__ import annotations

from app.agent.models import Contact, DistributorStatus, MainInfo, SessionStage, SessionState
from app.agent.service import AgentService
from app.agent.validators import MockValidationService


def _build_ready_state(session_id: str, *, distributor_name: str = "智行汽车") -> SessionState:
    return SessionState(
        session_id=session_id,
        stage=SessionStage.AWAITING_CONFIRMATION,
        awaiting_confirmation=True,
        creation_ready=True,
        main_info=MainInfo(
            distributorName=distributor_name,
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
                isPrimary=True,
            )
        ],
    )


def test_confirm_create_succeeds_when_state_is_ready() -> None:
    service = AgentService(validation_service=MockValidationService())
    state = _build_ready_state("session-create-1")
    service.store.save(state)

    response = service.process_chat("session-create-1", "确认创建")
    saved_state = service.store.get("session-create-1")

    assert response.stage == SessionStage.COMPLETED
    assert response.created_result is not None
    assert response.created_result["success"] is True
    assert "创建成功" in response.reply
    assert saved_state is not None
    assert saved_state.stage == SessionStage.COMPLETED
    assert saved_state.created_result is not None


def test_confirm_create_is_blocked_when_revalidation_fails() -> None:
    validation_service = MockValidationService(invalid_names={"测试禁用公司"})
    service = AgentService(validation_service=validation_service)
    state = _build_ready_state("session-create-2", distributor_name="测试禁用公司")
    service.store.save(state)

    response = service.process_chat("session-create-2", "可以，创建吧")
    saved_state = service.store.get("session-create-2")

    assert response.stage == SessionStage.VALIDATING
    assert response.created_result is None
    assert "校验未通过" in response.reply
    assert saved_state is not None
    assert saved_state.stage == SessionStage.VALIDATING
    assert saved_state.creation_ready is False
