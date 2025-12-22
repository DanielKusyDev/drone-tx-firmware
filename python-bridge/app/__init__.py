"""
FastAPI Integration for Asyncio Telemetry Bridge
Demonstrates how to integrate async TelemetryBridge with FastAPI.

This is a complete, ready-to-use FastAPI server for drone telemetry.

Usage:
    python -m app.main --port COM3 --baudrate 115200

Or with uvicorn:
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload

Author: Claude + Daniel
Date: 2025-12-14
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import settings
from app.services.telemetry_bridge import TelemetryBridge
from app.services.param_uart_bridge import ParamUARTBridge
from app.services.websocket_manager import WebSocketConnectionManager, websocket_manager

# Configure logging
logger = logging.getLogger(__name__)


async def _init_telemetry_bridge(
    ws_manager: WebSocketConnectionManager,
) -> TelemetryBridge | None:
    """Initialize telemetry bridge with WebSocket broadcast callback."""
    logger.info(f"Starting telemetry bridge: {settings.telemetry_port} @ {settings.baudrate}")

    try:
        bridge = TelemetryBridge(settings.telemetry_port, settings.baudrate)

        # Set async callback for real-time WebSocket broadcast
        async def on_packet(packet: dict[str, Any]):
            """
            Broadcast individual telemetry packets to all WebSocket clients.

            Each packet is sent immediately as it arrives from the serial port.
            This provides lowest latency and preserves packet timing:
            - ATTITUDE (ATT): 20 Hz
            - CONTROL (CTL): 10 Hz
            - MOTORS (MOT): 5 Hz
            - STATUS (STA): 2.5 Hz
            - SENSORS (SENS): 1.25 Hz
            - SAFETY (SAFE): 1.25 Hz
            - PERFORMANCE (PERF): 0.625 Hz

            WebSocket message format: Individual packet (see WebSocketPacket in models.py)
            """
            await ws_manager.broadcast(packet)

        bridge.set_packet_callback(on_packet)
        await bridge.start()

        logger.info("✅ Telemetry bridge started successfully")
        return bridge

    except Exception as e:
        logger.error(f"❌ Failed to start telemetry bridge: {e}", exc_info=True)
        # Continue running (API will return errors but won't crash)
        return None


async def _init_param_bridge() -> ParamUARTBridge | None:
    """Initialize PARAM UART bridge."""
    logger.info(f"Starting PARAM bridge: {settings.param_uart_port} @ {settings.param_uart_baudrate}")

    try:
        bridge = ParamUARTBridge(
            timeout=settings.param_uart_timeout,
            reconnect_interval=settings.param_uart_reconnect_interval,
        )

        # Connect to UART
        await bridge.connect(settings.param_uart_port, settings.param_uart_baudrate)

        # Start auto-reconnect task
        bridge.start_auto_reconnect()

        logger.info("✅ PARAM bridge started successfully")
        return bridge

    except Exception as e:
        logger.error(f"❌ Failed to start PARAM bridge: {e}", exc_info=True)
        # Continue running (API will return errors but won't crash)
        return None


# === Lifecycle Events ===
@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
    """Initialize telemetry bridge and PARAM bridge on startup and stop on shutdown."""

    # Initialize WebSocket manager
    app_instance.state.websocket_manager = websocket_manager

    # Initialize telemetry bridge
    app_instance.state.bridge = await _init_telemetry_bridge(app_instance.state.websocket_manager)

    # Initialize PARAM bridge
    app_instance.state.param_bridge = await _init_param_bridge()

    yield

    # Cleanup on shutdown
    if app_instance.state.bridge:
        logger.info("Stopping telemetry bridge...")
        await app_instance.state.bridge.stop()
        logger.info("✅ Telemetry bridge stopped")

    if hasattr(app_instance.state, 'param_bridge') and app_instance.state.param_bridge:
        logger.info("Stopping PARAM bridge...")
        await app_instance.state.param_bridge.disconnect()
        logger.info("✅ PARAM bridge stopped")


# FastAPI app
app = FastAPI(
    title="Drone Telemetry API",
    description="Real-time telemetry from ESP32 drone",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware (allow React UI from any origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(router)
