"""
EWC Compute — Health endpoints.

Two probes following Kubernetes conventions:
  GET /health/live   — liveness:  is the process running?
  GET /health/ready  — readiness: can it serve requests? (checks DB + Redis)

The root /health route returns the combined ready status for simple load balancer checks.
"""
import time
from typing import Literal

import structlog
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from redis.asyncio import Redis

from app.core.config import settings
from app.core.database import get_db_client
from app.core.cache import get_redis_client

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])

_startup_time = time.time()


class ComponentStatus(BaseModel):
    status: Literal["ok", "degraded", "down"]
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    version: str
    environment: str
    uptime_seconds: float
    components: dict[str, ComponentStatus]


async def _check_mongodb() -> ComponentStatus:
    """Ping MongoDB and measure round-trip latency."""
    try:
        client: AsyncIOMotorClient = get_db_client()
        t0 = time.monotonic()
        await client.admin.command("ping")
        latency_ms = (time.monotonic() - t0) * 1000
        return ComponentStatus(status="ok", latency_ms=round(latency_ms, 2))
    except Exception as exc:
        logger.warning("health.mongodb.down", error=str(exc))
        return ComponentStatus(status="down", detail=str(exc))


async def _check_redis() -> ComponentStatus:
    """Ping Redis and measure round-trip latency."""
    try:
        redis: Redis = get_redis_client()
        t0 = time.monotonic()
        await redis.ping()
        latency_ms = (time.monotonic() - t0) * 1000
        return ComponentStatus(status="ok", latency_ms=round(latency_ms, 2))
    except Exception as exc:
        logger.warning("health.redis.down", error=str(exc))
        return ComponentStatus(status="down", detail=str(exc))


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Combined health check",
)
async def health_check() -> JSONResponse:
    """
    Combined liveness + readiness check.
    Returns HTTP 200 if all components are ok, HTTP 503 if any are down.
    Used by load balancers and the deploy-dev.yml smoke test.
    """
    mongodb_status = await _check_mongodb()
    redis_status = await _check_redis()

    components = {
        "mongodb": mongodb_status,
        "redis": redis_status,
    }

    all_ok = all(c.status == "ok" for c in components.values())
    overall = "ok" if all_ok else "degraded"

    response = HealthResponse(
        status=overall,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        uptime_seconds=round(time.time() - _startup_time, 1),
        components=components,
    )

    http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=response.model_dump(), status_code=http_status)


@router.get("/health/live", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    """Kubernetes liveness probe — returns 200 as long as the process is running."""
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe")
async def readiness() -> JSONResponse:
    """
    Kubernetes readiness probe.
    Returns 200 only when MongoDB and Redis are reachable.
    """
    mongodb_status = await _check_mongodb()
    redis_status = await _check_redis()

    ready = mongodb_status.status == "ok" and redis_status.status == "ok"
    http_status = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        content={
            "ready": ready,
            "mongodb": mongodb_status.status,
            "redis": redis_status.status,
        },
        status_code=http_status,
    )
