from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.company_agent.models import CompanyResolveRequest, CompanyResolveResponse
from app.company_agent.service import CompanyAgentService
from app.integrations.qixin import QixinConfigError, QixinUpstreamError

router = APIRouter(prefix="/api/company", tags=["company-agent"])
service = CompanyAgentService()


@router.post("/resolve", response_model=CompanyResolveResponse)
def resolve_company(request: CompanyResolveRequest) -> CompanyResolveResponse:
    try:
        return service.resolve(request)
    except QixinConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except QixinUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
