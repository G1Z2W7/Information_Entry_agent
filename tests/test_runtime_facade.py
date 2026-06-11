from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.agent.runtime_config import RuntimeMode
from app.agent.runtime_facade import DistributorRuntimeFacade
from app.company_agent.runtime_facade import CompanyAgentRuntimeFacade
from app.location_agent.runtime_facade import LocationAgentRuntimeFacade
from app.main import app


LANGGRAPH_MISCONFIGURED_DETAIL = (
    "AGENT_RUNTIME is set to langgraph, but no langgraph runtime is configured."
)


@dataclass
class Payload:
    value: str


class LegacyDistributorStub:
    def __init__(self) -> None:
        self.store = object()
        self.llm_client = None
        self.intent_llm_client = None
        self.address_resolver = None
        self.reset_calls = 0

    def process_chat(self, session_id: str, message: str) -> dict[str, str]:
        return {"runtime": "legacy", "session_id": session_id, "message": message}

    def process_structured_patch(
        self, session_id: str, patch: dict[str, str]
    ) -> dict[str, object]:
        return {"runtime": "legacy", "session_id": session_id, "patch": patch}

    def search_company_candidates(self, request: Payload) -> dict[str, str]:
        return {"runtime": "legacy", "value": request.value}

    def sync_company_flow(self, request: Payload) -> dict[str, str]:
        return {"runtime": "legacy", "value": request.value}

    def commit_company_flow(self, request: Payload) -> dict[str, str]:
        return {"runtime": "legacy", "value": request.value}

    def sync_location_flow(self, request: Payload) -> dict[str, str]:
        return {"runtime": "legacy", "value": request.value}

    def commit_location_flow(self, request: Payload) -> dict[str, str]:
        return {"runtime": "legacy", "value": request.value}

    def get_field_options(self) -> dict[str, str]:
        return {"runtime": "legacy"}

    def resolve_address(self, request: Payload) -> dict[str, str]:
        return {"runtime": "legacy", "value": request.value}

    def reset(self) -> None:
        self.reset_calls += 1


class LanggraphDistributorStub:
    def process_chat(self, session_id: str, message: str) -> dict[str, str]:
        return {"runtime": "langgraph", "session_id": session_id, "message": message}

    def process_structured_patch(
        self, session_id: str, patch: dict[str, str]
    ) -> dict[str, object]:
        return {"runtime": "langgraph", "session_id": session_id, "patch": patch}

    def search_company_candidates(self, request: Payload) -> dict[str, str]:
        return {"runtime": "langgraph", "value": request.value}

    def sync_company_flow(self, request: Payload) -> dict[str, str]:
        return {"runtime": "langgraph", "value": request.value}

    def commit_company_flow(self, request: Payload) -> dict[str, str]:
        return {"runtime": "langgraph", "value": request.value}

    def sync_location_flow(self, request: Payload) -> dict[str, str]:
        return {"runtime": "langgraph", "value": request.value}

    def commit_location_flow(self, request: Payload) -> dict[str, str]:
        return {"runtime": "langgraph", "value": request.value}


class LegacyCompanyStub:
    def resolve(self, request: Payload) -> dict[str, str]:
        return {"runtime": "legacy", "value": request.value}


class LanggraphCompanyStub:
    def resolve(self, request: Payload) -> dict[str, str]:
        return {"runtime": "langgraph", "value": request.value}


class LegacyLocationStub:
    def handle(self, request: Payload) -> dict[str, str]:
        return {"runtime": "legacy", "value": request.value}


class LanggraphLocationStub:
    def handle(self, request: Payload) -> dict[str, str]:
        return {"runtime": "langgraph", "value": request.value}


class RuntimeErroringLanggraphDistributor:
    def commit_company_flow(self, request: Payload) -> None:
        raise RuntimeError("company commit failed")


@pytest.fixture
def misconfigured_distributor_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(chat_api.agent_service, "runtime_mode", RuntimeMode.LANGGRAPH)
    monkeypatch.setattr(chat_api.agent_service, "langgraph_runtime", None)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def langgraph_commit_error_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(chat_api.agent_service, "runtime_mode", RuntimeMode.LANGGRAPH)
    monkeypatch.setattr(
        chat_api.agent_service,
        "langgraph_runtime",
        RuntimeErroringLanggraphDistributor(),
    )
    return TestClient(app, raise_server_exceptions=False)


def test_distributor_runtime_facade_uses_legacy_by_default() -> None:
    facade = DistributorRuntimeFacade(
        legacy_service=LegacyDistributorStub(),
        langgraph_runtime=LanggraphDistributorStub(),
        runtime_mode=RuntimeMode.LEGACY,
    )

    result = facade.process_chat("s-1", "hello")

    assert result["runtime"] == "legacy"


def test_distributor_runtime_facade_can_route_to_langgraph() -> None:
    facade = DistributorRuntimeFacade(
        legacy_service=LegacyDistributorStub(),
        langgraph_runtime=LanggraphDistributorStub(),
        runtime_mode=RuntimeMode.LANGGRAPH,
    )

    result = facade.process_chat("s-2", "hello")

    assert result["runtime"] == "langgraph"


