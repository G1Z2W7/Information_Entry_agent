from __future__ import annotations

from typing import Protocol

from app.location_agent.models import (
    CurrentCoordinates,
    LocationAgentRequest,
    LocationAnalysis,
    LocationCandidate,
)


class CoordinatesProvider(Protocol):
    def get_current_coordinates(self) -> CurrentCoordinates: ...


class LocationAnalyzer(Protocol):
    def analyze(self, request: LocationAgentRequest) -> LocationAnalysis: ...


class MapSearcher(Protocol):
    def nearby(self, latitude: float, longitude: float) -> list[LocationCandidate]: ...

    def search(self, query: str, city_hint: str | None = None) -> list[LocationCandidate]: ...
