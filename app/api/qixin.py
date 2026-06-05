from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.integrations.qixin import QixinClient, QixinConfigError, QixinUpstreamError


router = APIRouter(prefix="/api/qixin", tags=["qixin"])


class QixinCompanySearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword: str = Field(min_length=1)


@router.post("/companies/search")
def search_companies(request: QixinCompanySearchRequest) -> dict[str, Any]:
    try:
        client = QixinClient.from_env()
        return client.adv_search(request.keyword)
    except QixinConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except QixinUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
