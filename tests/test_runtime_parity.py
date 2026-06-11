from __future__ import annotations

from app.agent.graph.distributor_graph import DistributorGraphRuntime
from app.agent.runtime_config import RuntimeMode
from app.agent.runtime_facade import DistributorRuntimeFacade
from app.agent.service import AgentService
from app.agent.session_store import InMemorySessionStore
from app.agent.validators import MockValidationService


def test_distributor_runtime_matches_legacy_for_guidance_message() -> None:
    legacy_service = AgentService(store=InMemorySessionStore())
    facade = DistributorRuntimeFacade(
        legacy_service=legacy_service,
        langgraph_runtime=DistributorGraphRuntime(
            store=legacy_service.store,
            legacy_service=legacy_service,
        ),
        runtime_mode=RuntimeMode.LANGGRAPH,
    )

    legacy_response = legacy_service.process_chat("parity-guidance-1", "你能干什么")
    graph_response = facade.process_chat("parity-guidance-1", "你能干什么")

    assert graph_response.stage == legacy_response.stage
    assert graph_response.active_flow == legacy_response.active_flow
    assert graph_response.missing_required_fields == legacy_response.missing_required_fields
    assert graph_response.reply == legacy_response.reply


def test_distributor_runtime_matches_legacy_for_structured_patch_path() -> None:
    validation_service = MockValidationService(invalid_mobiles={"13800138000"})
    legacy_service = AgentService(
        store=InMemorySessionStore(),
        validation_service=validation_service,
    )
    facade = DistributorRuntimeFacade(
        legacy_service=legacy_service,
        langgraph_runtime=DistributorGraphRuntime(
            store=legacy_service.store,
            legacy_service=legacy_service,
            validation_service=validation_service,
        ),
        runtime_mode=RuntimeMode.LANGGRAPH,
    )
    patch = {
        "main_info": {
            "distributorName": "上海样例经销商",
            "customerMobile": "13800138000",
        }
    }

    legacy_response = legacy_service.process_structured_patch("parity-patch-1", patch)
    graph_response = facade.process_structured_patch("parity-patch-1", patch)

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
