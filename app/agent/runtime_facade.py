from __future__ import annotations

from typing import Any

from app.agent.runtime_config import RuntimeMode, RuntimeSelectionError, get_runtime_mode
from app.agent.service import AgentService


class DistributorRuntimeFacade:
    def __init__(
        self,
        *,
        legacy_service: AgentService,
        langgraph_runtime: Any | None = None,
        runtime_mode: RuntimeMode | None = None,
    ) -> None:
        object.__setattr__(self, "legacy_service", legacy_service)
        object.__setattr__(self, "langgraph_runtime", langgraph_runtime)
        object.__setattr__(self, "runtime_mode", runtime_mode or get_runtime_mode("AGENT_RUNTIME"))

    def __getattr__(self, name: str) -> Any:
        return getattr(self.legacy_service, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"legacy_service", "langgraph_runtime", "runtime_mode"}:
            object.__setattr__(self, name, value)
            return
        setattr(self.legacy_service, name, value)
        if name in {"store", "validation_service"} and self.langgraph_runtime is not None:
            setattr(self.langgraph_runtime, name, value)

    def _active_runtime(self) -> Any:
        if self.runtime_mode is RuntimeMode.LANGGRAPH:
            if self.langgraph_runtime is None:
                raise RuntimeSelectionError(
                    "AGENT_RUNTIME is set to langgraph, but no langgraph runtime is configured."
                )
            return self.langgraph_runtime
        return self.legacy_service

    def process_chat(self, session_id: str, message: str):
        return self._active_runtime().process_chat(session_id, message)

    def process_structured_patch(self, session_id: str, patch: dict[str, Any]):
        return self._active_runtime().process_structured_patch(session_id, patch)

    def search_company_candidates(self, request):
        return self._active_runtime().search_company_candidates(request)

    def sync_company_flow(self, request):
        return self._active_runtime().sync_company_flow(request)

    def commit_company_flow(self, request):
        return self._active_runtime().commit_company_flow(request)

    def sync_location_flow(self, request):
        return self._active_runtime().sync_location_flow(request)

    def commit_location_flow(self, request):
        return self._active_runtime().commit_location_flow(request)

    def get_field_options(self):
        return self.legacy_service.get_field_options()

    def resolve_address(self, request):
        return self.legacy_service.resolve_address(request)

    def reset(self) -> None:
        self.legacy_service.reset()
