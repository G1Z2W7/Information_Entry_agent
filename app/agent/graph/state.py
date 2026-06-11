from __future__ import annotations

from typing import Any, Literal, TypedDict

from app.agent.models import ChatResponse, DialogAction, SessionState
from app.agent.session_store import SessionStore
from app.agent.validators import ValidationService


class DistributorGraphState(TypedDict, total=False):
    session_id: str
    message: str
    patch: dict[str, Any]
    operation: Literal["chat", "structured_patch"]
    store: SessionStore
    validation_service: ValidationService | None
    session_state: SessionState
    action: DialogAction
    response: ChatResponse
    reply: str
    route: str
    guidance_intent: str
    turn_number: int
