from __future__ import annotations

from dataclasses import dataclass

from app.agent.graph.distributor_graph import (
    DistributorGraphRuntime,
    build_distributor_graph,
)
from app.agent.models import ActiveFlow, CompanyFlowStatus, LocationFlowStatus
from app.agent.service import AgentService
from app.agent.session_store import InMemorySessionStore
from app.agent.state import create_initial_state
from app.agent.validators import MockValidationService
from app.company_agent.models import CompanyResolveResponse, CompanyState
from app.location_agent.models import LocationAgentResponse, LocationState


@dataclass
class Payload:
    value: str


class LegacyStub:
    def __init__(self) -> None:
        self.validation_service = MockValidationService(invalid_mobiles={"13800138000"})
        self.store = InMemorySessionStore()

    def search_company_candidates(self, request: Payload):
        return {"method": "search_company_candidates", "value": request.value}

    def sync_company_flow(self, request: Payload):
        return {"method": "sync_company_flow", "value": request.value}

    def commit_company_flow(self, request: Payload):
        return {"method": "commit_company_flow", "value": request.value}

    def sync_location_flow(self, request: Payload):
        return {"method": "sync_location_flow", "value": request.value}

    def commit_location_flow(self, request: Payload):
        return {"method": "commit_location_flow", "value": request.value}


def _build_company_response(suggested_reply: str = "请选择经销商") -> CompanyResolveResponse:
    return CompanyResolveResponse(
        status="need_select",
        suggested_reply=suggested_reply,
        state=CompanyState(),
    )


def _build_location_response(suggested_reply: str = "请确认地址") -> LocationAgentResponse:
    return LocationAgentResponse(
        status="need_select",
        message=suggested_reply,
        suggested_reply=suggested_reply,
        state=LocationState(),
    )


def _copy_state_to_store(store: InMemorySessionStore, session_id: str, state) -> None:
    seeded = state.model_copy(deep=True)
    seeded.session_id = session_id
    store.save(seeded)


def test_build_distributor_graph_compiles() -> None:
    graph = build_distributor_graph()

    assert graph is not None


def test_distributor_graph_runtime_process_chat_returns_chat_response() -> None:
    runtime = DistributorGraphRuntime(store=InMemorySessionStore())

    response = runtime.process_chat("graph-session-1", "你好")

    assert response.session_id == "graph-session-1"
    assert response.reply


def test_distributor_graph_runtime_process_structured_patch_updates_state() -> None:
    runtime = DistributorGraphRuntime(store=InMemorySessionStore())

    response = runtime.process_structured_patch(
        "graph-session-2",
        {
            "main_info": {
                "distributorName": "上海样例经销商",
                "customerMobile": "13800138000",
            }
        },
    )

    assert response.session_id == "graph-session-2"
    assert response.state_summary["main_info"]["distributorName"] == "上海样例经销商"
    assert "main_info.customerEmail" in response.missing_required_fields


def test_distributor_graph_runtime_uses_injected_validation_service_for_structured_patch() -> None:
    legacy_service = LegacyStub()

    runtime = DistributorGraphRuntime(
        store=legacy_service.store,
        legacy_service=legacy_service,
    )

    response = runtime.process_structured_patch(
        "graph-session-validation",
        {
            "main_info": {
                "customerMobile": "13800138000",
            }
        },
    )

    assert response.validation_results["main_info.customerMobile"].code == "MOBILE_REJECTED"


def test_distributor_graph_runtime_delegates_company_and_location_methods_to_legacy_service() -> None:
    legacy_service = LegacyStub()

    runtime = DistributorGraphRuntime(
        store=legacy_service.store,
        legacy_service=legacy_service,
    )

    assert runtime.search_company_candidates(Payload("company")) == {
        "method": "search_company_candidates",
        "value": "company",
    }
    assert runtime.sync_company_flow(Payload("sync-company")) == {
        "method": "sync_company_flow",
        "value": "sync-company",
    }
    assert runtime.commit_company_flow(Payload("commit-company")) == {
        "method": "commit_company_flow",
        "value": "commit-company",
    }
    assert runtime.sync_location_flow(Payload("sync-location")) == {
        "method": "sync_location_flow",
        "value": "sync-location",
    }
    assert runtime.commit_location_flow(Payload("commit-location")) == {
        "method": "commit_location_flow",
        "value": "commit-location",
    }


