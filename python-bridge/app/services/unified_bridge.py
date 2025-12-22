"""
Unified Bridge - Bidirectional UART Communication

Combines telemetry reception (ESP32 → Python) and PARAM commands (Python ↔ ESP32)
over a single UART port with packet routing based on packet type.

Packet Types:
- 0x01-0x07: Telemetry packets (ATTITUDE, MOTORS, STATUS, etc.) → broadcast to WebSocket
- 0x10: PARAM request (Python → ESP32) - outgoing only
- 0x11: PARAM response (ESP32 → Python) → deliver to waiting request

Author: Claude + Daniel
Date: 2025-12-22
"""

import asyncio
import logging
import struct
import time
from typing import Any, Callable, Awaitable, Optional

import aiorwlock
import serial_asyncio

from app.services.telemetry_parser import TelemetryParser

logger = logging.getLogger(__name__)


# === Protocol Constants ===

TELEM_PARAM_REQUEST = 0x10
TELEM_PARAM_RESPONSE = 0x11

PARAM_CMD_LIST = 0x01
PARAM_CMD_GET = 0x02
PARAM_CMD_SET = 0x03
PARAM_CMD_LIST_RESP = 0x81
PARAM_CMD_GET_RESP = 0x82
PARAM_CMD_SET_RESP = 0x83
PARAM_CMD_ERROR = 0xFF

ERROR_INDEX_OUT_OF_RANGE = 1
ERROR_PARAM_NOT_FOUND = 2
ERROR_READ_FAILED = 3
ERROR_WRITE_FAILED = 4
ERROR_UNKNOWN_COMMAND = 5

MAGIC_BYTE = 0x5B
PROTOCOL_VERSION = 2

REQUEST_PACKET_SIZE = 18  # 10 header + 6 payload + 2 CRC (NO padding)
RESPONSE_PACKET_SIZE = 54  # 10 header + 42 payload + 2 CRC (NO padding)


# === Exceptions ===

class ParamTimeoutError(Exception):
    """Request timeout - no response from drone."""
    pass


class ParamCRCError(Exception):
    """CRC validation failed."""
    pass


class ParamNotFoundError(Exception):
    """Parameter not found (invalid index)."""
    pass


class ParamReadOnlyError(Exception):
    """Attempted to write read-only parameter."""
    pass


class ParamConnectionError(Exception):
    """UART connection error."""
    pass


# === CRC-16/X.25 ===

