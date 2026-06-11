from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agent.graph.distributor_nodes import (
    apply_structured_patch,
    build_guidance_action_node,
    classify_turn_intent,
    decide_next_action_node,
    load_session_state,
    render_company_active,
    render_location_active,
    render_response,
    resume_company_flow,
    resume_location_flow,
    return_to_main_from_company,
    return_to_main_from_location,
)
from app.agent.graph.state import DistributorGraphState
from app.agent.session_store import InMemorySessionStore, SessionStore
from app.agent.validators import ValidationService


def build_distributor_graph():
    graph = StateGraph(DistributorGraphState)
    graph.add_node("load_session_state", load_session_state)
    graph.add_node("classify_turn_intent", classify_turn_intent)
    graph.add_node("apply_structured_patch", apply_structured_patch)
    graph.add_node("build_guidance_action", build_guidance_action_node)
    graph.add_node("decide_next_action", decide_next_action_node)
    graph.add_node("resume_company_flow", resume_company_flow)
    graph.add_node("resume_location_flow", resume_location_flow)
    graph.add_node("return_to_main_from_company", return_to_main_from_company)
    graph.add_node("return_to_main_from_location", return_to_main_from_location)
    graph.add_node("render_company_active", render_company_active)
    graph.add_node("render_location_active", render_location_active)
    graph.add_node("render_response", render_response)

    graph.add_edge(START, "load_session_state")
    graph.add_edge("load_session_state", "classify_turn_intent")
    graph.add_conditional_edges(
        "classify_turn_intent",
        route_after_classification,
        {
            "structured_patch": "apply_structured_patch",
            "guidance": "build_guidance_action",
            "main": "decide_next_action",
            "resume_company": "resume_company_flow",
            "resume_location": "resume_location_flow",
            "return_main_from_company": "return_to_main_from_company",
            "return_main_from_location": "return_to_main_from_location",
            "company_active": "render_company_active",
            "location_active": "render_location_active",
        },
    )
    graph.add_edge("apply_structured_patch", "decide_next_action")
    graph.add_edge("build_guidance_action", "render_response")
    graph.add_edge("decide_next_action", "render_response")
    graph.add_edge("resume_company_flow", "render_response")
    graph.add_edge("resume_location_flow", "render_response")
    graph.add_edge("return_to_main_from_company", "render_response")
    graph.add_edge("return_to_main_from_location", "render_response")
    graph.add_edge("render_company_active", "render_response")
    graph.add_edge("render_location_active", "render_response")
    graph.add_edge("render_response", END)
    return graph.compile()


def route_after_classification(state: DistributorGraphState) -> str:
    return state["route"]


class DistributorGraphRuntime:
    def __init__(
        self,
        *,
        store: SessionStore | None = None,
        legacy_service: Any | None = None,
        validation_service: ValidationService | None = None,
    ) -> None:
        self.legacy_service = legacy_service
        self.store = _resolve_runtime_store(store=store, legacy_service=legacy_service)
        self.validation_service = validation_service or getattr(
            legacy_service,
            "validation_service",
            None,
        )
        self.graph = build_distributor_graph()

    def process_chat(self, session_id: str, message: str):
        return self._invoke(
            {
                "session_id": session_id,
                "message": message,
                "operation": "chat",
            }
        )

    def process_structured_patch(self, session_id: str, patch: dict[str, Any]):
        return self._invoke(
            {
                "session_id": session_id,
                "patch": patch,
                "operation": "structured_patch",
            }
        )

    def search_company_candidates(self, request):
        return self._require_legacy_service().search_company_candidates(request)

    def sync_company_flow(self, request):
        return self._require_legacy_service().sync_company_flow(request)

    def commit_company_flow(self, request):
        return self._require_legacy_service().commit_company_flow(request)

    def sync_location_flow(self, request):
        return self._require_legacy_service().sync_location_flow(request)

    def commit_location_flow(self, request):
        return self._require_legacy_service().commit_location_flow(request)

    def reset(self) -> None:
        self.store.clear()

    def _invoke(self, payload: dict[str, Any]):
        result = self.graph.invoke(
            {
                **payload,
                "store": self.store,
                "validation_service": self.validation_service,
            }
        )
        return result["response"]

    def _require_legacy_service(self):
        if self.legacy_service is None:
            raise RuntimeError("DistributorGraphRuntime requires a legacy_service for delegated methods.")
        return self.legacy_service


def _resolve_runtime_store(
    *,
    store: SessionStore | None,
    legacy_service: Any | None,
) -> SessionStore:
    legacy_store = getattr(legacy_service, "store", None)

    if store is None and legacy_store is not None:
        return legacy_store

    if store is not None and legacy_store is not None and store is not legacy_store:
        raise RuntimeError(
            "DistributorGraphRuntime received both store and legacy_service.store, but they differ."
        )

    if store is not None:
        return store

    return InMemorySessionStore()
