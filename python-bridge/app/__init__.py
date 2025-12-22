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

from app.api import info_routes, params_routes, telemetry_routes
from app.config import settings
from app.services.unified_bridge import UnifiedBridge
from app.services.websocket_manager import WebSocketConnectionManager, websocket_manager

# Configure logging
logger = logging.getLogger(__name__)


async def _init_unified_bridge(
    ws_manager: WebSocketConnectionManager,
) -> UnifiedBridge | None:
    """Initialize unified bridge for telemetry and PARAM communication."""
    logger.info(
        f"Starting unified bridge: {settings.telemetry_port} @ {settings.baudrate}"
    )

    try:
        bridge = UnifiedBridge(
            port=settings.telemetry_port,
            baudrate=settings.baudrate,
            history_size=1000,
            param_timeout=settings.param_uart_timeout,
        )

        # Set async callback for real-time WebSocket broadcast
        async def on_telemetry(packet: dict[str, Any]):
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

        bridge.set_telemetry_callback(on_telemetry)
        await bridge.start()

        logger.info("✅ Unified bridge started successfully")
        return bridge

    except Exception as e:
        logger.error(f"❌ Failed to start unified bridge: {e}", exc_info=True)
        # Continue running (API will return errors but won't crash)
        return None


# === Lifecycle Events ===
@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
    """Initialize unified bridge on startup and stop on shutdown."""

    # Initialize WebSocket manager
    app_instance.state.websocket_manager = websocket_manager

    # Initialize unified bridge (handles both telemetry and PARAM)
    app_instance.state.bridge = await _init_unified_bridge(
        app_instance.state.websocket_manager
    )

    # Also set param_bridge to the same bridge for API compatibility
    app_instance.state.param_bridge = app_instance.state.bridge

    yield

    # Cleanup on shutdown
    if app_instance.state.bridge:
        logger.info("Stopping unified bridge...")
        await app_instance.state.bridge.stop()
        logger.info("✅ Unified bridge stopped")


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
app.include_router(info_routes.router)
app.include_router(info_routes.router)