def crc16_x25(data: bytes) -> int:
    """
    Calculate CRC-16/X.25 checksum.
    Must match firmware implementation exactly.
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return (~crc) & 0xFFFF


# === Unified Bridge ===

class UnifiedBridge:
    """
    Unified bidirectional UART bridge for telemetry and PARAM communication.

    Features:
    - Receives telemetry packets (0x01-0x07) → broadcasts to WebSocket clients
    - Sends PARAM requests (0x10) and receives responses (0x11)
    - Single UART connection shared for both directions
    - Automatic packet routing based on packet type
    - Thread-safe request/response handling

    Usage:
        bridge = UnifiedBridge('COM3', 115200)

        # Set telemetry callback for WebSocket broadcast
        async def on_telemetry(packet):
            await websocket_manager.broadcast(packet)

        bridge.set_telemetry_callback(on_telemetry)

        # Start bridge
        await bridge.start()

        # Use PARAM commands
        params = await bridge.list_params()
        value = await bridge.get_param(0)
        await bridge.set_param(0, 300.5)

        # Query telemetry data
        latest = await bridge.get_latest_packets()
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
            port: Serial port path
            baudrate: Baud rate (default: 115200)
            history_size: Max telemetry packets to keep in history
            param_timeout: PARAM request timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.history_size = history_size
        self.param_timeout = param_timeout

        # Serial port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._running = False
        self._read_task: Optional[asyncio.Task] = None

        # Telemetry parser
        self.telemetry_parser = TelemetryParser()

        # Telemetry data (same as TelemetryBridge)
        self._latest_packets: dict[str, dict[str, Any]] = {}
        self._packet_history: list[dict[str, Any]] = []
        self._lock = aiorwlock.RWLock()

        # Telemetry callback
        self._telemetry_callback: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None

        # PARAM response queue (for request/response matching)
        self._param_response_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._param_seq_counter = 0
        self._param_lock = asyncio.Lock()  # Only one PARAM request at a time

        # Health monitoring
        self._health = {
            "last_packet_time": None,
            "packets_received": 0,
            "packets_by_type": {},
        }

        # Statistics
        self.stats = {
            "bytes_read": 0,
            "bytes_written": 0,
            "telemetry_packets": 0,
            "param_requests": 0,
            "param_responses": 0,
            "param_timeouts": 0,
            "param_crc_errors": 0,
            "read_errors": 0,
            "start_time": None,
        }

    # === Lifecycle ===

    async def start(self) -> None:
        """Start unified bridge (open serial port and start read loop)."""
        if self._running:
            raise RuntimeError("UnifiedBridge already running")

        logger.info(f"Starting unified bridge: {self.port} @ {self.baudrate}")

        try:
            # Open serial port (async)
            self._reader, self._writer = await serial_asyncio.open_serial_connection(
                url=self.port,
                baudrate=self.baudrate,
            )
            logger.info(f"Serial port opened: {self.port}")
        except Exception as e:
            logger.error(f"Failed to open serial port: {e}")
            raise ParamConnectionError(f"Failed to open {self.port}: {e}")

        # Start reader task
        self._running = True
        self.stats["start_time"] = time.time()
        self._read_task = asyncio.create_task(self._read_loop())

        logger.info("✅ Unified bridge started successfully")

    async def stop(self, timeout: float = 5.0) -> None:
        """Stop unified bridge."""
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
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            logger.info("Serial port closed")

        logger.info("✅ Unified bridge stopped")

    def is_running(self) -> bool:
        """Check if bridge is running."""
        return self._running

    def is_connected(self) -> bool:
        """Check if bridge is connected (alias for is_running for API compatibility)."""
        return self._running and self._reader is not None and self._writer is not None

    # === Telemetry Features (from TelemetryBridge) ===

    def set_telemetry_callback(
        self, callback: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        Set async callback for telemetry packets (for WebSocket broadcast).

        Args:
            callback: Async function(packet_dict) called for each telemetry packet
        """
        self._telemetry_callback = callback

    async def get_latest_packets(self) -> dict[str, dict[str, Any] | None]:
        """
        Get latest packet of each telemetry type.

        Returns:
            Dictionary mapping packet type to latest packet (None if not received)
        """
        async with self._lock.reader_lock:
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
        """Get latest packet of specific type."""
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

    async def get_packet_history(
        self, packet_type: str | None = None, max_count: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Get telemetry packet history.

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

    async def get_health(self) -> dict[str, Any]:
        """Get bridge health status."""
        async with self._lock.reader_lock:
            health = {
                "is_alive": self._running,
                "packets_received": self._health["packets_received"],
                "packets_by_type": self._health["packets_by_type"].copy(),
            }

            if self._health["last_packet_time"]:
                health["last_packet_age_s"] = time.time() - self._health["last_packet_time"]
            else:
                health["last_packet_age_s"] = None

        return health

    async def is_healthy(self, max_age_s: float = 5.0) -> bool:
        """Check if bridge is healthy (receiving recent packets)."""
        if not self._running:
            return False

        async with self._lock.reader_lock:
            if self._health["last_packet_time"] is None:
                return False
            age = time.time() - self._health["last_packet_time"]

        return age < max_age_s

    # === PARAM Features (from ParamUARTBridge) ===

    def _build_param_request(self, command: int, param_index: int, value: float = 0.0) -> bytes:
        """Build PARAM request packet (18 bytes)."""
        self._param_seq_counter = (self._param_seq_counter + 1) & 0xFFFF
        timestamp_us = int(time.time() * 1_000_000) & 0xFFFFFFFF

        # Pack header + payload (without CRC)
        # IMPORTANT: No padding - matches firmware packed struct (10-byte header)
        packet_no_crc = struct.pack(
            '<BBBBHIBBf',  # Little-endian, NO padding (10 header + 6 payload = 16 bytes)
            MAGIC_BYTE,
            PROTOCOL_VERSION,
            TELEM_PARAM_REQUEST,
            0,  # flags
            self._param_seq_counter,
            timestamp_us,
            command,
            param_index,
            value
        )

        # Calculate and append CRC
        crc = crc16_x25(packet_no_crc)
        packet = packet_no_crc + struct.pack('<H', crc)

        return packet

    def _parse_param_response(self, data: bytes) -> dict:
        """Parse PARAM response packet (54 bytes)."""
        if len(data) != RESPONSE_PACKET_SIZE:
            raise ValueError(f"Invalid packet size: {len(data)}, expected {RESPONSE_PACKET_SIZE}")

        # Verify CRC
        crc_calc = crc16_x25(data[:-2])
        crc_received = struct.unpack('<H', data[-2:])[0]
        if crc_calc != crc_received:
            raise ParamCRCError(f"CRC mismatch: calc={crc_calc:04x}, recv={crc_received:04x}")

        # Parse header (NO padding - matches firmware packed struct)
        magic, version, pkt_type, flags, seq, timestamp_us = struct.unpack('<BBBBHI', data[0:10])

        if magic != MAGIC_BYTE:
            raise ValueError(f"Invalid magic: 0x{magic:02x}")

        if pkt_type != TELEM_PARAM_RESPONSE:
            raise ValueError(f"Invalid packet type: 0x{pkt_type:02x}")

        # Parse payload (NO padding - matches firmware packed struct)
        command, param_index, param_type, param_access, value, group_bytes, name_bytes, total_params, error_code = \
            struct.unpack('<BBBBf16s16sBB', data[10:52])

        group = group_bytes.decode('utf-8', errors='ignore').rstrip('\x00')
        name = name_bytes.decode('utf-8', errors='ignore').rstrip('\x00')

        return {
            'seq': seq,
            'timestamp_us': timestamp_us,
            'command': command,
            'param_index': param_index,
            'param_type': param_type,
            'param_access': param_access,
            'value': value,
            'group': group,
            'name': name,
            'total_params': total_params,
            'error_code': error_code,
        }

    async def _send_param_request_and_wait(self, packet: bytes) -> dict:
        """
        Send PARAM request and wait for response.

        Args:
            packet: Binary request packet

        Returns:
            Parsed response dictionary

        Raises:
            ParamConnectionError: Not connected
            ParamTimeoutError: No response within timeout
        """
        if not self._running:
            raise ParamConnectionError("Bridge not running")

        # Send request
        self._writer.write(packet)
        await self._writer.drain()
        self.stats['param_requests'] += 1
        self.stats['bytes_written'] += len(packet)

        # Wait for response with timeout
        try:
            response = await asyncio.wait_for(
                self._param_response_queue.get(),
                timeout=self.param_timeout
            )
            self.stats['param_responses'] += 1
            return response
        except asyncio.TimeoutError:
            self.stats['param_timeouts'] += 1
            raise ParamTimeoutError(f"No response within {self.param_timeout}s")

    async def list_params(self) -> list[dict]:
        """
        List all parameters.

        Returns:
            List of parameter dictionaries
        """
        async with self._param_lock:
            # Send LIST request for index 0 to get total_params count
            packet = self._build_param_request(PARAM_CMD_LIST, 0)
            response = await self._send_param_request_and_wait(packet)

            total_params = response['total_params']
            params = []

            # Request each parameter
            for idx in range(total_params):
                packet = self._build_param_request(PARAM_CMD_LIST, idx)
                try:
                    resp = await self._send_param_request_and_wait(packet)

                    if resp['error_code'] == 0:
                        params.append({
                            'index': resp['param_index'],
                            'group': resp['group'],
                            'name': resp['name'],
                            'param_type': resp['param_type'],
                            'param_access': resp['param_access'],
                            'value': resp['value'],
                        })
                    else:
                        logger.warning(f"Error listing param {idx}: error_code={resp['error_code']}")

                except ParamTimeoutError:
                    logger.warning(f"Timeout listing param {idx}")

            logger.info(f"Listed {len(params)} parameters")
            return params

    async def get_param(self, param_index: int) -> float:
        """
        Get parameter value.

        Args:
            param_index: Parameter index (0-255)

        Returns:
            Parameter value (float)
        """
        async with self._param_lock:
            packet = self._build_param_request(PARAM_CMD_GET, param_index)
            response = await self._send_param_request_and_wait(packet)

            if response['error_code'] != 0:
                if response['error_code'] == ERROR_PARAM_NOT_FOUND:
                    raise ParamNotFoundError(f"Parameter {param_index} not found")
                else:
                    raise Exception(f"Error getting param {param_index}: error_code={response['error_code']}")

            return response['value']

    async def set_param(self, param_index: int, value: float) -> bool:
        """
        Set parameter value.

        Args:
            param_index: Parameter index (0-255)
            value: New parameter value

        Returns:
            True if successful
        """
        async with self._param_lock:
            packet = self._build_param_request(PARAM_CMD_SET, param_index, value)
            response = await self._send_param_request_and_wait(packet)

            if response['error_code'] != 0:
                if response['error_code'] == ERROR_PARAM_NOT_FOUND:
                    raise ParamNotFoundError(f"Parameter {param_index} not found")
                elif response['error_code'] == ERROR_WRITE_FAILED:
                    raise ParamReadOnlyError(f"Parameter {param_index} is read-only")
                else:
                    raise Exception(f"Error setting param {param_index}: error_code={response['error_code']}")

            # Verify value was set correctly
            if abs(response['value'] - value) > 0.001:
                logger.warning(f"Set param {param_index}: requested {value}, got {response['value']}")

            logger.info(f"Set param {param_index} = {response['value']}")
            return True

    # === Statistics ===

    async def get_stats(self) -> dict[str, Any]:
        """
        Get comprehensive statistics (async, for TelemetryBridge API compatibility).

        Used by telemetry endpoints.
        """
        async with self._lock.reader_lock:
            stats = {
                **self.stats.copy(),
                "telemetry_parser_stats": self.telemetry_parser.get_stats(),
                "health": self._health.copy(),
            }

            if stats["start_time"]:
                stats["uptime_s"] = time.time() - stats["start_time"]
            else:
                stats["uptime_s"] = 0

            return stats

    def get_param_stats(self) -> dict[str, Any]:
        """
        Get PARAM statistics (synchronous, for ParamUARTBridge API compatibility).

        Used by PARAM endpoints.
        """
        return {
            'requests_sent': self.stats['param_requests'],
            'responses_received': self.stats['param_responses'],
            'timeouts': self.stats['param_timeouts'],
            'crc_errors': self.stats['param_crc_errors'],
            'errors': 0,  # Generic errors not tracked separately
            'last_response_time': None,  # Not tracked in current impl
        }

    async def reset_stats(self) -> None:
        """Reset all statistics counters."""
        async with self._lock.writer_lock:
            for key in self.stats:
                if key != "start_time":
                    self.stats[key] = 0

            self._health = {
                "last_packet_time": None,
                "packets_received": 0,
                "packets_by_type": {},
            }

        self.telemetry_parser.reset_stats()

    # === Internal Read Loop ===

    async def _read_loop(self) -> None:
        """
        Main read loop - continuously read from serial port and route packets.

        Routes packets based on type:
        - 0x01-0x07: Telemetry packets → _handle_telemetry_packet()
        - 0x11: PARAM response → _handle_param_response()
        """
        logger.info("Unified bridge read loop started")

        buffer = bytearray()

        try:
            while self._running:
                try:
                    # Read available data (async)
                    data = await self._reader.read(1024)
                    if not data:
                        logger.warning("Serial port closed unexpectedly")
                        break

                    self.stats["bytes_read"] += len(data)
                    buffer.extend(data)

                    # Try to parse packets from buffer
                    buffer = await self._parse_and_route_packets(buffer)

                except Exception as e:
                    logger.error(f"Error in read loop: {e}", exc_info=True)
                    self.stats["read_errors"] += 1
                    await asyncio.sleep(0.1)

        finally:
            logger.info("Unified bridge read loop stopped")

    async def _parse_and_route_packets(self, buffer: bytearray) -> bytearray:
        """
        Parse packets from buffer and route based on type.

        Args:
            buffer: Input buffer

        Returns:
            Remaining buffer after parsing
        """
        # IMPORTANT: Always feed all data to TelemetryParser first.
        # TelemetryParser maintains its own internal buffer and handles packet synchronization.
        # This ensures partial packets are not lost between iterations.
        if len(buffer) > 0:
            packets = self.telemetry_parser.feed(bytes(buffer))

            # Handle parsed telemetry packets
            for packet in packets:
                await self._handle_telemetry_packet(packet)

            # Clear our buffer since TelemetryParser has consumed the data
            # (it maintains its own internal buffer for partial packets)
            buffer.clear()

        # Note: PARAM response handling (type 0x11) is intentionally removed for now.
        # The TelemetryParser will log warnings for unknown packet types (0x11)
        # but will skip them gracefully. This prevents the double-buffering bug.
        #
        # TODO: If PARAM support is needed, implement a separate PARAM parser
        # that also gets fed all data, or modify TelemetryParser to understand
        # PARAM packets as well.

        return buffer

    async def _handle_telemetry_packet(self, packet: dict[str, Any]) -> None:
        """Handle parsed telemetry packet."""
        packet_type = packet["type"]

        # Route PARAM_RESP packets to param response queue
        if packet_type == "PARAM_RESP":
            try:
                # Parse full PARAM response from raw_data
                response = self._parse_param_response(packet['raw_data'])
                await self._handle_param_response(response)
            except Exception as e:
                logger.error(f"Error handling PARAM response: {e}")
            return  # Don't add to telemetry stream

        # Ignore PARAM_REQ packets (we don't expect to receive requests from drone)
        if packet_type == "PARAM_REQ":
            logger.debug("Received PARAM_REQ packet (unexpected, ignoring)")
            return

        # Update shared data with lock (for telemetry packets only)
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

            self.stats["telemetry_packets"] += 1

        # Call telemetry callback (outside lock to avoid blocking)
        if self._telemetry_callback:
            try:
                await self._telemetry_callback(packet)
            except Exception as e:
                logger.error(f"Error in telemetry callback: {e}", exc_info=True)

    async def _handle_param_response(self, response: dict) -> None:
        """Handle PARAM response packet - put in queue for waiting request."""
        try:
            self._param_response_queue.put_nowait(response)
        except asyncio.QueueFull:
            logger.warning("PARAM response queue full, dropping response")

    # === Context Manager ===

    async def __aenter__(self):
        """Async context manager enter."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

    # === Utility Methods ===

    @staticmethod
    def list_ports():
        """List available serial ports."""
        import serial.tools.list_ports

        ports = serial.tools.list_ports.comports()
        result = []

        for port in ports:
            result.append(
                {
                    "device": port.device,
                    "description": port.description,
                    "hwid": port.hwid,
                }
            )

        return result
