from __future__ import annotations

from typing import Any

from app.agent.runtime_config import RuntimeMode, RuntimeSelectionError, get_runtime_mode
from app.location_agent.service import LocationAgentService


class LocationAgentRuntimeFacade:
    def __init__(
        self,
        *,
        legacy_service: LocationAgentService,
        langgraph_runtime: Any | None = None,
        runtime_mode: RuntimeMode | None = None,
    ) -> None:
        self.legacy_service = legacy_service
        self.langgraph_runtime = langgraph_runtime
        self.runtime_mode = runtime_mode or get_runtime_mode("LOCATION_RUNTIME")

    def _active_runtime(self) -> Any:
        if self.runtime_mode is RuntimeMode.LANGGRAPH:
            if self.langgraph_runtime is None:
                raise RuntimeSelectionError(
                    "LOCATION_RUNTIME is set to langgraph, but no langgraph runtime is configured."
                )
            return self.langgraph_runtime
        return self.legacy_service

    def handle(self, request):
        return self._active_runtime().handle(request)
