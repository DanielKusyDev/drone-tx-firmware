"""
FastAPI Integration Example
Demonstrates how to integrate TelemetryBridge with FastAPI.

This is a complete, ready-to-use FastAPI server for drone telemetry.

Usage:
    python fastapi_example.py --port COM3 --baudrate 115200

Or with uvicorn:
    uvicorn fastapi_example:app --host 0.0.0.0 --port 8000 --reload

Author: Claude + Daniel
Date: 2025-12-03
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
import logging
import argparse
from telemetry_bridge import TelemetryBridge
import asyncio
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Drone Telemetry API",
    description="Real-time telemetry from ESP32 drone",
    version="1.0.0"
)

# CORS middleware (allow React UI from any origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global bridge instance (initialized on startup)
bridge: Optional[TelemetryBridge] = None

# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and register new connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove connection."""
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients."""
        if not self.active_connections:
            return

        # Send to all clients concurrently
        await asyncio.gather(
            *[connection.send_json(message) for connection in self.active_connections],
            return_exceptions=True
        )

manager = ConnectionManager()


# === Lifecycle Events ===

@app.on_event("startup")
async def startup_event():
    """Initialize telemetry bridge on startup."""
    global bridge

    # Get config from command line args or environment
    import os
    port = os.getenv('TELEMETRY_PORT', 'COM3')
    baudrate = int(os.getenv('TELEMETRY_BAUDRATE', '115200'))

    logger.info(f"Starting telemetry bridge: {port} @ {baudrate}")

    try:
        bridge = TelemetryBridge(port, baudrate)

        # Set callback for real-time WebSocket broadcast
        def on_packet(packet: Dict[str, Any]):
            """Forward packet to all WebSocket clients."""
            # Create asyncio task to avoid blocking serial reader thread
            asyncio.create_task(manager.broadcast(packet))

        bridge.set_packet_callback(on_packet)
        bridge.start()

        logger.info("✅ Telemetry bridge started successfully")

    except Exception as e:
        logger.error(f"❌ Failed to start telemetry bridge: {e}")
        # Continue running (API will return errors but won't crash)


@app.on_event("shutdown")
async def shutdown_event():
    """Stop telemetry bridge on shutdown."""
    global bridge

    if bridge:
        logger.info("Stopping telemetry bridge...")
        bridge.stop()
        logger.info("✅ Telemetry bridge stopped")


# === REST Endpoints ===

@app.get("/")
async def root():
    """API info."""
    return {
        "name": "Drone Telemetry API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "telemetry": "/telemetry/latest",
            "attitude": "/telemetry/attitude",
            "motors": "/telemetry/motors",
            "status": "/telemetry/status",
            "health": "/health",
            "stats": "/stats",
            "websocket": "ws://localhost:8000/ws/telemetry"
        }
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns:
        200: Bridge is healthy (receiving recent packets)
        503: Bridge is unhealthy or not started
    """
    if not bridge:
        raise HTTPException(status_code=503, detail="Bridge not initialized")

    health = bridge.get_health()

    if not bridge.is_healthy():
        raise HTTPException(status_code=503, detail="No recent telemetry")

    return {
        "status": "healthy",
        "last_packet_age_s": health.get('last_packet_age_s'),
        "packets_received": health['packets_received'],
        "is_alive": health['is_alive']
    }


@app.get("/stats")
async def get_stats():
    """
    Get comprehensive statistics.

    Returns detailed stats about:
    - Bridge operation
    - Serial reader
    - Parser (CRC errors, etc.)
    - Packet counts by type
    """
    if not bridge:
        raise HTTPException(status_code=503, detail="Bridge not initialized")

    return bridge.get_stats()


@app.get("/telemetry/latest")
async def get_latest_telemetry():
    """
    Get latest packet of each type.

    Returns:
        Dictionary with latest ATT, MOT, STA, etc.
    """
    if not bridge:
        raise HTTPException(status_code=503, detail="Bridge not initialized")

    latest = bridge.get_latest_packets()

    if not latest:
        raise HTTPException(status_code=404, detail="No telemetry received yet")

    return latest


@app.get("/telemetry/attitude")
async def get_latest_attitude():
    """Get latest ATTITUDE packet (roll, pitch, yaw + rates)."""
    if not bridge:
        raise HTTPException(status_code=503, detail="Bridge not initialized")

    attitude = bridge.get_latest_attitude()

    if not attitude:
        raise HTTPException(status_code=404, detail="No ATTITUDE packet received yet")

    return attitude


@app.get("/telemetry/motors")
async def get_latest_motors():
    """Get latest MOTORS packet (motor commands, throttle)."""
    if not bridge:
        raise HTTPException(status_code=503, detail="Bridge not initialized")

    motors = bridge.get_latest_motors()

    if not motors:
        raise HTTPException(status_code=404, detail="No MOTORS packet received yet")

    return motors


@app.get("/telemetry/status")
async def get_latest_status():
    """Get latest STATUS packet (armed, flags, link quality)."""
    if not bridge:
        raise HTTPException(status_code=503, detail="Bridge not initialized")

    status = bridge.get_latest_status()

    if not status:
        raise HTTPException(status_code=404, detail="No STATUS packet received yet")

    return status


@app.get("/telemetry/history/{packet_type}")
async def get_packet_history(packet_type: str, max_count: int = 100):
    """
    Get packet history for specific type.

    Args:
        packet_type: 'ATT', 'MOT', 'STA', etc.
        max_count: Max packets to return (default: 100)

    Returns:
        List of packets (newest last)
    """
    if not bridge:
        raise HTTPException(status_code=503, detail="Bridge not initialized")

    history = bridge.get_packet_history(packet_type.upper(), max_count=max_count)

    return {
        "packet_type": packet_type.upper(),
        "count": len(history),
        "packets": history
    }


# === WebSocket Endpoint ===

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
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

@app.get("/ports")
async def list_serial_ports():
    """List available serial ports (useful for debugging)."""
    return {
        "ports": TelemetryBridge.list_ports()
    }


# === CLI Entry Point ===

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Drone Telemetry FastAPI Server')

    parser.add_argument(
        '-p', '--port',
        type=str,
        default='COM3',
        help='Serial port (e.g., COM3 or /dev/ttyUSB0)'
    )

    parser.add_argument(
        '-b', '--baudrate',
        type=int,
        default=115200,
        help='Serial baud rate (default: 115200)'
    )

    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='FastAPI host (default: 0.0.0.0)'
    )

    parser.add_argument(
        '--api-port',
        type=int,
        default=8000,
        help='FastAPI port (default: 8000)'
    )

    parser.add_argument(
        '--list-ports',
        action='store_true',
        help='List available serial ports and exit'
    )

    args = parser.parse_args()

    # List ports if requested
    if args.list_ports:
        print("Available serial ports:")
        for port in TelemetryBridge.list_ports():
            print(f"  {port['device']}: {port['description']}")
        return

    # Set environment variables for startup event
    import os
    os.environ['TELEMETRY_PORT'] = args.port
    os.environ['TELEMETRY_BAUDRATE'] = str(args.baudrate)

    # Run FastAPI server
    logger.info(f"Starting FastAPI server on {args.host}:{args.api_port}")
    logger.info(f"Telemetry: {args.port} @ {args.baudrate}")

    uvicorn.run(
        app,
        host=args.host,
        port=args.api_port,
        log_level="info"
    )


if __name__ == '__main__':
    main()
