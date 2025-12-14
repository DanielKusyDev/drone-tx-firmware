import logging
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.params import Query

from app.services.telemetry_bridge import TelemetryBridge
from app.dependencies import Bridge, WsConnection

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(bridge: Bridge) -> dict[str, Any]:
    """
    Health check endpoint.

    Returns:
        200: Bridge is healthy (receiving recent packets)
        503: Bridge is unhealthy or not started
    """
    health = await bridge.get_health()

    if not await bridge.is_healthy():
        raise HTTPException(status_code=503, detail="No recent telemetry")

    return {
        "status": "healthy",
        "last_packet_age_s": health.get("last_packet_age_s"),
        "packets_received": health["packets_received"],
        "is_alive": health["is_alive"],
    }


@router.get("/stats")
async def get_stats(bridge: Bridge) -> dict[str, Any]:
    """
    Get comprehensive statistics.

    Returns detailed stats about:
    - Bridge operation
    - Serial reader
    - Parser (CRC errors, etc.)
    - Packet counts by type
    """
    return await bridge.get_stats()


@router.get("/telemetry/latest")
async def get_latest_telemetry(bridge: Bridge) -> dict[str, dict[str, Any]]:
    """
    Get latest packet of each type.

    Returns:
        Dictionary with latest ATT, MOT, STA, etc.
    """
    latest = await bridge.get_latest_packets()

    if not latest:
        raise HTTPException(status_code=404, detail="No telemetry received yet")

    return latest


@router.get("/telemetry/attitude")
async def get_latest_attitude(bridge: Bridge) -> dict[str, Any] | None:
    """Get latest ATTITUDE packet (roll, pitch, yaw + rates)."""
    attitude = await bridge.get_latest_attitude()

    if not attitude:
        raise HTTPException(status_code=404, detail="No ATTITUDE packet received yet")

    return attitude


@router.get("/telemetry/motors")
async def get_latest_motors(bridge: Bridge) -> dict[str, Any] | None:
    """Get latest MOTORS packet (motor commands, throttle)."""
    motors = await bridge.get_latest_motors()

    if not motors:
        raise HTTPException(status_code=404, detail="No MOTORS packet received yet")

    return motors


@router.get("/telemetry/status")
async def get_latest_status(bridge: Bridge) -> dict[str, Any] | None:
    """Get latest STATUS packet (armed, flags, link quality)."""
    status = await bridge.get_latest_status()

    if not status:
        raise HTTPException(status_code=404, detail="No STATUS packet received yet")

    return status


@router.get("/telemetry/history/{packet_type}")
async def get_packet_history(
    bridge: Bridge, packet_type: str, max_count: int = Query(default=100, ge=1, le=10000)
) -> dict[str, Any]:
    """Get packet history for specific type."""
    history = await bridge.get_packet_history(packet_type.upper(), max_count=max_count)

    return {
        "packet_type": packet_type.upper(),
        "count": len(history),
        "packets": history,
    }


# === WebSocket Endpoint ===
@router.websocket("/ws/telemetry")
async def websocket_telemetry(manager: WsConnection, websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time telemetry streaming.

    Clients will receive packets as they arrive in real-time.
    Each message is a JSON packet (ATT, MOT, STA, etc.)

    Usage:
        const ws = new WebSocket('ws://localhost:8000/ws/telemetry');
        ws.onmessage = (event) => {
            const packet = JSON.parse(event.data);
            console.log(packet.type, packet.seq);
        };
    """
    await manager.connect(websocket)

    try:
        # Keep connection alive and handle client messages
        while True:
            # Wait for client message (ping, etc.)
            data = await websocket.receive_text()

            # Handle client commands if needed
            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# === Utility Endpoints ===


@router.get("/ports")
async def list_serial_ports():
    """List available serial ports (useful for debugging)."""
    return {"ports": TelemetryBridge.list_ports()}
