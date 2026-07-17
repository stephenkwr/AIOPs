"""Health probes.

Two separate concerns, following the liveness/readiness convention:
  * /healthz — liveness: the process is up. No dependencies. Used by Render's
    health check so a cold DB never marks the service unhealthy.
  * /readyz  — readiness: can we actually serve traffic? Runs a real DB query.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", response_model=None)
async def readyz(session: AsyncSession = Depends(get_session)) -> JSONResponse | dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — surface any connectivity failure as 503
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": str(exc)[:200]},
        )
    return {"status": "ready", "database": "ok"}