def test_distributor_runtime_facade_preserves_legacy_attribute_access() -> None:
    legacy_service = LegacyDistributorStub()
    facade = DistributorRuntimeFacade(
        legacy_service=legacy_service,
        langgraph_runtime=LanggraphDistributorStub(),
        runtime_mode=RuntimeMode.LANGGRAPH,
    )

    marker = object()
    facade.llm_client = marker
    facade.intent_llm_client = marker
    facade.address_resolver = marker
    facade.reset()

    assert facade.store is legacy_service.store
    assert facade.llm_client is marker
    assert facade.intent_llm_client is marker
    assert facade.address_resolver is marker
    assert legacy_service.reset_calls == 1


def test_distributor_runtime_facade_fails_loudly_without_langgraph_runtime() -> None:
    legacy_service = LegacyDistributorStub()
    facade = DistributorRuntimeFacade(
        legacy_service=legacy_service,
        runtime_mode=RuntimeMode.LANGGRAPH,
    )

    with pytest.raises(
        RuntimeError,
        match="AGENT_RUNTIME is set to langgraph, but no langgraph runtime is configured.",
    ):
        facade.process_chat("s-3", "hello")

    facade.reset()
    assert legacy_service.reset_calls == 1


def test_company_runtime_facade_can_route_to_langgraph() -> None:
    facade = CompanyAgentRuntimeFacade(
        legacy_service=LegacyCompanyStub(),
        langgraph_runtime=LanggraphCompanyStub(),
        runtime_mode=RuntimeMode.LANGGRAPH,
    )

    result = facade.resolve(Payload(value="company"))

    assert result["runtime"] == "langgraph"


def test_company_runtime_facade_fails_loudly_without_langgraph_runtime() -> None:
    facade = CompanyAgentRuntimeFacade(
        legacy_service=LegacyCompanyStub(),
        runtime_mode=RuntimeMode.LANGGRAPH,
    )

    with pytest.raises(
        RuntimeError,
        match="COMPANY_RUNTIME is set to langgraph, but no langgraph runtime is configured.",
    ):
        facade.resolve(Payload(value="company"))


def test_location_runtime_facade_defaults_to_legacy() -> None:
    facade = LocationAgentRuntimeFacade(
        legacy_service=LegacyLocationStub(),
        langgraph_runtime=LanggraphLocationStub(),
        runtime_mode=RuntimeMode.LEGACY,
    )

    result = facade.handle(Payload(value="location"))

    assert result["runtime"] == "legacy"


def test_location_runtime_facade_fails_loudly_without_langgraph_runtime() -> None:
    facade = LocationAgentRuntimeFacade(
        legacy_service=LegacyLocationStub(),
        runtime_mode=RuntimeMode.LANGGRAPH,
    )

    with pytest.raises(
        RuntimeError,
        match="LOCATION_RUNTIME is set to langgraph, but no langgraph runtime is configured.",
    ):
        facade.handle(Payload(value="location"))


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "post",
            "/api/agent/distributors/chat",
            {"session_id": "session-runtime-chat", "message": "hello"},
        ),
        (
            "patch",
            "/api/agent/distributors/fields",
            {
                "session_id": "session-runtime-fields",
                "patch": {"main_info": {"status": "normal"}},
            },
        ),
        (
            "post",
            "/api/agent/distributors/company/search",
            {"session_id": "session-runtime-company-search", "keyword": "Acme"},
        ),
        (
            "post",
            "/api/agent/distributors/company/sync",
            {
                "session_id": "session-runtime-company-sync",
                "company_agent_response": {
                    "status": "need_manual_input",
                    "suggested_reply": "",
                    "state": {"phase": "idle"},
                },
            },
        ),
        (
            "post",
            "/api/agent/distributors/company/commit",
            {"session_id": "session-runtime-company-commit", "company_name": "Acme"},
        ),
        (
            "post",
            "/api/agent/distributors/location/sync",
            {
                "session_id": "session-runtime-location-sync",
                "location_agent_response": {
                    "status": "need_manual_input",
                    "message": "need input",
                    "suggested_reply": "",
                    "state": {"phase": "idle"},
                },
            },
        ),
        (
            "post",
            "/api/agent/distributors/location/commit",
            {
                "session_id": "session-runtime-location-commit",
                "location_agent_response": {
                    "status": "need_manual_input",
                    "message": "need input",
                    "suggested_reply": "",
                    "state": {"phase": "idle"},
                },
            },
        ),
    ],
)
def test_distributor_router_returns_503_for_runtime_misconfiguration(
    misconfigured_distributor_client: TestClient,
    method: str,
    path: str,
    payload: dict[str, object],
) -> None:
    response = getattr(misconfigured_distributor_client, method)(path, json=payload)

    assert response.status_code == 503
    assert response.json() == {"detail": LANGGRAPH_MISCONFIGURED_DETAIL}


def test_distributor_commit_endpoint_keeps_non_config_runtime_errors_as_422(
    langgraph_commit_error_client: TestClient,
) -> None:
    response = langgraph_commit_error_client.post(
        "/api/agent/distributors/company/commit",
        json={"session_id": "session-runtime-company-commit-error", "company_name": "Acme"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "company commit failed"}
