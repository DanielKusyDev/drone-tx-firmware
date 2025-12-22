import logging

from fastapi import APIRouter, HTTPException

from app.dependencies import Bridge
from app.models import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(bridge: Bridge) -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        200: Bridge is healthy (receiving recent packets)
        503: Bridge is unhealthy or not started
    """
    health = await bridge.get_health()

    if not await bridge.is_healthy():
        raise HTTPException(status_code=503, detail="No recent telemetry")

    return HealthResponse(
        status="healthy",
        last_packet_age_s=health.get("last_packet_age_s"),
        packets_received=health["packets_received"],
        is_alive=health["is_alive"],
    )
