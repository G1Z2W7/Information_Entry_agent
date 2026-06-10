from __future__ import annotations

import os
import re
from typing import Any

from app.agent.address_resolver import (
    AddressResolver,
    PlaceholderAddressResolver,
)
from app.agent.dialog_policy import (
    build_guidance_action,
    classify_guidance_intent,
    decide_next_action,
    render_reply,
)
from app.agent.enums import get_field_options_payload
from app.agent.extractor import (
    classify_llm_intent,
    extract_rule_based_patch,
    extract_llm_incremental_patch,
)
from app.agent.models import (
    ActiveFlow,
    CompanyCommitRequest,
    CompanyFlowSnapshot,
    CompanyFlowStatus,
    CompanyFlowSyncRequest,
    CompanySearchRequest,
    AddressResolutionRequest,
    AddressResolutionResponse,
    ChatResponse,
    FieldOptionsResponse,
    LocationCommitRequest,
    LocationFlowStatus,
    LocationFlowSyncRequest,
    LocationFlowSnapshot,
    SessionStage,
    SessionState,
)
from app.company_agent.models import CompanyResolveRequest, CompanyResolveResponse
from app.company_agent.service import CompanyAgentService
from app.agent.session_store import (
    SessionStore,
    build_session_store_from_env,
)
from app.agent.state import create_initial_state, merge_state
from app.agent.validators import (
    ValidationService,
    validate_changed_fields,
    validate_required_fields,
)


CONFIRM_CREATE_PATTERN = re.compile(
    r"(确认创建|确认提交|创建吧|提交吧|可以创建|确认新增|没问题.*提交|没问题.*创建|可以.*创建)"
)
MODIFICATION_HINT_PATTERN = re.compile(r"(改成|修改|补充|变更|换成|不是|不对)")
RESUME_COMPANY_PATTERN = re.compile(r"(继续经销商名称确认|继续经销商确认|继续公司确认|继续公司名称确认)")
RESUME_LOCATION_PATTERN = re.compile(r"(继续地址确认|继续位置确认|地址继续|继续刚才地址)")
RETURN_MAIN_FLOW_PATTERN = re.compile(r"(返回信息录入|退出地址确认|先改主信息|返回主流程|暂停地址确认)")
LOCATION_SITE_FIELDS = {
    "fullAddress",
    "provinceName",
    "cityName",
    "districtName",
    "formattedAddress",
    "latitude",
    "longitude",
    "geoSource",
}
SITE_CONTEXT_FIELDS = {
    "siteType",
    "siteTypeName",
    "siteSubType",
    "hasStore",
    "storeAreaRange",
    "remark",
}

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


class MockCreateService:
    """Mock create adapter used before the real backend create API is integrated."""

    def create_distributor(self, state: SessionState) -> dict[str, Any]:
        distributor_name = state.main_info.distributorName or "unknown"
        distributor_code = state.main_info.erpCode or ""
        return {
            "success": True,
            "distributorId": f"mock-{state.session_id}",
            "distributorName": distributor_name,
            "erpCode": distributor_code,
            "message": "mock create distributor success",
        }