def test_distributor_graph_runtime_uses_legacy_store_when_store_omitted() -> None:
    legacy_service = LegacyStub()

    runtime = DistributorGraphRuntime(legacy_service=legacy_service)

    assert runtime.store is legacy_service.store


def test_distributor_graph_runtime_rejects_mismatched_store_and_legacy_store() -> None:
    legacy_service = LegacyStub()

    try:
        DistributorGraphRuntime(
            store=InMemorySessionStore(),
            legacy_service=legacy_service,
        )
    except RuntimeError as exc:
        assert "legacy_service.store" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_distributor_graph_runtime_reset_clears_shared_legacy_store() -> None:
    legacy_service = LegacyStub()
    state = create_initial_state("graph-reset-shared-store")
    legacy_service.store.save(state)
    runtime = DistributorGraphRuntime(legacy_service=legacy_service)

    runtime.reset()

    assert runtime.store.get("graph-reset-shared-store") is None
    assert legacy_service.store.get("graph-reset-shared-store") is None


def test_distributor_graph_runtime_matches_agent_service_for_greeting_path() -> None:
    graph_store = InMemorySessionStore()
    legacy_store = InMemorySessionStore()
    graph_runtime = DistributorGraphRuntime(store=graph_store)
    legacy_service = AgentService(store=legacy_store)

    graph_response = graph_runtime.process_chat("graph-parity-greeting", "你好")
    legacy_response = legacy_service.process_chat("graph-parity-greeting", "你好")

    assert graph_response.model_dump() == legacy_response.model_dump()


def test_distributor_graph_runtime_matches_agent_service_for_structured_patch_path() -> None:
    validation_service = MockValidationService(invalid_mobiles={"13800138000"})
    graph_store = InMemorySessionStore()
    legacy_store = InMemorySessionStore()
    legacy_service = LegacyStub()
    legacy_service.store = graph_store
    graph_runtime = DistributorGraphRuntime(
        store=graph_store,
        legacy_service=legacy_service,
        validation_service=validation_service,
    )
    legacy_service = AgentService(
        store=legacy_store,
        validation_service=validation_service,
    )
    patch = {
        "main_info": {
            "distributorName": "上海样例经销商",
            "customerMobile": "13800138000",
        }
    }

    graph_response = graph_runtime.process_structured_patch("graph-parity-patch", patch)
    legacy_response = legacy_service.process_structured_patch("graph-parity-patch", patch)

    assert graph_response.reply == legacy_response.reply
    assert graph_response.stage == legacy_response.stage
    assert graph_response.active_flow == legacy_response.active_flow
    assert graph_response.missing_required_fields == legacy_response.missing_required_fields
    assert graph_response.state_summary == legacy_response.state_summary
    assert {
        path: result.code for path, result in graph_response.validation_results.items()
    } == {
        path: result.code for path, result in legacy_response.validation_results.items()
    }


def test_distributor_graph_runtime_resumes_company_flow_from_saved_state() -> None:
    store = InMemorySessionStore()
    state = create_initial_state("graph-session-company-resume")
    state.active_flow = ActiveFlow.MAIN
    state.company_flow.status = CompanyFlowStatus.PAUSED
    store.save(state)
    runtime = DistributorGraphRuntime(store=store)

    response = runtime.process_chat("graph-session-company-resume", "继续经销商确认")

    assert response.active_flow is ActiveFlow.COMPANY
    assert response.company_flow.status is CompanyFlowStatus.ACTIVE
    assert "继续上次经销商名称确认" in response.reply


def test_distributor_graph_runtime_returns_main_from_location_flow() -> None:
    store = InMemorySessionStore()
    state = create_initial_state("graph-session-location-return")
    state.active_flow = ActiveFlow.LOCATION
    state.location_flow.status = LocationFlowStatus.ACTIVE
    store.save(state)
    runtime = DistributorGraphRuntime(store=store)

    response = runtime.process_chat("graph-session-location-return", "返回信息录入")

    assert response.active_flow is ActiveFlow.MAIN
    assert response.location_flow.status is LocationFlowStatus.PAUSED
    assert "地址确认已暂停" in response.reply


