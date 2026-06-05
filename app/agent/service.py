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
    extract_llm_incremental_patch,
)
from app.agent.models import (
    AddressResolutionRequest,
    AddressResolutionResponse,
    ChatResponse,
    FieldOptionsResponse,
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
        llm_client: Any | None = None,
        intent_llm_client: Any | None = None,
        address_resolver: AddressResolver | None = None,
    ) -> None:
        self.store = store or build_session_store_from_env()
        self.validation_service = validation_service
        self.create_service = create_service or MockCreateService()
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

    def process_chat(self, session_id: str, message: str) -> ChatResponse:
        state = self.store.get(session_id) or create_initial_state(session_id)
        current_turn = state.turn_count + 1

        if self._should_attempt_create_before_extraction(message, state):
            return self._handle_create(state)

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

        if self._should_create(message, state, llm_patch):
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
