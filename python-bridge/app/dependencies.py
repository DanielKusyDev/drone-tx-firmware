from typing import Annotated, Union

from fastapi import HTTPException, Depends, WebSocket
from starlette.requests import Request

from app.config import Settings, get_settings
from app.services.telemetry_bridge import TelemetryBridge
from app.services.param_uart_bridge import ParamUARTBridge
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


async def get_param_bridge(request: Request) -> ParamUARTBridge:
    """
    Get PARAM UART bridge from app state.

    Note: This dependency is for HTTP endpoints only.
    WebSocket endpoints should access websocket.app.state.param_bridge directly.
    """
    if not hasattr(request.app.state, 'param_bridge') or not request.app.state.param_bridge:
        raise HTTPException(status_code=503, detail="PARAM bridge not initialized")
    return request.app.state.param_bridge


Bridge = Annotated[TelemetryBridge, Depends(get_telemetry_bridge)]
ParamBridge = Annotated[ParamUARTBridge, Depends(get_param_bridge)]
AppSettings = Annotated[Settings, Depends(get_settings)]
WsConnection = Annotated[WebSocketConnectionManager, Depends(get_websocket_connection_manager)]