def test_distributor_graph_runtime_resumes_location_flow_with_agent_service_parity() -> None:
    session_id = "graph-session-location-resume"
    graph_store = InMemorySessionStore()
    legacy_store = InMemorySessionStore()
    state = create_initial_state(session_id)
    state.active_flow = ActiveFlow.MAIN
    state.location_flow.status = LocationFlowStatus.PAUSED
    _copy_state_to_store(graph_store, session_id, state)
    _copy_state_to_store(legacy_store, session_id, state)
    graph_runtime = DistributorGraphRuntime(store=graph_store)
    legacy_service = AgentService(store=legacy_store)

    graph_response = graph_runtime.process_chat(session_id, "继续地址确认")
    legacy_response = legacy_service.process_chat(session_id, "继续地址确认")

    assert graph_response.model_dump() == legacy_response.model_dump()
    assert graph_response.active_flow is ActiveFlow.LOCATION
    assert graph_response.location_flow.status is LocationFlowStatus.ACTIVE


def test_distributor_graph_runtime_returns_main_from_company_with_agent_service_parity() -> None:
    session_id = "graph-session-company-return"
    graph_store = InMemorySessionStore()
    legacy_store = InMemorySessionStore()
    state = create_initial_state(session_id)
    state.active_flow = ActiveFlow.COMPANY
    state.company_flow.status = CompanyFlowStatus.ACTIVE
    _copy_state_to_store(graph_store, session_id, state)
    _copy_state_to_store(legacy_store, session_id, state)
    graph_runtime = DistributorGraphRuntime(store=graph_store)
    legacy_service = AgentService(store=legacy_store)

    graph_response = graph_runtime.process_chat(session_id, "返回信息录入")
    legacy_response = legacy_service.process_chat(session_id, "返回信息录入")

    assert graph_response.model_dump() == legacy_response.model_dump()
    assert graph_response.active_flow is ActiveFlow.MAIN
    assert graph_response.company_flow.status is CompanyFlowStatus.PAUSED


def test_distributor_graph_runtime_handles_company_active_with_agent_service_parity() -> None:
    session_id = "graph-session-company-active"
    graph_store = InMemorySessionStore()
    legacy_store = InMemorySessionStore()
    state = create_initial_state(session_id)
    state.active_flow = ActiveFlow.COMPANY
    state.company_flow.status = CompanyFlowStatus.ACTIVE
    state.company_flow.last_response = _build_company_response("继续从候选中选择")
    _copy_state_to_store(graph_store, session_id, state)
    _copy_state_to_store(legacy_store, session_id, state)
    graph_runtime = DistributorGraphRuntime(store=graph_store)
    legacy_service = AgentService(store=legacy_store)
    legacy_service._extract_incremental_patch = lambda message, state: {}

    graph_response = graph_runtime.process_chat(session_id, "我先看看")
    legacy_response = legacy_service.process_chat(session_id, "我先看看")

    assert graph_response.model_dump() == legacy_response.model_dump()
    assert "当前正在确认经销商名称" in graph_response.reply


def test_distributor_graph_runtime_handles_location_active_with_agent_service_parity() -> None:
    session_id = "graph-session-location-active"
    graph_store = InMemorySessionStore()
    legacy_store = InMemorySessionStore()
    state = create_initial_state(session_id)
    state.active_flow = ActiveFlow.LOCATION
    state.location_flow.status = LocationFlowStatus.ACTIVE
    state.location_flow.last_response = _build_location_response("继续从位置卡片中确认")
    _copy_state_to_store(graph_store, session_id, state)
    _copy_state_to_store(legacy_store, session_id, state)
    graph_runtime = DistributorGraphRuntime(store=graph_store)
    legacy_service = AgentService(store=legacy_store)
    legacy_service._extract_incremental_patch = lambda message, state: {}

    graph_response = graph_runtime.process_chat(session_id, "继续")
    legacy_response = legacy_service.process_chat(session_id, "继续")

    assert graph_response.model_dump() == legacy_response.model_dump()
    assert "当前正在确认地址" in graph_response.reply
