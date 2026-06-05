from __future__ import annotations

from datetime import datetime, timezone

from app.agent.dialog_policy import (
    build_guidance_action,
    classify_guidance_intent,
    decide_next_action,
    render_reply,
)
from app.agent.models import (
    Contact,
    DistributorStatus,
    MainInfo,
    NextActionType,
    SessionState,
    ValidationResult,
)


def test_dialog_policy_requests_grouped_fields_by_category() -> None:
    state = SessionState(
        session_id="session-dialog-1",
        missing_required_fields=[
            "main_info.customerEmail",
            "main_info.mainCategory",
            "contacts[0].contactName",
        ],
    )

    action = decide_next_action(state)
    reply = render_reply(state, action)

    assert action.action_type == NextActionType.REQUEST_FIELDS
    assert "main_info.customerEmail" in action.fields
    assert "主体信息（必填）" in reply
    assert "经营信息（必填）" in reply
    assert "联系人信息（至少 1 位，必填）" in reply
    assert "客户邮箱" in reply
    assert "主营品类" in reply
    assert "联系人姓名" in reply
    assert "非必填信息" in reply
    assert state.stage.value == "collecting"


def test_dialog_policy_prioritizes_validation_failure() -> None:
    state = SessionState(
        session_id="session-dialog-2",
        validation_results={
            "main_info.customerMobile": ValidationResult(
                valid=False,
                code="INVALID_MOBILE",
                message="mobile format is invalid",
                validated_at=datetime.now(timezone.utc),
            )
        },
    )

    action = decide_next_action(state)
    reply = render_reply(state, action)

    assert action.action_type == NextActionType.FIX_INVALID_FIELDS
    assert action.fields == ["main_info.customerMobile"]
    assert "联系人电话" not in reply
    assert "客户手机号" in reply
    assert state.stage.value == "validating"


def test_dialog_policy_enters_confirmation_when_ready() -> None:
    state = SessionState(
        session_id="session-dialog-3",
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
        creation_ready=True,
    )

    action = decide_next_action(state)
    reply = render_reply(state, action)

    assert action.action_type == NextActionType.AWAITING_CONFIRMATION
    assert "确认创建" in reply
    assert "智行汽车" in reply
    assert "微信 13900001111" in reply
    assert "当前还可以补充这些非必填信息" in reply
    assert "主体信息" in reply
    assert "经营信息" in reply
    assert "场地信息" in reply
    assert state.stage.value == "awaiting_confirmation"


def test_guidance_intent_classifies_greeting_and_identity_query() -> None:
    assert classify_guidance_intent("你好") == "greeting"
    assert classify_guidance_intent("你是谁") == "identity_query"
    assert classify_guidance_intent("需要哪些字段") == "help_query"
    assert classify_guidance_intent("今天天气怎么样") == "off_topic"
    assert classify_guidance_intent("客户手机号是13800138000") is None


def test_guidance_reply_uses_role_and_redirects_to_task() -> None:
    state = SessionState(
        session_id="session-dialog-4",
        missing_required_fields=[
            "main_info.distributorName",
            "main_info.customerMobile",
        ],
    )

    action = build_guidance_action("identity_query")
    reply = render_reply(state, action)

    assert action.action_type == NextActionType.GUIDE_USER
    assert "我是新增经销商信息收集助手" in reply
    assert "主体信息（必填）" in reply
    assert "经销商名称" in reply
    assert "客户手机号" in reply
