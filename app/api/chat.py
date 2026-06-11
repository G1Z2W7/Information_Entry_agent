from fastapi import APIRouter, Depends, HTTPException, WebSocket

from app.agent.asr_realtime import bridge_qwen_realtime_asr
from app.agent.graph.distributor_graph import DistributorGraphRuntime
from app.agent.models import (
    AddressResolutionRequest,
    AddressResolutionResponse,
    ChatRequest,
    ChatResponse,
    CompanyCommitRequest,
    CompanyFlowSyncRequest,
    CompanySearchRequest,
    FieldOptionsResponse,
    LocationCommitRequest,
    LocationFlowSyncRequest,
    StructuredPatchRequest,
)
from app.agent.runtime_config import RuntimeSelectionError
from app.agent.runtime_facade import DistributorRuntimeFacade
from app.agent.service import AgentService


router = APIRouter(prefix="/api/agent/distributors", tags=["distributor-agent"])
legacy_service = AgentService()
agent_service = DistributorRuntimeFacade(
    legacy_service=legacy_service,
    langgraph_runtime=DistributorGraphRuntime(
        store=legacy_service.store,
        legacy_service=legacy_service,
    ),
)


def get_agent_service() -> DistributorRuntimeFacade:
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
    service: DistributorRuntimeFacade = Depends(get_agent_service),
) -> FieldOptionsResponse:
    return service.get_field_options()


@router.post("/address/resolve", response_model=AddressResolutionResponse)
def resolve_address(
    request: AddressResolutionRequest,
    service: DistributorRuntimeFacade = Depends(get_agent_service),
) -> AddressResolutionResponse:
    return service.resolve_address(request)


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    service: DistributorRuntimeFacade = Depends(get_agent_service),
) -> ChatResponse:
    try:
        return service.process_chat(request.session_id, request.message)
    except RuntimeSelectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.patch("/fields", response_model=ChatResponse)
def patch_fields(
    request: StructuredPatchRequest,
    service: DistributorRuntimeFacade = Depends(get_agent_service),
) -> ChatResponse:
    try:
        return service.process_structured_patch(request.session_id, request.patch)
    except RuntimeSelectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/company/search", response_model=ChatResponse)
def search_company_candidates(
    request: CompanySearchRequest,
    service: DistributorRuntimeFacade = Depends(get_agent_service),
) -> ChatResponse:
    try:
        return service.search_company_candidates(request)
    except RuntimeSelectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/company/sync", response_model=ChatResponse)
def sync_company_flow(
    request: CompanyFlowSyncRequest,
    service: DistributorRuntimeFacade = Depends(get_agent_service),
) -> ChatResponse:
    try:
        return service.sync_company_flow(request)
    except RuntimeSelectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/company/commit", response_model=ChatResponse)
def commit_company_flow(
    request: CompanyCommitRequest,
    service: DistributorRuntimeFacade = Depends(get_agent_service),
) -> ChatResponse:
    try:
        return service.commit_company_flow(request)
    except RuntimeSelectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/location/sync", response_model=ChatResponse)
def sync_location_flow(
    request: LocationFlowSyncRequest,
    service: DistributorRuntimeFacade = Depends(get_agent_service),
) -> ChatResponse:
    try:
        return service.sync_location_flow(request)
    except RuntimeSelectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/location/commit", response_model=ChatResponse)
def commit_location_flow(
    request: LocationCommitRequest,
    service: DistributorRuntimeFacade = Depends(get_agent_service),
) -> ChatResponse:
    try:
        return service.commit_location_flow(request)
    except RuntimeSelectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
