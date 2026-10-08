"""Health endpoint (spec platform-health)."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter()


class HealthResponse(BaseModel):
    """Health payload. Forbids undeclared fields (regla dura 4)."""

    model_config = ConfigDict(extra="forbid")

    status: str


@router.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return 200 {"status": "ok"} without auth, tenant or DB dependency."""
    return HealthResponse(status="ok")
