import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.dependencies import ParamBridge
from app.models import (
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
)

logger = logging.getLogger(__name__)

router = APIRouter()

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


@router.websocket("/live")
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
                        await websocket.send_json(
                            {
                                "type": "error",
                                "code": "INVALID_REQUEST",
                                "message": "Missing 'index' field",
                            }
                        )
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
                        await websocket.send_json(
                            {
                                "type": "error",
                                "code": "PARAM_NOT_FOUND",
                                "message": str(e),
                                "index": index,
                            }
                        )
                    except ParamTimeoutError as e:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "code": "TIMEOUT",
                                "message": str(e),
                                "index": index,
                            }
                        )

                elif action == "set":
                    # SET parameter value
                    index = data.get("index")
                    value = data.get("value")

                    if index is None or value is None:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "code": "INVALID_REQUEST",
                                "message": "Missing 'index' or 'value' field",
                            }
                        )
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
                        await websocket.send_json(
                            {
                                "type": "error",
                                "code": "PARAM_NOT_FOUND",
                                "message": str(e),
                                "index": index,
                            }
                        )
                    except ParamReadOnlyError as e:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "code": "PARAM_READ_ONLY",
                                "message": str(e),
                                "index": index,
                            }
                        )
                    except ParamTimeoutError as e:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "code": "TIMEOUT",
                                "message": str(e),
                                "index": index,
                            }
                        )

                else:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "UNKNOWN_ACTION",
                            "message": f"Unknown action: {action}",
                        }
                    )

            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "INVALID_JSON",
                        "message": "Invalid JSON format",
                    }
                )
            except Exception as e:
                logger.error(
                    f"Error processing PARAM WebSocket message: {e}", exc_info=True
                )
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "INTERNAL_ERROR",
                        "message": str(e),
                    }
                )

    except WebSocketDisconnect:
        logger.info(f"PARAM WebSocket client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"PARAM WebSocket error: {e}", exc_info=True)
    finally:
        param_websocket_clients.discard(websocket)


# === PARAM REST Endpoints ===


@router.get("", response_model=ParamListResponse)
async def get_params_list(param_bridge: ParamBridge) -> ParamListResponse:
    """
    Get list of all parameters with current values.

    Returns:
        List of all parameters with metadata and values
    """
    try:
        params = await param_bridge.list_params()
        return ParamListResponse(
            type="list_response", params=[ParamInfo(**p) for p in params]
        )

    except ParamConnectionError:
        raise HTTPException(status_code=503, detail="PARAM bridge not connected")
    except ParamTimeoutError:
        raise HTTPException(
            status_code=504, detail="Timeout waiting for parameter list"
        )
    except Exception as e:
        logger.error(f"Error listing parameters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{index}", response_model=ParamGetResponse)
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
        return ParamGetResponse(
            type="get_response", index=index, value=value, status="success"
        )

    except ParamNotFoundError:
        raise HTTPException(status_code=404, detail=f"Parameter {index} not found")
    except ParamConnectionError:
        raise HTTPException(status_code=503, detail="PARAM bridge not connected")
    except ParamTimeoutError:
        raise HTTPException(status_code=504, detail="Timeout waiting for parameter")
    except Exception as e:
        logger.error(f"Error getting parameter {index}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{index}", response_model=ParamRestResponse)
async def set_param_value(
    index: int, update: ParamValueUpdate, param_bridge: ParamBridge
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


@router.get("/connection-status", response_model=ParamConnectionStatusRest)
async def get_param_connection_status(
    param_bridge: ParamBridge,
) -> ParamConnectionStatusRest:
    """
    Get PARAM connection status.

    Returns:
        Connection status and last update timestamp
    """
    # Get PARAM stats (for UnifiedBridge compatibility, use get_param_stats if available)
    if hasattr(param_bridge, "get_param_stats"):
        stats = param_bridge.get_param_stats()
    else:
        # Fallback for old ParamUARTBridge
        stats = param_bridge.get_stats()

    last_update = None

    if stats["last_response_time"]:
        last_update = datetime.fromtimestamp(stats["last_response_time"]).isoformat()

    return ParamConnectionStatusRest(
        uart_connected=param_bridge.is_connected(),
        last_update=last_update,
    )
