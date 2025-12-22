import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.params import Query

from app.dependencies import Bridge, WsConnection
from app.models import StatusPacket, PacketHistoryResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status", response_model=StatusPacket)
async def get_latest_status(bridge: Bridge) -> StatusPacket:
    """Get latest STATUS packet (armed, flags, link quality)."""
    status = await bridge.get_latest_status()

    if not status:
        raise HTTPException(status_code=404, detail="No STATUS packet received yet")

    return StatusPacket(**status)


@router.get("/history/{packet_type}", response_model=PacketHistoryResponse)
async def get_packet_history(
    bridge: Bridge,
    packet_type: str,
    max_count: int = Query(default=100, ge=1, le=10000),
) -> PacketHistoryResponse:
    """Get packet history for specific type."""
    history = await bridge.get_packet_history(packet_type.upper(), max_count=max_count)

    return PacketHistoryResponse(
        packet_type=packet_type.upper(),
        count=len(history),
        packets=history,
    )


# === WebSocket Endpoint ===
@router.websocket("/ws")
async def websocket_telemetry(manager: WsConnection, websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time telemetry streaming.

    IMPORTANT: This endpoint sends INDIVIDUAL packets as they arrive from the drone.

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