class AgentService:
    def __init__(
        self,
        *,
        store: SessionStore | None = None,
        validation_service: ValidationService | None = None,
        create_service: MockCreateService | None = None,
        company_agent_service: CompanyAgentService | None = None,
        llm_client: Any | None = None,
        intent_llm_client: Any | None = None,
        address_resolver: AddressResolver | None = None,
    ) -> None:
        self.store = store or build_session_store_from_env()
        self.validation_service = validation_service
        self.create_service = create_service or MockCreateService()
        self.company_agent_service = company_agent_service or CompanyAgentService()
        self.llm_client = llm_client
        self.intent_llm_client = intent_llm_client
        self.address_resolver = address_resolver or PlaceholderAddressResolver()

    def get_field_options(self) -> FieldOptionsResponse:
        return FieldOptionsResponse(fields=get_field_options_payload())

    def resolve_address(
        self,
        request: AddressResolutionRequest,
    ) -> AddressResolutionResponse:
        return self.address_resolver.resolve(request)

    def sync_location_flow(self, request: LocationFlowSyncRequest) -> ChatResponse:
        state = self.store.get(request.session_id) or create_initial_state(request.session_id)
        state.active_flow = ActiveFlow.LOCATION
        state.location_flow.status = LocationFlowStatus.ACTIVE
        state.location_flow.prompt_mode = None
        state.location_flow.site_index = request.site_index
        state.location_flow.original_user_message = (
            request.original_user_message or state.location_flow.original_user_message
        )
        if request.current_coordinates is not None:
            state.location_flow.current_coordinates = request.current_coordinates
        state.location_flow.last_response = request.location_agent_response
        return self._finalize_response(
            state,
            reply=request.location_agent_response.suggested_reply or "地址确认状态已更新。",
        )

    def search_company_candidates(
        self,
        request: CompanySearchRequest,
    ) -> CompanyResolveResponse:
        return self.company_agent_service.search_candidates(request.keyword)

    def sync_company_flow(self, request: CompanyFlowSyncRequest) -> ChatResponse:
        state = self.store.get(request.session_id) or create_initial_state(request.session_id)
        state.active_flow = ActiveFlow.COMPANY
        state.company_flow.status = CompanyFlowStatus.ACTIVE
        state.company_flow.original_user_message = (
            request.original_user_message or state.company_flow.original_user_message
        )
        state.company_flow.last_response = request.company_agent_response
        return self._finalize_response(
            state,
            reply=request.company_agent_response.suggested_reply or "经销商名称确认状态已更新。",
        )

    def commit_company_flow(self, request: CompanyCommitRequest) -> ChatResponse:
        state = self.store.get(request.session_id) or create_initial_state(request.session_id)
        company_name = request.company_name.strip()
        if not company_name:
            raise RuntimeError("Company commit requires a non-empty company name.")

        patch = {"main_info": {"distributorName": company_name}}
        self._apply_patch(
            state,
            patch,
            turn_number=state.turn_count + 1,
            source_text="[company_agent_commit 更新]",
        )
        state.active_flow = ActiveFlow.MAIN
        state.company_flow.status = CompanyFlowStatus.COMPLETED
        if request.company_agent_response is not None:
            state.company_flow.last_response = request.company_agent_response

        action = decide_next_action(state)
        return self._finalize_response(
            state,
            reply=f"经销商名称已确认并录入。\n\n{render_reply(state, action)}",
        )

    def commit_location_flow(self, request: LocationCommitRequest) -> ChatResponse:
        state = self.store.get(request.session_id) or create_initial_state(request.session_id)
        resolved_address = request.location_agent_response.resolved_address
        if resolved_address is None:
            raise RuntimeError("Location commit requires a resolved address.")

        patch = {
            "sites": [
                {
                    "fullAddress": resolved_address.full_address,
                    "provinceName": resolved_address.province_name,
                    "cityName": resolved_address.city_name,
                    "districtName": resolved_address.district_name,
                    "formattedAddress": resolved_address.formatted_address,
                    "latitude": resolved_address.latitude,
                    "longitude": resolved_address.longitude,
                    "geoSource": resolved_address.geo_source,
                }
            ]
        }
        self._apply_patch(
            state,
            patch,
            turn_number=state.turn_count + 1,
            source_text="[location_agent_commit 更新]",
        )
        state.active_flow = ActiveFlow.MAIN
        state.location_flow.status = LocationFlowStatus.COMPLETED
        state.location_flow.prompt_mode = None
        state.location_flow.site_index = request.site_index
        state.location_flow.last_response = request.location_agent_response

        action = decide_next_action(state)
        return self._finalize_response(
            state,
            reply=f"地址已确认并录入。\n\n{render_reply(state, action)}",
        )

    def process_chat(self, session_id: str, message: str) -> ChatResponse:
        state = self.store.get(session_id) or create_initial_state(session_id)
        current_turn = state.turn_count + 1

        if self._should_resume_company_flow(message, state):
            state.active_flow = ActiveFlow.COMPANY
            state.company_flow.status = CompanyFlowStatus.ACTIVE
            return self._finalize_response(state, reply=_build_company_resume_reply(state))

        if self._should_resume_location_flow(message, state):
            state.active_flow = ActiveFlow.LOCATION
            state.location_flow.status = LocationFlowStatus.ACTIVE
            return self._finalize_response(state, reply=_build_location_resume_reply(state))

        if state.active_flow == ActiveFlow.COMPANY:
            if self._should_return_to_main_flow(message):
                state.active_flow = ActiveFlow.MAIN
                if state.company_flow.status == CompanyFlowStatus.ACTIVE:
                    state.company_flow.status = CompanyFlowStatus.PAUSED
                action = decide_next_action(state)
                return self._finalize_response(
                    state,
                    reply=f"已返回信息录入。经销商名称确认已暂停，可随时说“继续经销商确认”。\n\n{render_reply(state, action)}",
                )

            combined_patch = self._extract_incremental_patch(message, state)
            patch_without_location, location_handoff = _split_location_patch(combined_patch)
            patch_without_company, company_handoff = _split_company_patch(patch_without_location)

            if company_handoff is not None and not _patch_has_non_company_updates(patch_without_company):
                self._start_company_flow(
                    state,
                    original_user_message=company_handoff["original_user_message"],
                )
                return self._finalize_response(state, reply=_build_company_handoff_reply(state))

            if location_handoff is not None and not _patch_has_non_company_updates(patch_without_company):
                state.active_flow = ActiveFlow.MAIN
                state.company_flow.status = CompanyFlowStatus.PAUSED
                self._start_location_flow(
                    state,
                    site_index=location_handoff["site_index"],
                    original_user_message=location_handoff["original_user_message"],
                    prompt_mode=location_handoff["prompt_mode"],
                    site_context_label=location_handoff["site_context_label"],
                )
                return self._finalize_response(
                    state,
                    reply=(
                        "经销商名称确认已暂停，先处理你刚补充的地址信息。\n\n"
                        f"{_build_location_handoff_reply(state)}"
                    ),
                )

            if _patch_has_non_company_updates(patch_without_company):
                state.active_flow = ActiveFlow.MAIN
                state.company_flow.status = CompanyFlowStatus.PAUSED
                self._apply_patch(
                    state,
                    patch_without_company,
                    turn_number=current_turn,
                    source_text=message,
                )
                if location_handoff is not None:
                    self._start_location_flow(
                        state,
                        site_index=location_handoff["site_index"],
                        original_user_message=location_handoff["original_user_message"],
                        prompt_mode=location_handoff["prompt_mode"],
                        site_context_label=location_handoff["site_context_label"],
                    )
                    return self._finalize_response(state, reply=_build_location_handoff_reply(state))
                action = decide_next_action(state)
                return self._finalize_response(
                    state,
                    reply=f"经销商名称确认已暂停，先处理你刚补充的主信息。\n\n{render_reply(state, action)}",
                )

            return self._finalize_response(state, reply=_build_company_active_reply(state))

        if state.active_flow == ActiveFlow.LOCATION:
            if self._should_return_to_main_flow(message):
                state.active_flow = ActiveFlow.MAIN
                if state.location_flow.status == LocationFlowStatus.ACTIVE:
                    state.location_flow.status = LocationFlowStatus.PAUSED
                action = decide_next_action(state)
                return self._finalize_response(
                    state,
                    reply=f"已返回信息录入。地址确认已暂停，可随时说“继续地址确认”。\n\n{render_reply(state, action)}",
                )

            combined_patch = self._extract_incremental_patch(message, state)
            patch_without_location, location_handoff = _split_location_patch(combined_patch)
            if _patch_has_non_location_updates(patch_without_location):
                state.active_flow = ActiveFlow.MAIN
                state.location_flow.status = LocationFlowStatus.PAUSED
                self._apply_patch(
                    state,
                    patch_without_location,
                    turn_number=current_turn,
                    source_text=message,
                )
                action = decide_next_action(state)
                return self._finalize_response(
                    state,
                    reply=f"地址确认已暂停，先处理你刚补充的主信息。\n\n{render_reply(state, action)}",
                )
            if location_handoff is not None:
                state.location_flow.original_user_message = (
                    location_handoff["original_user_message"]
                    or state.location_flow.original_user_message
                )
            return self._finalize_response(state, reply=_build_location_active_reply(state))

        if self._should_attempt_create_before_extraction(message, state):
            return self._handle_create(state)

        guidance_intent = self._classify_guidance_intent(message, state)
        if guidance_intent is not None:
            action = build_guidance_action(guidance_intent)
            return self._finalize_response(state, reply=render_reply(state, action))

        combined_patch = self._extract_incremental_patch(message, state)
        patch_without_location, location_handoff = _split_location_patch(combined_patch)
        patch_without_company, company_handoff = _split_company_patch(patch_without_location)
        if patch_without_company:
            self._apply_patch(
                state,
                patch_without_company,
                turn_number=current_turn,
                source_text=message,
            )
        if company_handoff is not None:
            self._start_company_flow(
                state,
                original_user_message=company_handoff["original_user_message"],
            )
            return self._finalize_response(state, reply=_build_company_handoff_reply(state))
        if location_handoff is not None:
            self._start_location_flow(
                state,
                site_index=location_handoff["site_index"],
                original_user_message=location_handoff["original_user_message"],
                prompt_mode=location_handoff["prompt_mode"],
                site_context_label=location_handoff["site_context_label"],
            )
            return self._finalize_response(state, reply=_build_location_handoff_reply(state))

        if self._should_create(message, state, patch_without_company):
            return self._handle_create(state)

        action = decide_next_action(state)
        return self._finalize_response(state, reply=render_reply(state, action))

    def process_structured_patch(
        self,
        session_id: str,
        patch: dict[str, Any],
    ) -> ChatResponse:
        state = self.store.get(session_id) or create_initial_state(session_id)
        current_turn = state.turn_count + 1

        self._apply_patch(
            state,
            patch,
            turn_number=current_turn,
            source_text="[structured_fields]",
        )

        action = decide_next_action(state)
        return self._finalize_response(
            state,
            reply=_build_structured_patch_reply(patch, render_reply(state, action)),
        )

    def reset(self) -> None:
        self.store.clear()

    def _apply_patch(
        self,
        state: SessionState,
        patch: dict[str, Any],
        *,
        turn_number: int,
        source_text: str,
    ) -> None:
        merge_state(
            state,
            patch,
            turn_number=turn_number,
            source_text=source_text,
        )
        validate_changed_fields(
            state,
            _collect_changed_paths(patch),
            validation_service=self.validation_service,
        )

    def _finalize_response(
        self,
        state: SessionState,
        *,
        reply: str,
    ) -> ChatResponse:
        self.store.save(state)
        return ChatResponse(
            session_id=state.session_id,
            reply=reply,
            stage=state.stage,
            active_flow=state.active_flow,
            company_flow=state.company_flow,
            location_flow=state.location_flow,
            missing_required_fields=state.missing_required_fields,
            validation_results=state.validation_results,
            state_summary=_build_response_summary(state),
            created_result=state.created_result,
        )

    def _extract_llm_patch_if_enabled(
        self,
        message: str,
        state: SessionState,
    ) -> dict[str, Any]:
        if not self._llm_enabled():
            raise RuntimeError(
                "DeepSeek extraction is required, but DS_API_KEY or DS_MODEL is not configured."
            )

        return extract_llm_incremental_patch(
            message,
            state,
            llm_client=self.llm_client,
        )

    def _extract_incremental_patch(
        self,
        message: str,
        state: SessionState,
    ) -> dict[str, Any]:
        llm_patch = self._extract_llm_patch_if_enabled(message, state)
        rule_patch = extract_rule_based_patch(message)
        return _merge_extraction_patches(rule_patch, llm_patch)

    def _llm_enabled(self) -> bool:
        if self.llm_client is not None:
            return True
        if str(os.getenv("LLM_EXTRACTION_ENABLED", "true")).lower() != "true":
            return False
        api_key = os.getenv("DS_API_KEY", "")
        model = os.getenv("DS_MODEL", "")
        return bool(api_key and model)

    def _intent_llm_enabled(self) -> bool:
        if self.intent_llm_client is not None:
            return True
        if str(os.getenv("LLM_INTENT_ENABLED", "true")).lower() != "true":
            return False
        api_key = os.getenv("DS_API_KEY", "")
        model = os.getenv("DS_INTENT_MODEL") or os.getenv("DS_MODEL", "")
        return bool(api_key and model)

    def _classify_guidance_intent(
        self,
        message: str,
        state: SessionState,
    ) -> str | None:
        if self._intent_llm_enabled():
            try:
                llm_intent = classify_llm_intent(
                    message,
                    state,
                    llm_client=self.intent_llm_client,
                )
                if llm_intent in {"greeting", "identity_query", "help_query", "off_topic"}:
                    return llm_intent
                if llm_intent in {"task_input", "task_modify", "confirm_create"}:
                    return None
            except Exception:
                pass

        return classify_guidance_intent(message)

    def _should_create(
        self,
        message: str,
        state: SessionState,
        combined_patch: dict[str, Any],
    ) -> bool:
        if combined_patch:
            return False
        if not state.awaiting_confirmation:
            return False
        if not state.creation_ready:
            return False
        if not CONFIRM_CREATE_PATTERN.search(message):
            return False
        if MODIFICATION_HINT_PATTERN.search(message):
            return False
        return True

    def _should_attempt_create_before_extraction(
        self,
        message: str,
        state: SessionState,
    ) -> bool:
        if not state.awaiting_confirmation:
            return False
        if not state.creation_ready:
            return False
        if not CONFIRM_CREATE_PATTERN.search(message):
            return False
        if MODIFICATION_HINT_PATTERN.search(message):
            return False
        return True

    def _handle_create(self, state: SessionState) -> ChatResponse:
        validate_required_fields(state, validation_service=self.validation_service)
        action = decide_next_action(state)
        if not state.creation_ready or state.stage != SessionStage.AWAITING_CONFIRMATION:
            return self._finalize_response(state, reply=render_reply(state, action))

        state.stage = SessionStage.CREATING
        created_result = self.create_service.create_distributor(state)
        state.created_result = created_result
        state.awaiting_confirmation = False
        state.stage = SessionStage.COMPLETED

        return self._finalize_response(
            state,
            reply=(
                f"经销商创建成功：{created_result['distributorName']}。"
                f"编号 {created_result['distributorId']}。"
            ),
        )

    def _start_company_flow(
        self,
        state: SessionState,
        *,
        original_user_message: str,
    ) -> None:
        company_response = self.company_agent_service.resolve(
            CompanyResolveRequest(user_input=original_user_message)
        )
        company_response = _normalize_company_handoff_response(
            company_response,
            raw_input=original_user_message,
        )
        state.active_flow = ActiveFlow.COMPANY
        state.company_flow = CompanyFlowSnapshot(
            status=CompanyFlowStatus.ACTIVE,
            original_user_message=original_user_message,
            last_response=company_response,
        )

    def _start_location_flow(
        self,
        state: SessionState,
        *,
        site_index: int,
        original_user_message: str | None,
        prompt_mode: str | None = None,
        site_context_label: str | None = None,
    ) -> None:
        state.active_flow = ActiveFlow.LOCATION
        state.location_flow = LocationFlowSnapshot(
            status=LocationFlowStatus.ACTIVE,
            site_index=site_index,
            prompt_mode=prompt_mode,
            site_context_label=site_context_label,
            original_user_message=original_user_message,
        )

    def _should_resume_company_flow(
        self,
        message: str,
        state: SessionState,
    ) -> bool:
        if not RESUME_COMPANY_PATTERN.search(message):
            return False
        return state.company_flow.status in {
            CompanyFlowStatus.ACTIVE,
            CompanyFlowStatus.PAUSED,
        }

    def _should_resume_location_flow(
        self,
        message: str,
        state: SessionState,
    ) -> bool:
        if not RESUME_LOCATION_PATTERN.search(message):
            return False
        return state.location_flow.status in {
            LocationFlowStatus.ACTIVE,
            LocationFlowStatus.PAUSED,
        }

    def _should_return_to_main_flow(self, message: str) -> bool:
        return bool(RETURN_MAIN_FLOW_PATTERN.search(message))


