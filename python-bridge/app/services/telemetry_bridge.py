"""
Telemetry Bridge - Orchestration Layer (Asyncio version)
Manages serial reader and provides clean interface for async backends (FastAPI, WebSocket, etc.)

This is the main entry point for integrating telemetry into any async application.

Author: Claude + Daniel
Date: 2025-12-14
"""

import asyncio
import logging
import time
from typing import Any, Callable, Awaitable

import aiorwlock

from app.services.serial_reader import SerialReader, list_serial_ports

logger = logging.getLogger(__name__)


class TelemetryBridge:
    """
    High-level async telemetry bridge.

    Manages serial reader and provides:
    - Latest packet cache (quick access to most recent data)
    - Packet history (rolling buffer)
    - Statistics and health monitoring
    - Event callbacks for real-time processing

    This class is designed to be backend-agnostic. You can:
    - Subscribe to packet events
    - Query latest data
    - Get packet history
    - Monitor health/statistics

    Usage with callback (e.g., FastAPI WebSocket):
        bridge = TelemetryBridge('COM3', 115200)

        async def on_packet(packet):
            # Send to WebSocket clients
            await websocket.send_json(packet)

        bridge.set_packet_callback(on_packet)
        await bridge.start()

    Usage with polling (e.g., FastAPI REST endpoint):
        bridge = TelemetryBridge('COM3', 115200)
        await bridge.start()

        @app.get("/telemetry/latest")
        async def get_latest():
            return bridge.get_latest_packets()
    """

    def __init__(self, port: str, baudrate: int, history_size: int = 1000):
        """
        Initialize telemetry bridge.

        Args:
            port: Serial port path
            baudrate: Baud rate (default: 115200)
            history_size: Max packets to keep in history (default: 1000)
        """
        self.port = port
        self.baudrate = baudrate
        self.history_size = history_size

        self.reader = SerialReader(port, baudrate)

        # Latest packet cache (one per packet type)
        self._latest_packets: dict[str, dict[str, Any]] = {}

        # Packet history (rolling buffer)
        self._packet_history: list[dict[str, Any]] = []

        # Lock for thread-safe access to shared data
        self._lock = aiorwlock.RWLock()

        # User callback
        self._user_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None

        # Register internal callback
        self.reader.set_packet_callback(self._on_packet)

        # Health monitoring
        self._health = {
            "last_packet_time": None,
            "packets_received": 0,
            "packets_by_type": {},
        }

    def set_packet_callback(self, callback: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        """
        Set async callback for real-time packet processing.

        The callback will be awaited from the reader task.

        Args:
            callback: Async function(packet_dict) to call for each packet
        """
        self._user_callback = callback

    async def start(self) -> None:
        """Start telemetry bridge."""
        logger.info(f"Starting telemetry bridge: {self.port} @ {self.baudrate}")
        await self.reader.start()
        logger.info("Telemetry bridge started")

    async def stop(self) -> None:
        """Stop telemetry bridge."""
        logger.info("Stopping telemetry bridge...")
        await self.reader.stop()
        logger.info("Telemetry bridge stopped")

    async def _on_packet(self, packet: dict[str, Any]) -> None:
        """
        Internal packet handler (called from reader task).

        Updates cache, history, health stats, and calls user callback.

        Args:
            packet: Parsed packet dictionary
        """
        packet_type = packet["type"]

        # Update shared data with lock
        async with self._lock.writer_lock:
            # Update latest packet cache
            self._latest_packets[packet_type] = packet

            # Update packet history (rolling buffer)
            self._packet_history.append(packet)
            if len(self._packet_history) > self.history_size:
                self._packet_history.pop(0)

            # Update health stats
            self._health["last_packet_time"] = time.time()
            self._health["packets_received"] += 1
            if packet_type not in self._health["packets_by_type"]:
                self._health["packets_by_type"][packet_type] = 0
            self._health["packets_by_type"][packet_type] += 1

        # Call user callback (outside lock to avoid blocking)
        if self._user_callback:
            try:
                await self._user_callback(packet)
            except Exception as e:
                logger.error(f"Error in user callback: {e}", exc_info=True)

    # === Latest Data API (for REST endpoints) ===

    async def get_latest_packets(self) -> dict[str, dict[str, Any] | None]:
        """
        Get latest packet of each type.

        Used by REST endpoint /telemetry/latest.
        Returns all 7 packet types with None for ones not yet received.

        Returns:
            Dictionary mapping packet type to latest packet (None if not received):
            {
                'ATT': {...} or None,
                'MOT': {...} or None,
                'STA': {...} or None,
                'CTL': {...} or None,
                'SENS': {...} or None,
                'SAFE': {...} or None,
                'PERF': {...} or None,
            }
        """
        async with self._lock.reader_lock:
            # Return all packet types, with None for ones not yet received
            return {
                'ATT': self._latest_packets.get('ATT'),
                'MOT': self._latest_packets.get('MOT'),
                'STA': self._latest_packets.get('STA'),
                'CTL': self._latest_packets.get('CTL'),
                'SENS': self._latest_packets.get('SENS'),
                'SAFE': self._latest_packets.get('SAFE'),
                'PERF': self._latest_packets.get('PERF'),
            }

    async def get_latest_packet(self, packet_type: str) -> dict[str, Any] | None:
        """
        Get latest packet of specific type.

        Args:
            packet_type: Packet type ('ATT', 'MOT', 'STA', etc.)

        Returns:
            Latest packet or None if not received yet
        """
        async with self._lock.reader_lock:
            return self._latest_packets.get(packet_type)

    async def get_latest_attitude(self) -> dict[str, Any] | None:
        """Get latest ATTITUDE packet."""
        return await self.get_latest_packet("ATT")

    async def get_latest_motors(self) -> dict[str, Any] | None:
        """Get latest MOTORS packet."""
        return await self.get_latest_packet("MOT")

    async def get_latest_status(self) -> dict[str, Any] | None:
        """Get latest STATUS packet."""
        return await self.get_latest_packet("STA")

    # === History API ===

    async def get_packet_history(
        self, packet_type: str | None = None, max_count: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Get packet history.

        Args:
            packet_type: Filter by packet type (None = all types)
            max_count: Max packets to return (None = all)

        Returns:
            List of packets (newest last)
        """
        async with self._lock.reader_lock:
            history = self._packet_history.copy()

        if packet_type:
            history = [p for p in history if p["type"] == packet_type]

        if max_count:
            history = history[-max_count:]

        return history

    # === Health Monitoring API ===

    async def get_health(self) -> dict[str, Any]:
        """
        Get bridge health status.

        Returns:
            Dictionary with:
            - is_alive: bool
            - last_packet_age_s: float (seconds since last packet)
            - packets_received: int
            - packets_by_type: dict
            - serial_stats: dict
        """
        async with self._lock.reader_lock:
            health = {
                "is_alive": self.reader.is_running(),
                "packets_received": self._health["packets_received"],
                "packets_by_type": self._health["packets_by_type"].copy(),
                "serial_stats": self.reader.get_stats(),
            }

            if self._health["last_packet_time"]:
                health["last_packet_age_s"] = time.time() - self._health["last_packet_time"]
            else:
                health["last_packet_age_s"] = None

        return health

    async def is_healthy(self, max_age_s: float = 5.0) -> bool:
        """
        Check if bridge is healthy.

        Args:
            max_age_s: Max age of last packet (default: 5.0 seconds)

        Returns:
            True if healthy (receiving recent packets)
        """
        if not self.reader.is_running():
            return False

        async with self._lock.reader_lock:
            if self._health["last_packet_time"] is None:
                return False

            age = time.time() - self._health["last_packet_time"]

        return age < max_age_s

    # === Statistics API ===

    async def get_stats(self) -> dict[str, Any]:
        """
        Get comprehensive statistics.

        Returns:
            Dictionary with bridge, reader, and parser stats
        """
        async with self._lock.reader_lock:
            return {
                "bridge": {
                    "history_size": len(self._packet_history),
                    "latest_packet_types": list(self._latest_packets.keys()),
                    **self._health,
                },
                "reader": self.reader.get_stats(),
            }

    async def reset_stats(self) -> None:
        """Reset all statistics counters."""
        async with self._lock.writer_lock:
            self._health = {
                "last_packet_time": None,
                "packets_received": 0,
                "packets_by_type": {},
            }
        self.reader.parser.reset_stats()

    # === Utility Methods ===

    @staticmethod
    def list_ports():
        """List available serial ports."""
        return list_serial_ports()

    async def __aenter__(self):
        """Async context manager enter."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
