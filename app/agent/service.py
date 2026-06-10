from __future__ import annotations

import os
import re
from typing import Any

from app.agent.address_resolver import (
    AddressResolver,
    build_address_resolver_from_env,
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
    AddressActionType,
    AddressConfirmationPayload,
    LocationCandidate,
    LocationFlowStatus,
    LocationState,
    AddressResolutionRequest,
    AddressResolutionResponse,
    ChatResponse,
    FieldOptionsResponse,
    Site,
    SessionStage,
    SessionState,
)
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
CONTINUE_ADDRESS_CONFIRMATION_PATTERN = re.compile(r"^\s*继续地址确认\s*$")

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
    "contacts[0].position": "联系人职位",
    "contacts[0].wechat": "联系人微信",
    "sites[0].fullAddress": "详细地址",
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
        llm_client: Any | None = None,
        intent_llm_client: Any | None = None,
        address_resolver: AddressResolver | None = None,
    ) -> None:
        self.store = store or build_session_store_from_env()
        self.validation_service = validation_service
        self.create_service = create_service or MockCreateService()
        self.llm_client = llm_client
        self.intent_llm_client = intent_llm_client
        self.address_resolver = address_resolver or build_address_resolver_from_env()

    def get_field_options(self) -> FieldOptionsResponse:
        return FieldOptionsResponse(fields=get_field_options_payload())

    def resolve_address(
        self,
        request: AddressResolutionRequest,
    ) -> AddressResolutionResponse:
        state = self.store.get(request.session_id) or create_initial_state(request.session_id)
        response = self._handle_address_resolution(state, request).model_copy(
            update={
                "stage": state.stage,
                "missing_required_fields": state.missing_required_fields,
                "state_summary": _build_response_summary(state),
            }
        )
        self.store.save(state)
        return response

    def process_chat(self, session_id: str, message: str) -> ChatResponse:
        state = self.store.get(session_id) or create_initial_state(session_id)
        current_turn = state.turn_count + 1

        if self._should_attempt_create_before_extraction(message, state):
            return self._handle_create(state)

        if self._should_resume_address_confirmation(message):
            response = self._handle_address_resolution(
                state,
                AddressResolutionRequest(
                    session_id=session_id,
                    action=AddressActionType.RESUME,
                ),
            )
            return self._finalize_response(
                state,
                reply=response.suggested_reply or response.message,
                address_confirmation=response.address_confirmation,
            )

        guidance_intent = self._classify_guidance_intent(message, state)
        if guidance_intent is not None:
            action = build_guidance_action(guidance_intent)
            return self._finalize_response(state, reply=render_reply(state, action))

        llm_patch = self._extract_llm_patch_if_enabled(message, state)
        if llm_patch:
            self._apply_patch(
                state,
                llm_patch,
                turn_number=current_turn,
                source_text=message,
            )

        rule_patch = extract_rule_based_patch(message)
        if rule_patch:
            self._apply_patch(
                state,
                rule_patch,
                turn_number=current_turn,
                source_text=message,
            )

        location_response = self._maybe_start_address_confirmation(
            state,
            session_id=session_id,
            llm_patch=llm_patch,
            rule_patch=rule_patch,
        )
        if location_response is not None:
            return self._finalize_response(
                state,
                reply=location_response.suggested_reply or location_response.message,
                address_confirmation=location_response.address_confirmation,
            )

        if self._should_create(message, state, _merge_patch_presence(llm_patch, rule_patch)):
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
        address_confirmation: AddressConfirmationPayload | None = None,
    ) -> ChatResponse:
        self.store.save(state)
        return ChatResponse(
            session_id=state.session_id,
            reply=reply,
            stage=state.stage,
            missing_required_fields=state.missing_required_fields,
            validation_results=state.validation_results,
            state_summary=_build_response_summary(state),
            address_confirmation=address_confirmation or _build_address_confirmation_payload(state),
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

    def _should_resume_address_confirmation(self, message: str) -> bool:
        return bool(CONTINUE_ADDRESS_CONFIRMATION_PATTERN.fullmatch(message.strip()))

    def _maybe_start_address_confirmation(
        self,
        state: SessionState,
        *,
        session_id: str,
        llm_patch: dict[str, Any],
        rule_patch: dict[str, Any],
    ) -> AddressResolutionResponse | None:
        full_address = _extract_first_site_full_address(llm_patch) or _extract_first_site_full_address(rule_patch)
        if not full_address:
            return None

        return self._handle_address_resolution(
            state,
            AddressResolutionRequest(
                session_id=session_id,
                action=AddressActionType.RESOLVE_TEXT,
                full_address=full_address,
            ),
        )

    def _handle_address_resolution(
        self,
        state: SessionState,
        request: AddressResolutionRequest,
    ) -> AddressResolutionResponse:
        if request.action == AddressActionType.SKIP:
            state.location_state.dismissed = True
            return AddressResolutionResponse(
                session_id=state.session_id,
                site_index=request.site_index,
                resolution_status="skipped",
                message="已跳过本次地址确认，你可以稍后说“继续地址确认”恢复。",
                location_state=state.location_state,
            )

        if request.action == AddressActionType.RESUME:
            if state.location_state.status == LocationFlowStatus.IDLE:
                state.location_state = LocationState(
                    status=LocationFlowStatus.AWAITING_CURRENT_LOCATION,
                    dismissed=False,
                    suggested_reply="当前还没有确认地址。你可以使用当前位置，或手工输入详细地址。",
                )
            else:
                state.location_state.dismissed = False
            payload = _build_address_confirmation_payload(state)
            return AddressResolutionResponse(
                session_id=state.session_id,
                site_index=request.site_index,
                resolution_status=state.location_state.status,
                message=state.location_state.suggested_reply or "已恢复地址确认流程。",
                suggested_reply=state.location_state.suggested_reply or "已恢复地址确认流程。",
                current_location=state.location_state.current_location,
                full_address=state.location_state.pending_full_address,
                candidates=state.location_state.candidates,
                normalized_site=state.location_state.normalized_site,
                location_state=state.location_state,
                address_confirmation=payload,
            )

        if request.action == AddressActionType.CONFIRM_CANDIDATE:
            candidate = _find_location_candidate(state.location_state.candidates, request.candidate_id)
            if candidate is None:
                raise ValueError(f"Unknown address candidate: {request.candidate_id}")
            site = _location_candidate_to_site(candidate)
            _upsert_site(state, request.site_index, site)
            state.location_state = LocationState(
                status=LocationFlowStatus.RESOLVED,
                dismissed=False,
                pending_full_address=site.fullAddress,
                current_location=state.location_state.current_location,
                candidates=state.location_state.candidates,
                normalized_site=site,
                suggested_reply="地址已确认并保存。",
            )
            return AddressResolutionResponse(
                session_id=state.session_id,
                site_index=request.site_index,
                resolution_status=LocationFlowStatus.RESOLVED,
                message="地址已确认并保存。",
                suggested_reply="地址已确认并保存。",
                current_location=state.location_state.current_location,
                full_address=site.fullAddress,
                candidates=state.location_state.candidates,
                normalized_site=site,
                location_state=state.location_state,
            )

        resolver_response = self.address_resolver.resolve(request)
        state.location_state = LocationState(
            status=LocationFlowStatus(resolver_response.resolution_status),
            dismissed=False,
            pending_full_address=resolver_response.full_address,
            current_location=resolver_response.current_location or request.current_location,
            candidates=resolver_response.candidates,
            normalized_site=resolver_response.normalized_site,
            suggested_reply=resolver_response.suggested_reply or resolver_response.message,
        )
        payload = _build_address_confirmation_payload(state)
        return resolver_response.model_copy(
            update={
                "current_location": resolver_response.current_location or request.current_location,
                "location_state": state.location_state,
                "address_confirmation": payload,
            }
        )

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


def _collect_changed_paths(patch: dict[str, Any]) -> list[str]:
    changed_paths: list[str] = []
    for field_name in patch.get("main_info", {}):
        changed_paths.append(f"main_info.{field_name}")
    for index, contact in enumerate(patch.get("contacts", [])):
        for field_name in contact:
            changed_paths.append(f"contacts[{index}].{field_name}")
    return changed_paths


def _build_structured_patch_reply(patch: dict[str, Any], follow_up_reply: str) -> str:
    updated_labels = []
    for field_name in patch.get("main_info", {}):
        updated_labels.append(
            STRUCTURED_FIELD_LABELS.get(f"main_info.{field_name}", f"main_info.{field_name}")
        )
    for field_name in (patch.get("contacts", [{}])[0] if patch.get("contacts") else {}):
        updated_labels.append(
            STRUCTURED_FIELD_LABELS.get(f"contacts[0].{field_name}", f"contacts[0].{field_name}")
        )

    if not updated_labels:
        return follow_up_reply

    return f"已更新：{'、'.join(updated_labels)}。\n\n{follow_up_reply}"


def _merge_patch_presence(*patches: dict[str, Any]) -> dict[str, Any]:
    return next((patch for patch in patches if patch), {})


def _extract_first_site_full_address(patch: dict[str, Any]) -> str | None:
    for site in patch.get("sites", []):
        full_address = site.get("fullAddress")
        if isinstance(full_address, str) and full_address.strip():
            return full_address.strip()
    return None


def _build_address_confirmation_payload(state: SessionState) -> AddressConfirmationPayload | None:
    if state.location_state.dismissed:
        return None
    if state.location_state.status not in {
        LocationFlowStatus.AWAITING_CURRENT_LOCATION,
        LocationFlowStatus.AWAITING_SEARCH_SELECTION,
        LocationFlowStatus.AWAITING_NEARBY_SELECTION,
        LocationFlowStatus.AWAITING_MANUAL_INPUT,
        LocationFlowStatus.AWAITING_USER_CONFIRMATION,
    }:
        return None
    return AddressConfirmationPayload(
        active=True,
        status=state.location_state.status,
        message=state.location_state.suggested_reply or "请继续完成地址确认。",
        pending_full_address=state.location_state.pending_full_address,
        candidates=state.location_state.candidates,
        normalized_site=state.location_state.normalized_site,
        can_skip=True,
        can_use_current_location=True,
    )


def _find_location_candidate(
    candidates: list[LocationCandidate],
    candidate_id: str | None,
) -> LocationCandidate | None:
    if not candidate_id:
        return None
    for candidate in candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    return None


def _location_candidate_to_site(candidate: LocationCandidate) -> Site:
    return Site(
        fullAddress=candidate.fullAddress,
        provinceName=candidate.provinceName,
        cityName=candidate.cityName,
        districtName=candidate.districtName,
        formattedAddress=candidate.formattedAddress or candidate.fullAddress,
        latitude=candidate.latitude,
        longitude=candidate.longitude,
        geoSource=candidate.geoSource,
    )


def _upsert_site(state: SessionState, site_index: int, site: Site) -> None:
    if site_index < len(state.sites):
        merged_site = state.sites[site_index].model_dump()
        for field_name, value in site.model_dump().items():
            if value is not None and value != "":
                merged_site[field_name] = value
        state.sites[site_index] = Site.model_validate(merged_site)
        return

    while len(state.sites) < site_index:
        state.sites.append(Site())
    state.sites.append(site)


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
