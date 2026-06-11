from __future__ import annotations

import re

from app.agent.dialog_policy import (
    build_guidance_action,
    classify_guidance_intent,
    decide_next_action,
    render_reply,
)
from app.agent.graph.state import DistributorGraphState
from app.agent.models import (
    ActiveFlow,
    ChatResponse,
    CompanyFlowStatus,
    LocationFlowStatus,
    SessionState,
)
from app.agent.state import create_initial_state, merge_state
from app.agent.validators import validate_changed_fields


RESUME_COMPANY_PATTERN = re.compile(r"(继续经销商名称确认|继续经销商确认|继续公司确认|继续公司名称确认)")
RESUME_LOCATION_PATTERN = re.compile(r"(继续地址确认|继续位置确认|地址继续|继续刚才地址)")
RETURN_MAIN_FLOW_PATTERN = re.compile(r"(返回信息录入|退出地址确认|先改主信息|返回主流程|暂停地址确认)")

STRUCTURED_FIELD_LABELS = {
    "main_info.distributorLevel": "经销商等级",
    "main_info.mainCategory": "主营品类",
    "main_info.mainCategoryGrade": "主营品类档次",
    "main_info.businessType": "经营类型",
    "main_info.cooperationStatus": "合作状态",
    "main_info.status": "经销商状态",
    "main_info.informationSource": "信息来源",
    "main_info.providePoints": "是否发放积分",
    "main_info.providePointsRatio": "积分发放比例",
}


def load_session_state(state: DistributorGraphState) -> DistributorGraphState:
    store = state["store"]
    session_id = state["session_id"]
    session_state = store.get(session_id) or create_initial_state(session_id)
    return {
        "session_state": session_state,
        "turn_number": session_state.turn_count + 1,
    }


def classify_turn_intent(state: DistributorGraphState) -> DistributorGraphState:
    session_state = state["session_state"]
    operation = state.get("operation", "chat")

    if operation == "structured_patch":
        return {"route": "structured_patch"}

    message = state.get("message", "")
    if (
        RESUME_COMPANY_PATTERN.search(message)
        and session_state.company_flow.status
        in {CompanyFlowStatus.ACTIVE, CompanyFlowStatus.PAUSED}
    ):
        return {"route": "resume_company"}

    if (
        RESUME_LOCATION_PATTERN.search(message)
        and session_state.location_flow.status
        in {LocationFlowStatus.ACTIVE, LocationFlowStatus.PAUSED}
    ):
        return {"route": "resume_location"}

    if session_state.active_flow == ActiveFlow.COMPANY:
        if RETURN_MAIN_FLOW_PATTERN.search(message):
            return {"route": "return_main_from_company"}
        return {"route": "company_active"}

    if session_state.active_flow == ActiveFlow.LOCATION:
        if RETURN_MAIN_FLOW_PATTERN.search(message):
            return {"route": "return_main_from_location"}
        return {"route": "location_active"}

    guidance_intent = classify_guidance_intent(message)
    if guidance_intent is not None:
        return {
            "guidance_intent": guidance_intent,
            "route": "guidance",
        }

    return {"route": "main"}


def apply_structured_patch(state: DistributorGraphState) -> DistributorGraphState:
    session_state = state["session_state"]
    patch = state.get("patch", {})

    merge_state(
        session_state,
        patch,
        turn_number=state["turn_number"],
        source_text="[structured_fields]",
    )
    validate_changed_fields(
        session_state,
        _collect_changed_paths(patch),
        validation_service=state.get("validation_service"),
    )
    return {"session_state": session_state}


def build_guidance_action_node(state: DistributorGraphState) -> DistributorGraphState:
    return {"action": build_guidance_action(state["guidance_intent"])}


def decide_next_action_node(state: DistributorGraphState) -> DistributorGraphState:
    return {"action": decide_next_action(state["session_state"])}


def resume_company_flow(state: DistributorGraphState) -> DistributorGraphState:
    session_state = state["session_state"]
    session_state.active_flow = ActiveFlow.COMPANY
    session_state.company_flow.status = CompanyFlowStatus.ACTIVE
    return {
        "reply": _build_company_resume_reply(session_state),
        "session_state": session_state,
    }


def resume_location_flow(state: DistributorGraphState) -> DistributorGraphState:
    session_state = state["session_state"]
    session_state.active_flow = ActiveFlow.LOCATION
    session_state.location_flow.status = LocationFlowStatus.ACTIVE
    return {
        "reply": _build_location_resume_reply(session_state),
        "session_state": session_state,
    }


def return_to_main_from_company(state: DistributorGraphState) -> DistributorGraphState:
    session_state = state["session_state"]
    session_state.active_flow = ActiveFlow.MAIN
    if session_state.company_flow.status == CompanyFlowStatus.ACTIVE:
        session_state.company_flow.status = CompanyFlowStatus.PAUSED
    action = decide_next_action(session_state)
    return {
        "action": action,
        "reply": (
            "已返回信息录入。经销商名称确认已暂停，可随时说“继续经销商确认”。\n\n"
            f"{render_reply(session_state, action)}"
        ),
        "session_state": session_state,
    }


