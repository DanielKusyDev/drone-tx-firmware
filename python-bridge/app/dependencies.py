from typing import Annotated, Union

from fastapi import HTTPException, Depends, WebSocket
from starlette.requests import Request

from app.config import Settings, get_settings
from app.services.telemetry_bridge import TelemetryBridge
from app.services.websocket_manager import WebSocketConnectionManager, websocket_manager


async def get_websocket_connection_manager() -> WebSocketConnectionManager:
    """
    Get WebSocket connection manager from app state.

    Works with both HTTP requests and WebSocket connections.
    """
    if not websocket_manager:
        raise HTTPException(status_code=503, detail="WebSocket Connection not initialized")
    return websocket_manager


async def get_telemetry_bridge(request: Request) -> TelemetryBridge:
    """
    Get telemetry bridge from app state.

    Works with both HTTP requests and WebSocket connections.
    """
    if not request.app.state.bridge:
        raise HTTPException(status_code=503, detail="Bridge not initialized")
    return request.app.state.bridge


Bridge = Annotated[TelemetryBridge, Depends(get_telemetry_bridge)]
AppSettings = Annotated[Settings, Depends(get_settings)]
WsConnection = Annotated[WebSocketConnectionManager, Depends(get_websocket_connection_manager)]