def _collect_changed_paths(patch: dict[str, Any]) -> list[str]:
    changed_paths: list[str] = []
    for field_name in patch.get("main_info", {}):
        changed_paths.append(f"main_info.{field_name}")
    return changed_paths


def _build_structured_patch_reply(patch: dict[str, Any], follow_up_reply: str) -> str:
    updated_labels = []
    for field_name in patch.get("main_info", {}):
        updated_labels.append(
            STRUCTURED_FIELD_LABELS.get(f"main_info.{field_name}", f"main_info.{field_name}")
        )

    if not updated_labels:
        return follow_up_reply

    return f"已更新：{'、'.join(updated_labels)}。\n\n{follow_up_reply}"


def _split_location_patch(
    patch: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not patch:
        return {}, None

    location_handoff: dict[str, Any] | None = None
    retained_patch = {key: value for key, value in patch.items() if key != "sites"}
    incoming_sites = patch.get("sites", [])
    retained_sites: list[dict[str, Any]] = []

    if isinstance(incoming_sites, list):
        for index, site in enumerate(incoming_sites):
            if not isinstance(site, dict):
                continue
            location_site_fields = {
                key: value
                for key, value in site.items()
                if key in LOCATION_SITE_FIELDS and value not in (None, "")
            }
            site_context_fields = {
                key: value
                for key, value in site.items()
                if key in SITE_CONTEXT_FIELDS and value not in (None, "")
            }
            non_location_site_fields = {
                key: value
                for key, value in site.items()
                if key not in LOCATION_SITE_FIELDS and value not in (None, "")
            }
            if location_handoff is None and location_site_fields:
                location_handoff = {
                    "site_index": index,
                    "original_user_message": _build_location_entry_text(location_site_fields),
                    "prompt_mode": "address_text",
                    "site_context_label": _build_site_context_label(site_context_fields),
                }
            elif location_handoff is None and site_context_fields:
                location_handoff = {
                    "site_index": index,
                    "original_user_message": None,
                    "prompt_mode": "current_location_consent",
                    "site_context_label": _build_site_context_label(site_context_fields),
                }
            if non_location_site_fields:
                retained_sites.append(non_location_site_fields)

    if retained_sites:
        retained_patch["sites"] = retained_sites

    return retained_patch, location_handoff


def _split_company_patch(
    patch: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not patch:
        return {}, None

    retained_patch = {key: value for key, value in patch.items() if key != "main_info"}
    incoming_main_info = patch.get("main_info", {})
    retained_main_info: dict[str, Any] = {}
    company_handoff: dict[str, Any] | None = None

    if isinstance(incoming_main_info, dict):
        for field_name, value in incoming_main_info.items():
            if field_name == "distributorName" and isinstance(value, str) and value.strip():
                company_handoff = {"original_user_message": value.strip()}
                continue
            retained_main_info[field_name] = value

    if retained_main_info:
        retained_patch["main_info"] = retained_main_info

    return retained_patch, company_handoff


def _build_location_entry_text(location_site_fields: dict[str, Any]) -> str | None:
    for field_name in ("fullAddress", "formattedAddress"):
        value = location_site_fields.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()

    components = [
        location_site_fields.get("provinceName"),
        location_site_fields.get("cityName"),
        location_site_fields.get("districtName"),
    ]
    combined = "".join(str(value).strip() for value in components if value)
    return combined or None


def _normalize_company_handoff_response(
    response: CompanyResolveResponse,
    *,
    raw_input: str,
) -> CompanyResolveResponse:
    if response.status != "resolved" or not response.company_name:
        return response

    candidate = response.candidates[0] if response.candidates else None
    normalized_candidate = candidate or {
        "candidate_id": "verified_0",
        "company_name": response.company_name,
        "source": "both",
        "match_confidence": "high",
        "match_reason": None,
    }
    return CompanyResolveResponse.model_validate(
        {
            "status": "need_select",
            "suggested_reply": "已找到启信宝候选，请确认是否使用该经销商名称。",
            "candidates": [normalized_candidate],
            "state": {
                "phase": "awaiting_selection",
                "candidates": [normalized_candidate],
                "raw_input": raw_input,
            },
        }
    )


def _patch_has_non_company_updates(patch: dict[str, Any]) -> bool:
    if patch.get("main_info"):
        return True
    if patch.get("contacts"):
        return True
    if patch.get("sites"):
        return True
    return False


def _patch_has_non_location_updates(patch: dict[str, Any]) -> bool:
    if patch.get("main_info"):
        return True
    if patch.get("contacts"):
        return True
    if patch.get("sites"):
        return True
    return False


def _build_company_handoff_reply(state: SessionState) -> str:
    raw_name = state.company_flow.original_user_message or "当前经销商名称"
    last_response = state.company_flow.last_response
    if last_response is None:
        return (
            f"已识别到经销商名称“{raw_name}”，现在进入名称确认。"
            "请在前端卡片中选择候选公司；如果没有，请继续输入并实时查询启信宝。"
        )
    if last_response.status == "resolved" and last_response.company_name:
        return (
            f"已根据“{raw_name}”找到候选公司“{last_response.company_name}”。"
            "请在前端卡片中确认是否使用该经销商名称。"
        )
    if last_response.status == "need_select":
        return (
            f"已根据“{raw_name}”查到多个经销商候选。"
            "请在前端下拉列表中选择；如果没有想要的结果，可继续输入并实时查询启信宝。"
        )
    return (
        f"暂时没为“{raw_name}”找到可直接确认的经销商名称。"
        "请在前端卡片中继续输入名称，系统会实时查询启信宝候选。"
    )


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


def _build_location_handoff_reply(state: SessionState) -> str:
    location_text = state.location_flow.original_user_message or "当前地址"
    if state.location_flow.prompt_mode == "current_location_consent":
        context_label = state.location_flow.site_context_label or "这个场地"
        return (
            f"已记录场地“{context_label}”，但你还没有提供详细位置。"
            "是否使用当前位置帮你推荐附近地址？也可以直接手动输入地址。"
        )
    return (
        f"已识别到位置信息“{location_text}”，现在进入地址确认。"
        "请在前端的位置确认卡片中选择或补充位置，确认完成后我再继续录入其他信息。"
    )


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


def _build_site_context_label(site_context_fields: dict[str, Any]) -> str | None:
    for field_name in ("siteTypeName", "siteSubType", "siteType"):
        value = site_context_fields.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if site_context_fields.get("hasStore") is True:
        return "门店"
    return None


def _merge_extraction_patches(
    rule_patch: dict[str, Any],
    llm_patch: dict[str, Any],
) -> dict[str, Any]:
    if not rule_patch:
        return llm_patch
    if not llm_patch:
        return rule_patch

    merged: dict[str, Any] = {}
    merged["main_info"] = {
        **rule_patch.get("main_info", {}),
        **llm_patch.get("main_info", {}),
    }
    if not merged["main_info"]:
        merged.pop("main_info")

    merged_contacts = llm_patch.get("contacts") or rule_patch.get("contacts")
    if merged_contacts:
        merged["contacts"] = merged_contacts

    merged_sites = llm_patch.get("sites") or rule_patch.get("sites")
    if merged_sites:
        merged["sites"] = merged_sites

    return merged


def _build_response_summary(state: SessionState) -> dict[str, Any]:
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
