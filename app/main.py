from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.chat import router as chat_router
from app.api.company_agent import router as company_agent_router
from app.api.location_agent import router as location_agent_router
from app.api.qixin import router as qixin_router


app = FastAPI(title="Information Entry Agent")
PLAYGROUND_FILE = (
    Path(__file__).resolve().parent / "playground" / "distributor_chat" / "index.html"
)
LOCATION_PLAYGROUND_FILE = (
    Path(__file__).resolve().parent / "playground" / "location_agent" / "index.html"
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/playground/distributor-agent")
def distributor_agent_playground() -> FileResponse:
    return FileResponse(PLAYGROUND_FILE)


@app.get("/playground/location-agent")
def location_agent_playground() -> FileResponse:
    return FileResponse(LOCATION_PLAYGROUND_FILE)


app.include_router(chat_router)
app.include_router(company_agent_router)
app.include_router(location_agent_router)
app.include_router(qixin_router)
