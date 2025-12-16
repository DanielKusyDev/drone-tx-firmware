import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.params import Query

from app.services.telemetry_bridge import TelemetryBridge
from app.dependencies import Bridge, WsConnection
from app.models import (
    HealthResponse,
    StatsResponse,
    LatestTelemetryResponse,
    AttitudePacket,
    MotorsPacket,
    StatusPacket,
    PacketHistoryResponse,
    PortsResponse,
)

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


@router.get("/stats", response_model=StatsResponse)
async def get_stats(bridge: Bridge) -> StatsResponse:
    """
    Get comprehensive statistics.

    Returns detailed stats about:
    - Bridge operation
    - Serial reader
    - Parser (CRC errors, etc.)
    - Packet counts by type
    """
    stats = await bridge.get_stats()
    return StatsResponse(**stats)


@router.get("/telemetry/latest", response_model=LatestTelemetryResponse)
async def get_latest_telemetry(bridge: Bridge) -> LatestTelemetryResponse:
    """
    Get latest packet of each type.

    Returns:
        Dictionary with latest ATT, MOT, STA, etc.
    """
    latest = await bridge.get_latest_packets()

    if not latest:
        raise HTTPException(status_code=404, detail="No telemetry received yet")

    return LatestTelemetryResponse(**latest)


@router.get("/telemetry/attitude", response_model=AttitudePacket)
async def get_latest_attitude(bridge: Bridge) -> AttitudePacket:
    """Get latest ATTITUDE packet (roll, pitch, yaw + rates)."""
    attitude = await bridge.get_latest_attitude()

    if not attitude:
        raise HTTPException(status_code=404, detail="No ATTITUDE packet received yet")

    return AttitudePacket(**attitude)


@router.get("/telemetry/motors", response_model=MotorsPacket)
async def get_latest_motors(bridge: Bridge) -> MotorsPacket:
    """Get latest MOTORS packet (motor commands, throttle)."""
    motors = await bridge.get_latest_motors()

    if not motors:
        raise HTTPException(status_code=404, detail="No MOTORS packet received yet")

    return MotorsPacket(**motors)


@router.get("/telemetry/status", response_model=StatusPacket)
async def get_latest_status(bridge: Bridge) -> StatusPacket:
    """Get latest STATUS packet (armed, flags, link quality)."""
    status = await bridge.get_latest_status()

    if not status:
        raise HTTPException(status_code=404, detail="No STATUS packet received yet")

    return StatusPacket(**status)


@router.get("/telemetry/history/{packet_type}", response_model=PacketHistoryResponse)
async def get_packet_history(
    bridge: Bridge, packet_type: str, max_count: int = Query(default=100, ge=1, le=10000)
) -> PacketHistoryResponse:
    """Get packet history for specific type."""
    history = await bridge.get_packet_history(packet_type.upper(), max_count=max_count)

    return PacketHistoryResponse(
        packet_type=packet_type.upper(),
        count=len(history),
        packets=history,
    )


# === WebSocket Endpoint ===
@router.websocket("/ws/telemetry")
async def websocket_telemetry(manager: WsConnection, websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time telemetry streaming.

    IMPORTANT: This endpoint sends INDIVIDUAL packets as they arrive from the drone,
    NOT aggregated state like GET /telemetry/latest does.

    Message Format:
        - Each WebSocket message is ONE packet (see WebSocketPacket in models.py)
        - Packet type indicated by "type" field: "ATT", "MOT", "STA", "CTL", etc.
        - Message rate varies by packet type:
          * ATTITUDE (ATT): 20 Hz - roll/pitch/yaw angles and rates
          * MOTORS (MOT): 5 Hz - motor commands and throttle
          * STATUS (STA): 2.5 Hz - armed state, flags, battery
          * CONTROL (CTL): 10 Hz - PID setpoints and outputs
          * SENSORS (SENS): 1.25 Hz - raw IMU data
          * SAFETY (SAFE): 1.25 Hz - ground confidence, error flags
          * PERFORMANCE (PERF): 0.625 Hz - loop timing, CPU, heap

    Client Implementation:
        Frontend should accumulate packets into state by type:

        const ws = new WebSocket('ws://localhost:8000/ws/telemetry');
        const latestData = { ATT: null, MOT: null, STA: null, ... };

        ws.onmessage = (event) => {
            const packet = JSON.parse(event.data);
            latestData[packet.type] = packet;  // Update corresponding packet type

            // Now use latestData.ATT, latestData.MOT, etc.
            if (latestData.ATT) {
                updateArtificialHorizon(latestData.ATT.roll_deg, latestData.ATT.pitch_deg);
            }
        };

    Why Individual Packets?
        - Lowest latency: Attitude data reaches UI in <50ms
        - Bandwidth efficient: Only send what changed
        - Preserves packet timing: Critical data (attitude) arrives faster than diagnostics
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


@router.get("/ports", response_model=PortsResponse)
async def list_serial_ports() -> PortsResponse:
    """List available serial ports (useful for debugging)."""
    return PortsResponse(ports=TelemetryBridge.list_ports())
