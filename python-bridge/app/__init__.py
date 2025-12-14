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
            """Forward packet to all WebSocket clients."""
            await ws_manager.broadcast(packet)

        bridge.set_packet_callback(on_packet)
        await bridge.start()

        logger.info("✅ Telemetry bridge started successfully")
        return bridge

    except Exception as e:
        logger.error(f"❌ Failed to start telemetry bridge: {e}", exc_info=True)
        # Continue running (API will return errors but won't crash)
        return None


# === Lifecycle Events ===
@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
    """Initialize telemetry bridge on startup and stop on shutdown."""

    # Initialize WebSocket manager
    app_instance.state.websocket_manager = websocket_manager

    # Initialize telemetry bridge
    app_instance.state.bridge = await _init_telemetry_bridge(app_instance.state.websocket_manager)

    yield

    # Cleanup on shutdown
    if app_instance.state.bridge:
        logger.info("Stopping telemetry bridge...")
        await app_instance.state.bridge.stop()
        logger.info("✅ Telemetry bridge stopped")


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
