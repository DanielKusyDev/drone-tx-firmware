import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.params import Query

from app.dependencies import Bridge, ParamBridge, WsConnection
from app.models import (
    HealthResponse,
    StatsResponse,
    LatestTelemetryResponse,
    AttitudePacket,
    MotorsPacket,
    StatusPacket,
    PacketHistoryResponse,
    PortsResponse,
    ParamListResponse,
    ParamGetResponse,
    ParamValueUpdate,
    ParamRestResponse,
    ParamConnectionStatusRest,
    ParamInfo,
)
from app.services.unified_bridge import (
    ParamTimeoutError,
    ParamNotFoundError,
    ParamReadOnlyError,
    ParamConnectionError,
    UnifiedBridge,
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
    return PortsResponse(ports=UnifiedBridge.list_ports())


# === PARAM Endpoints ===


# WebSocket clients registry for PARAM
param_websocket_clients: set[WebSocket] = set()


async def broadcast_param_message(message: dict[str, Any]) -> None:
    """Broadcast PARAM message to all connected WebSocket clients."""
    disconnected_clients = set()

    for client in param_websocket_clients:
        try:
            await client.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send to PARAM WebSocket client: {e}")
            disconnected_clients.add(client)

    # Remove disconnected clients
    param_websocket_clients.difference_update(disconnected_clients)


@router.websocket("/params/live")
async def websocket_params(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time parameter management.

    Client → Server messages:
        {"action": "list"}
        {"action": "get", "index": 0}
        {"action": "set", "index": 0, "value": 300.5}

    Server → Client messages:
        {"type": "list_response", "params": [...]}
        {"type": "get_response", "index": 0, "value": 250.0, "status": "success"}
        {"type": "set_response", "index": 0, "value": 300.5, "status": "success"}
        {"type": "error", "code": "PARAM_NOT_FOUND", "message": "...", "index": 99}
        {"type": "connection_status", "uart_connected": true, "controller_connected": true}
        {"type": "param_changed", "index": 0, "value": 300.5, "changed_by": "client_123"}
    """
    await websocket.accept()

    # Get param bridge from app state
    param_bridge = websocket.app.state.param_bridge
    if not param_bridge:
        await websocket.close(code=1011, reason="PARAM bridge not initialized")
        return

    param_websocket_clients.add(websocket)

    # Get client ID for tracking who changed params
    client_id = f"client_{id(websocket)}"

    logger.info(f"PARAM WebSocket client connected: {client_id}")

    try:
        # Send initial connection status
        connection_status = {
            "type": "connection_status",
            "uart_connected": param_bridge.is_connected(),
            "controller_connected": param_bridge.is_connected(),  # Simplified
            "timestamp": datetime.now().isoformat(),
        }
        await websocket.send_json(connection_status)

        while True:
            # Wait for client message
            data_text = await websocket.receive_text()

            try:
                data = json.loads(data_text)
                action = data.get("action")

                if action == "list":
                    # LIST all parameters
                    params = await param_bridge.list_params()
                    response = {
                        "type": "list_response",
                        "params": params,
                    }
                    await websocket.send_json(response)

                elif action == "get":
                    # GET single parameter
                    index = data.get("index")
                    if index is None:
                        await websocket.send_json({
                            "type": "error",
                            "code": "INVALID_REQUEST",
                            "message": "Missing 'index' field",
                        })
                        continue

                    try:
                        value = await param_bridge.get_param(index)
                        response = {
                            "type": "get_response",
                            "index": index,
                            "value": value,
                            "status": "success",
                        }
                        await websocket.send_json(response)

                    except ParamNotFoundError as e:
                        await websocket.send_json({
                            "type": "error",
                            "code": "PARAM_NOT_FOUND",
                            "message": str(e),
                            "index": index,
                        })
                    except ParamTimeoutError as e:
                        await websocket.send_json({
                            "type": "error",
                            "code": "TIMEOUT",
                            "message": str(e),
                            "index": index,
                        })

                elif action == "set":
                    # SET parameter value
                    index = data.get("index")
                    value = data.get("value")

                    if index is None or value is None:
                        await websocket.send_json({
                            "type": "error",
                            "code": "INVALID_REQUEST",
                            "message": "Missing 'index' or 'value' field",
                        })
                        continue

                    try:
                        await param_bridge.set_param(index, value)

                        # Respond to this client
                        response = {
                            "type": "set_response",
                            "index": index,
                            "value": value,
                            "status": "success",
                        }
                        await websocket.send_json(response)

                        # Broadcast to all other clients
                        broadcast_msg = {
                            "type": "param_changed",
                            "index": index,
                            "value": value,
                            "changed_by": client_id,
                        }
                        await broadcast_param_message(broadcast_msg)

                    except ParamNotFoundError as e:
                        await websocket.send_json({
                            "type": "error",
                            "code": "PARAM_NOT_FOUND",
                            "message": str(e),
                            "index": index,
                        })
                    except ParamReadOnlyError as e:
                        await websocket.send_json({
                            "type": "error",
                            "code": "PARAM_READ_ONLY",
                            "message": str(e),
                            "index": index,
                        })
                    except ParamTimeoutError as e:
                        await websocket.send_json({
                            "type": "error",
                            "code": "TIMEOUT",
                            "message": str(e),
                            "index": index,
                        })

                else:
                    await websocket.send_json({
                        "type": "error",
                        "code": "UNKNOWN_ACTION",
                        "message": f"Unknown action: {action}",
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_JSON",
                    "message": "Invalid JSON format",
                })
            except Exception as e:
                logger.error(f"Error processing PARAM WebSocket message: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "code": "INTERNAL_ERROR",
                    "message": str(e),
                })

    except WebSocketDisconnect:
        logger.info(f"PARAM WebSocket client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"PARAM WebSocket error: {e}", exc_info=True)
    finally:
        param_websocket_clients.discard(websocket)


# === PARAM REST Endpoints ===


@router.get("/params", response_model=ParamListResponse)
async def get_params_list(param_bridge: ParamBridge) -> ParamListResponse:
    """
    Get list of all parameters with current values.

    Returns:
        List of all parameters with metadata and values
    """
    try:
        params = await param_bridge.list_params()
        return ParamListResponse(type="list_response", params=[ParamInfo(**p) for p in params])

    except ParamConnectionError:
        raise HTTPException(status_code=503, detail="PARAM bridge not connected")
    except ParamTimeoutError:
        raise HTTPException(status_code=504, detail="Timeout waiting for parameter list")
    except Exception as e:
        logger.error(f"Error listing parameters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/params/{index}", response_model=ParamGetResponse)
async def get_param_value(index: int, param_bridge: ParamBridge) -> ParamGetResponse:
    """
    Get single parameter value.

    Args:
        index: Parameter index (0-255)

    Returns:
        Parameter value
    """
    try:
        value = await param_bridge.get_param(index)
        return ParamGetResponse(type="get_response", index=index, value=value, status="success")

    except ParamNotFoundError:
        raise HTTPException(status_code=404, detail=f"Parameter {index} not found")
    except ParamConnectionError:
        raise HTTPException(status_code=503, detail="PARAM bridge not connected")
    except ParamTimeoutError:
        raise HTTPException(status_code=504, detail="Timeout waiting for parameter")
    except Exception as e:
        logger.error(f"Error getting parameter {index}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/params/{index}", response_model=ParamRestResponse)
async def set_param_value(
    index: int,
    update: ParamValueUpdate,
    param_bridge: ParamBridge
) -> ParamRestResponse:
    """
    Set parameter value.

    Args:
        index: Parameter index (0-255)
        update: New value

    Returns:
        Confirmation with new value
    """
    try:
        await param_bridge.set_param(index, update.value)

        # Broadcast to WebSocket clients
        broadcast_msg = {
            "type": "param_changed",
            "index": index,
            "value": update.value,
            "changed_by": "rest_api",
        }
        await broadcast_param_message(broadcast_msg)

        return ParamRestResponse(status="success", value=update.value)

    except ParamNotFoundError:
        raise HTTPException(status_code=404, detail=f"Parameter {index} not found")
    except ParamReadOnlyError:
        raise HTTPException(status_code=403, detail=f"Parameter {index} is read-only")
    except ParamConnectionError:
        raise HTTPException(status_code=503, detail="PARAM bridge not connected")
    except ParamTimeoutError:
        raise HTTPException(status_code=504, detail="Timeout waiting for confirmation")
    except Exception as e:
        logger.error(f"Error setting parameter {index}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/params/connection-status", response_model=ParamConnectionStatusRest)
async def get_param_connection_status(param_bridge: ParamBridge) -> ParamConnectionStatusRest:
    """
    Get PARAM connection status.

    Returns:
        Connection status and last update timestamp
    """
    # Get PARAM stats (for UnifiedBridge compatibility, use get_param_stats if available)
    if hasattr(param_bridge, 'get_param_stats'):
        stats = param_bridge.get_param_stats()
    else:
        # Fallback for old ParamUARTBridge
        stats = param_bridge.get_stats()

    last_update = None

    if stats['last_response_time']:
        last_update = datetime.fromtimestamp(stats['last_response_time']).isoformat()

    return ParamConnectionStatusRest(
        uart_connected=param_bridge.is_connected(),
        last_update=last_update,
    )
