from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class HealthResponse(BaseModel):
    status: str = Field(default="ok", json_schema_extra={"example": "ok"})
    version: str = Field(default="1.0.0", json_schema_extra={"example": "1.0.0"})
    time: str = Field(json_schema_extra={"example": "2026-11-13T12:00:00Z"})


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Endpoint pemeriksaan kesehatan layanan."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        time=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