def return_to_main_from_location(state: DistributorGraphState) -> DistributorGraphState:
    session_state = state["session_state"]
    session_state.active_flow = ActiveFlow.MAIN
    if session_state.location_flow.status == LocationFlowStatus.ACTIVE:
        session_state.location_flow.status = LocationFlowStatus.PAUSED
    action = decide_next_action(session_state)
    return {
        "action": action,
        "reply": (
            "已返回信息录入。地址确认已暂停，可随时说“继续地址确认”。\n\n"
            f"{render_reply(session_state, action)}"
        ),
        "session_state": session_state,
    }


def render_company_active(state: DistributorGraphState) -> DistributorGraphState:
    return {"reply": _build_company_active_reply(state["session_state"])}


def render_location_active(state: DistributorGraphState) -> DistributorGraphState:
    return {"reply": _build_location_active_reply(state["session_state"])}


def render_response(state: DistributorGraphState) -> DistributorGraphState:
    session_state = state["session_state"]
    reply = _resolve_reply(state, session_state)
    state["store"].save(session_state)
    response = ChatResponse(
        session_id=session_state.session_id,
        reply=reply,
        stage=session_state.stage,
        active_flow=session_state.active_flow,
        company_flow=session_state.company_flow,
        location_flow=session_state.location_flow,
        missing_required_fields=session_state.missing_required_fields,
        validation_results=session_state.validation_results,
        state_summary=_build_response_summary(session_state),
        created_result=session_state.created_result,
    )
    return {"response": response}


def _collect_changed_paths(patch: dict[str, object]) -> list[str]:
    return [f"main_info.{field_name}" for field_name in patch.get("main_info", {})]


def _build_structured_patch_reply(patch: dict[str, object], follow_up_reply: str) -> str:
    updated_labels = [
        STRUCTURED_FIELD_LABELS.get(f"main_info.{field_name}", f"main_info.{field_name}")
        for field_name in patch.get("main_info", {})
    ]
    if not updated_labels:
        return follow_up_reply
    return f"已更新：{'、'.join(updated_labels)}。\n\n{follow_up_reply}"


def _build_response_summary(state: SessionState) -> dict[str, object]:
    return {
        "main_info": {
            key: value
            for key, value in state.main_info.model_dump().items()
            if value is not None and value != ""
        },
        "contacts": [
            {
                key: value
                for key, value in contact.model_dump().items()
                if value is not None and value != ""
            }
            for contact in state.contacts
        ],
        "sites": [
            {
                key: value
                for key, value in site.model_dump().items()
                if value is not None and value != ""
            }
            for site in state.sites
        ],
    }


def _build_company_active_reply(state: SessionState) -> str:
    last_response = state.company_flow.last_response
    if last_response is not None:
        return (
            "当前正在确认经销商名称，请继续使用经销商确认卡片完成选择或查询。\n\n"
            f"{last_response.suggested_reply}"
        )
    return "当前正在确认经销商名称，请先完成名称确认；如果要先改其他信息，请说“返回信息录入”。"


def _build_company_resume_reply(state: SessionState) -> str:
    if state.company_flow.last_response is not None:
        return (
            "继续上次经销商名称确认。\n\n"
            f"{state.company_flow.last_response.suggested_reply}"
        )
    return "继续上次经销商名称确认。请在卡片中继续选择或输入经销商名称。"


def _build_location_active_reply(state: SessionState) -> str:
    if state.location_flow.prompt_mode == "current_location_consent":
        context_label = state.location_flow.site_context_label or "这个场地"
        return f"请先确认是否使用当前位置来为“{context_label}”推荐附近地址，或者直接手动补充地址。"
    if state.location_flow.last_response is not None:
        return (
            "当前正在确认地址，请继续使用位置确认卡片完成选择或补充。\n\n"
            f"{state.location_flow.last_response.suggested_reply}"
        )
    return "当前正在确认地址，请先完成位置确认；如果要先改主信息，请说“返回信息录入”。"


def _build_location_resume_reply(state: SessionState) -> str:
    if state.location_flow.prompt_mode == "current_location_consent":
        context_label = state.location_flow.site_context_label or "这个场地"
        return f"继续地址确认。请先确认是否使用当前位置为“{context_label}”推荐附近地址。"
    if state.location_flow.last_response is not None:
        return (
            "继续上次地址确认。\n\n"
            f"{state.location_flow.last_response.suggested_reply}"
        )
    return "继续上次地址确认。请在位置确认卡片中继续选择或补充地址。"


def _resolve_reply(
    state: DistributorGraphState,
    session_state: SessionState,
) -> str:
    if "reply" in state:
        return state["reply"]

    action = state["action"]
    follow_up_reply = render_reply(session_state, action)
    if state.get("operation") == "structured_patch":
        return _build_structured_patch_reply(state.get("patch", {}), follow_up_reply)
    return follow_up_reply
