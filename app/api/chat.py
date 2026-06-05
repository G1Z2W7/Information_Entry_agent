from fastapi import APIRouter, Depends, HTTPException, WebSocket

from app.agent.asr_realtime import bridge_qwen_realtime_asr
from app.agent.models import (
    AddressResolutionRequest,
    AddressResolutionResponse,
    ChatRequest,
    ChatResponse,
    FieldOptionsResponse,
    StructuredPatchRequest,
)
from app.agent.service import AgentService


router = APIRouter(prefix="/api/agent/distributors", tags=["distributor-agent"])
agent_service = AgentService()


def get_agent_service() -> AgentService:
    return agent_service


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.websocket("/asr/realtime")
async def realtime_asr(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        await bridge_qwen_realtime_asr(websocket)
    except RuntimeError as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close()
    except Exception:
        await websocket.send_json({"type": "error", "message": "实时语音识别连接失败。"})
        await websocket.close()


@router.get("/field-options", response_model=FieldOptionsResponse)
def field_options(
    service: AgentService = Depends(get_agent_service),
) -> FieldOptionsResponse:
    return service.get_field_options()


@router.post("/address/resolve", response_model=AddressResolutionResponse)
def resolve_address(
    request: AddressResolutionRequest,
    service: AgentService = Depends(get_agent_service),
) -> AddressResolutionResponse:
    return service.resolve_address(request)


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    service: AgentService = Depends(get_agent_service),
) -> ChatResponse:
    try:
        return service.process_chat(request.session_id, request.message)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.patch("/fields", response_model=ChatResponse)
def patch_fields(
    request: StructuredPatchRequest,
    service: AgentService = Depends(get_agent_service),
) -> ChatResponse:
    return service.process_structured_patch(request.session_id, request.patch)
