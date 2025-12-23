"""
Unified Bridge - Bidirectional UART Communication

Orchestrates single UART connection with bidirectional communication:
- Telemetry reception (ESP32 TX → Python) - 7 packet types
- PARAM requests/responses (Python ↔ ESP32 TX)

Packet routing:
- Type 0x01-0x07: Telemetry → broadcast callback
- Type 0x11: PARAM response → request handler
- Type 0x10: PARAM request → send (not receive)

Architecture:
- Uses composition for modularity
- Each component has single responsibility
- Async I/O throughout
"""

import asyncio
import logging
from typing import Any, Callable, Awaitable, Optional

from app.core.health_monitor import HealthMonitor
from app.core.packet_router import PacketRouter, RouteDestination
from app.core.param_handler import (
    ParamHandler,
)
from app.core.serial_connection import SerialConnection, SerialConnectionError
from app.core.telemetry_store import TelemetryStore
from app.services.telemetry_parser import TelemetryParser

logger = logging.getLogger(__name__)


class UnifiedBridge:
    """
    Unified bidirectional UART bridge for telemetry and PARAM communication.

    This is the main coordinator that orchestrates:
    - Serial I/O (SerialConnection)
    - Packet parsing (TelemetryParser)
    - Packet routing (PacketRouter)
    - Telemetry storage (TelemetryStore)
    - PARAM handling (ParamHandler)
    - Health monitoring (HealthMonitor)

    Usage:
        bridge = UnifiedBridge('COM3', 115200)

        # Set telemetry callback for real-time broadcast
        async def on_telemetry(packet):
            print(f"Telemetry: {packet['type']}")

        bridge.set_telemetry_callback(on_telemetry)

        # Start bridge
        await bridge.start()

        # Use PARAM commands
        params = await bridge.list_params()
        value = await bridge.get_param(0)
        await bridge.set_param(0, 300.5)

        # Query telemetry data
        latest = await bridge.get_latest_attitude()
        history = await bridge.get_packet_history('MOT')
        health = await bridge.get_health()

        # Stop bridge
        await bridge.stop()
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        history_size: int = 1000,
        param_timeout: float = 2.0,
    ):
        """
        Initialize unified bridge.

        Args:
            port: Serial port path (e.g., 'COM3' or '/dev/ttyUSB0')
            baudrate: Baud rate (default: 115200)
            history_size: Max telemetry packets to keep in history
            param_timeout: PARAM request timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate

        # Components (composition)
        self.serial = SerialConnection(port, baudrate)
        self.parser = TelemetryParser()
        self.router = PacketRouter()
        self.telemetry = TelemetryStore(history_size)
        self.param = ParamHandler(param_timeout)
        self.health = HealthMonitor()

        # Telemetry callback (for real-time broadcast)
        self._telemetry_callback: Optional[
            Callable[[dict[str, Any]], Awaitable[None]]
        ] = None

        # Read loop task
        self._read_task: Optional[asyncio.Task] = None
        self._running = False

    # === Lifecycle ===

    async def start(self) -> None:
        """
        Start unified bridge.

        Opens serial port and starts read loop.

        Raises:
            RuntimeError: If already running
            SerialConnectionError: If port cannot be opened
        """
        if self._running:
            raise RuntimeError("UnifiedBridge already running")

        logger.info(f"Starting unified bridge: {self.port} @ {self.baudrate}")

        # Open serial connection
        await self.serial.open()

        # Start read loop
        self._running = True
        self._read_task = asyncio.create_task(self._read_loop())

        logger.info("✅ Unified bridge started successfully")

    async def stop(self, timeout: float = 5.0) -> None:
        """
        Stop unified bridge.

        Stops read loop and closes serial port.

        Args:
            timeout: Max time to wait for clean shutdown (seconds)
        """
        if not self._running:
            return

        logger.info("Stopping unified bridge...")
        self._running = False

        # Stop read task
        if self._read_task:
            try:
                await asyncio.wait_for(self._read_task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Read task did not stop cleanly, cancelling...")
                self._read_task.cancel()
                try:
                    await self._read_task
                except asyncio.CancelledError:
                    pass
            self._read_task = None

        # Close serial port
        await self.serial.close()

        logger.info("✅ Unified bridge stopped")

    def is_running(self) -> bool:
        """Check if bridge is running."""
        return self._running

    def is_connected(self) -> bool:
        """Check if bridge is connected (serial port open)."""
        return self.serial.is_open()

    # === Telemetry Features ===

    def set_telemetry_callback(
        self, callback: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        Set async callback for telemetry packets.

        Callback is called for each telemetry packet (ATT, MOT, STA, etc.)
        immediately after it's stored. Use for real-time broadcasting.

        Args:
            callback: Async function(packet_dict) to call for each packet
        """
        self._telemetry_callback = callback

    async def get_latest_packets(self) -> dict[str, Optional[dict[str, Any]]]:
        """
        Get latest packet of each telemetry type.

        Returns:
            Dictionary mapping packet type to latest packet (None if not received)
        """
        return await self.telemetry.get_all_latest()

    async def get_latest_packet(self, packet_type: str) -> Optional[dict[str, Any]]:
        """Get latest packet of specific type."""
        return await self.telemetry.get_latest(packet_type)

    async def get_latest_attitude(self) -> Optional[dict[str, Any]]:
        """Get latest ATTITUDE packet."""
        return await self.telemetry.get_latest("ATT")

    async def get_latest_motors(self) -> Optional[dict[str, Any]]:
        """Get latest MOTORS packet."""
        return await self.telemetry.get_latest("MOT")

    async def get_latest_status(self) -> Optional[dict[str, Any]]:
        """Get latest STATUS packet."""
        return await self.telemetry.get_latest("STA")

    async def get_packet_history(
        self, packet_type: Optional[str] = None, max_count: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """
        Get telemetry packet history.

        Args:
            packet_type: Filter by packet type (None = all types)
            max_count: Max packets to return (None = all)

        Returns:
            List of packets (newest last)
        """
        return await self.telemetry.get_history(packet_type, max_count)

    async def get_health(self) -> dict[str, Any]:
        """Get bridge health status."""
        telemetry_health = await self.telemetry.get_health()

        return {
            "is_alive": self._running,
            "packets_received": telemetry_health["packets_received"],
            "packets_by_type": telemetry_health["packets_by_type"],
            "last_packet_age_s": telemetry_health["last_packet_age_s"],
        }

    async def is_healthy(self, max_age_s: float = 5.0) -> bool:
        """Check if bridge is healthy (receiving recent packets)."""
        if not self._running:
            return False

        return await self.telemetry.is_healthy(max_age_s)

    # === PARAM Features ===

    async def list_params(self) -> list[dict]:
        """
        List all parameters.

        Returns:
            List of parameter dictionaries with index, group, name, type, access, value

        Raises:
            SerialConnectionError: Not connected
            ParamTimeoutError: Request timeout
        """
        return await self.param.list_params(self._send_param_request)

    async def get_param(self, param_index: int) -> float:
        """
        Get parameter value.

        Args:
            param_index: Parameter index (0-255)

        Returns:
            Parameter value (float)

        Raises:
            ParamNotFoundError: Parameter not found
            ParamTimeoutError: Request timeout
        """
        return await self.param.get_param(param_index, self._send_param_request)

    async def set_param(self, param_index: int, value: float) -> bool:
        """
        Set parameter value.

        Args:
            param_index: Parameter index (0-255)
            value: New parameter value

        Returns:
            True if successful

        Raises:
            ParamNotFoundError: Parameter not found
            ParamReadOnlyError: Parameter is read-only
            ParamTimeoutError: Request timeout
        """
        return await self.param.set_param(param_index, value, self._send_param_request)

    async def _send_param_request(self, packet: bytes) -> None:
        """
        Send PARAM request packet over serial.

        Args:
            packet: Binary request packet
        """
        await self.serial.write(packet)
        self.health.record_bytes_written(len(packet))
        self.health.record_param_request()

    # === Statistics ===

    async def get_stats(self) -> dict[str, Any]:
        """
        Get comprehensive statistics.

        Returns:
            Dictionary with all component stats
        """
        return {
            "health": self.health.get_stats(),
            "parser": self.parser.get_stats(),
            "router": self.router.get_stats(),
            "telemetry": self.telemetry.get_stats(),
            "param": self.param.get_stats(),
        }

    def get_param_stats(self) -> dict[str, Any]:
        """Get PARAM statistics (for API compatibility)."""
        return self.param.get_stats()

    async def reset_stats(self) -> None:
        """Reset all statistics counters."""
        self.health.reset()
        self.parser.reset_stats()
        self.router.reset_stats()
        # Telemetry store doesn't have reset_stats (would need lock)
        self.param.reset_stats()

    # === Internal Read Loop ===

    async def _read_loop(self) -> None:
        """
        Main read loop - continuously read from serial and route packets.

        Routes packets based on type:
        - Telemetry (ATT, MOT, STA, etc.) → store + callback
        - PARAM response → param handler
        """
        logger.info("Unified bridge read loop started")

        try:
            while self._running:
                try:
                    # Read from serial
                    data = await self.serial.read(1024)
                    self.health.record_bytes_read(len(data))

                    # Parse packets
                    packets = self.parser.feed(data)

                    # Route each packet
                    for packet in packets:
                        await self._route_packet(packet)

                except SerialConnectionError as e:
                    logger.error(f"Serial error in read loop: {e}")
                    self.health.record_read_error()
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Error in read loop: {e}", exc_info=True)
                    self.health.record_read_error()
                    await asyncio.sleep(0.1)

        finally:
            logger.info("Unified bridge read loop stopped")

    async def _route_packet(self, packet: dict[str, Any]) -> None:
        """
        Route packet to appropriate handler.

        Args:
            packet: Parsed packet dictionary
        """
        destination = self.router.route(packet)

        if destination == RouteDestination.TELEMETRY:
            await self._handle_telemetry(packet)

        elif destination == RouteDestination.PARAM_RESPONSE:
            await self._handle_param_response(packet)

        else:
            # Unknown packet type
            logger.debug(f"Unknown packet destination: {packet.get('type')}")

    async def _handle_telemetry(self, packet: dict[str, Any]) -> None:
        """
        Handle telemetry packet.

        Stores packet and calls callback if set.

        Args:
            packet: Telemetry packet
        """
        # Store packet
        await self.telemetry.add(packet)
        self.health.record_telemetry_packet()

        # Call callback (outside lock for performance)
        if self._telemetry_callback:
            try:
                await self._telemetry_callback(packet)
            except Exception as e:
                logger.error(f"Error in telemetry callback: {e}", exc_info=True)

    async def _handle_param_response(self, packet: dict[str, Any]) -> None:
        """
        Handle PARAM response packet.

        Parses response and puts in handler queue.

        Args:
            packet: PARAM response packet (with 'raw_data')
        """
        try:
            # Parse PARAM response from raw_data
            response = self.param.parse_response(packet["raw_data"])
            await self.param.handle_response(response)
            self.health.record_param_response()

        except Exception as e:
            logger.error(f"Error handling PARAM response: {e}")

    # === Context Manager ===

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

    # === Utility Methods ===

    @staticmethod
    def list_ports():
        """List available serial ports."""
        return SerialConnection.list_ports()
