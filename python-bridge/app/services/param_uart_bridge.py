"""
PARAM UART Bridge - Binary Protocol Implementation

Implements binary communication protocol for parameter management:
- LIST: Get all parameters
- GET: Read single parameter value
- SET: Write single parameter value

Communication flow:
  Computer → UART → Controller (ESP32-C3) → ESP-NOW → Drone (ESP32-S3)
  Drone → ESP-NOW → Controller → UART → Computer

Protocol: Binary packets with CRC-16/X.25 validation
Request packet: 18 bytes
Response packet: 57 bytes

Author: Claude + Daniel
Date: 2025-12-20
"""

import asyncio
import logging
import struct
import time
from typing import Callable, Optional
from datetime import datetime

import serial
import serial.tools.list_ports

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

REQUEST_PACKET_SIZE = 20  # 12 (header with padding) + 6 (payload) + 2 (CRC)
RESPONSE_PACKET_SIZE = 57  # 12 (header with padding) + 43 (payload with padding) + 2 (CRC)


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

    Args:
        data: Bytes to calculate CRC over

    Returns:
        16-bit CRC value
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


# === PARAM UART Bridge ===


class ParamUARTBridge:
    """
    PARAM UART Bridge for drone parameter management.

    This class handles binary communication with the drone via UART:
    - Builds binary request packets
    - Sends packets to controller → drone
    - Receives and parses binary response packets
    - Validates CRC
    - Handles timeouts and auto-reconnect

    Usage:
        bridge = ParamUARTBridge()
        await bridge.connect("/dev/ttyUSB0", 115200)

        params = await bridge.list_params()
        value = await bridge.get_param(0)
        success = await bridge.set_param(0, 300.5)

        await bridge.disconnect()
    """

    def __init__(self, timeout: float = 2.0, reconnect_interval: float = 5.0):
        """
        Initialize PARAM UART bridge.

        Args:
            timeout: Request timeout in seconds (default: 2.0)
            reconnect_interval: Auto-reconnect interval in seconds (default: 5.0)
        """
        self.timeout = timeout
        self.reconnect_interval = reconnect_interval

        self.serial: Optional[serial.Serial] = None
        self.port: Optional[str] = None
        self.baudrate: int = 115200

        self.seq_counter = 0
        self.lock = asyncio.Lock()  # Thread safety - only one request at a time

        self.is_running = False
        self.reconnect_task: Optional[asyncio.Task] = None

        # Callbacks
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
        self.on_param_changed: Optional[Callable[[int, float], None]] = None

        self.last_response_time: Optional[float] = None
        self.stats = {
            'requests_sent': 0,
            'responses_received': 0,
            'timeouts': 0,
            'crc_errors': 0,
            'errors': 0,
        }

    @staticmethod
    def list_ports() -> list[str]:
        """List available serial ports."""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    async def connect(self, port: str, baudrate: int = 115200) -> bool:
        """
        Connect to UART port.

        Args:
            port: Serial port (e.g., "COM3" or "/dev/ttyUSB0")
            baudrate: Baud rate (default: 115200)

        Returns:
            True if connected successfully

        Raises:
            ParamConnectionError: If connection fails
        """
        self.port = port
        self.baudrate = baudrate

        try:
            self.serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,  # Non-blocking read with small timeout
            )

            self.is_running = True
            logger.info(f"✅ Connected to {port} @ {baudrate} baud")

            if self.on_connected:
                await self.on_connected()

            return True

        except Exception as e:
            logger.error(f"❌ Failed to connect to {port}: {e}")
            raise ParamConnectionError(f"Failed to connect to {port}: {e}")

    async def disconnect(self) -> None:
        """Disconnect from UART port."""
        self.is_running = False

        if self.reconnect_task:
            self.reconnect_task.cancel()
            try:
                await self.reconnect_task
            except asyncio.CancelledError:
                pass

        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info(f"Disconnected from {self.port}")

            if self.on_disconnected:
                await self.on_disconnected()

        self.serial = None

    def is_connected(self) -> bool:
        """Check if UART is connected."""
        return self.serial is not None and self.serial.is_open

    async def _auto_reconnect(self) -> None:
        """Auto-reconnect loop (runs in background)."""
        while self.is_running:
            await asyncio.sleep(self.reconnect_interval)

            if not self.is_connected() and self.port:
                logger.info(f"Attempting to reconnect to {self.port}...")
                try:
                    await self.connect(self.port, self.baudrate)
                except ParamConnectionError:
                    logger.warning(f"Reconnect failed, will retry in {self.reconnect_interval}s")

    def start_auto_reconnect(self) -> None:
        """Start auto-reconnect task."""
        if not self.reconnect_task or self.reconnect_task.done():
            self.reconnect_task = asyncio.create_task(self._auto_reconnect())

    def _build_request(self, command: int, param_index: int, value: float = 0.0) -> bytes:
        """
        Build PARAM request packet (18 bytes).

        Args:
            command: PARAM_CMD_LIST / GET / SET
            param_index: Parameter index (0-255)
            value: Parameter value (for SET command)

        Returns:
            18-byte binary packet
        """
        self.seq_counter = (self.seq_counter + 1) & 0xFFFF
        timestamp_us = int(time.time() * 1_000_000) & 0xFFFFFFFF

        # Pack header + payload (without CRC)
        # Note: Using padding to match firmware struct layout
        packet_no_crc = struct.pack(
            '<BBBBHxxIBBf',  # Little-endian with 2-byte padding after seq
            MAGIC_BYTE,           # magic
            PROTOCOL_VERSION,     # version
            TELEM_PARAM_REQUEST,  # type
            0,                    # flags
            self.seq_counter,     # seq (followed by 2-byte padding)
            timestamp_us,         # timestamp_us
            command,              # command
            param_index,          # param_index
            value                 # value
        )

        # Calculate and append CRC
        crc = crc16_x25(packet_no_crc)
        packet = packet_no_crc + struct.pack('<H', crc)

        return packet

    def _parse_response(self, data: bytes) -> dict:
        """
        Parse PARAM response packet (57 bytes).

        Args:
            data: 57-byte binary packet

        Returns:
            Parsed response dictionary

        Raises:
            ValueError: Invalid packet size
            ParamCRCError: CRC validation failed
        """
        if len(data) != RESPONSE_PACKET_SIZE:
            raise ValueError(f"Invalid packet size: {len(data)}, expected {RESPONSE_PACKET_SIZE}")

        # Verify CRC
        crc_calc = crc16_x25(data[:-2])
        crc_received = struct.unpack('<H', data[-2:])[0]
        if crc_calc != crc_received:
            raise ParamCRCError(f"CRC mismatch: calc={crc_calc:04x}, recv={crc_received:04x}")

        # Parse header (with 2-byte padding after seq)
        magic, version, pkt_type, flags, seq, timestamp_us = struct.unpack('<BBBBHxxI', data[0:12])

        if magic != MAGIC_BYTE:
            raise ValueError(f"Invalid magic: 0x{magic:02x}, expected 0x{MAGIC_BYTE:02x}")

        if pkt_type != TELEM_PARAM_RESPONSE:
            raise ValueError(f"Invalid packet type: 0x{pkt_type:02x}, expected 0x{TELEM_PARAM_RESPONSE:02x}")

        # Parse payload (with 1-byte padding after value)
        command, param_index, param_type, param_access, value, group_bytes, name_bytes, total_params, error_code = \
            struct.unpack('<BBBBfx16s16sBB', data[12:55])

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

    async def _send_request_and_wait_response(self, packet: bytes) -> dict:
        """
        Send request packet and wait for response.

        Args:
            packet: Binary request packet

        Returns:
            Parsed response dictionary

        Raises:
            ParamConnectionError: Not connected
            ParamTimeoutError: No response within timeout
            ParamCRCError: CRC validation failed
        """
        if not self.is_connected():
            raise ParamConnectionError("Not connected to UART")

        # Send request
        self.serial.write(packet)
        self.serial.flush()
        self.stats['requests_sent'] += 1

        # Wait for response with timeout
        buffer = bytearray()
        start_time = time.time()

        while True:
            # Check timeout
            if time.time() - start_time > self.timeout:
                self.stats['timeouts'] += 1
                raise ParamTimeoutError(f"No response within {self.timeout}s")

            # Read available data
            if self.serial.in_waiting > 0:
                chunk = self.serial.read(self.serial.in_waiting)
                buffer.extend(chunk)

                # Check if we have complete packet
                if len(buffer) >= RESPONSE_PACKET_SIZE:
                    # Try to find magic byte
                    try:
                        magic_idx = buffer.index(MAGIC_BYTE)
                    except ValueError:
                        # No magic byte, discard buffer
                        buffer.clear()
                        continue

                    # Discard bytes before magic
                    if magic_idx > 0:
                        buffer = buffer[magic_idx:]

                    # Check if we have full packet
                    if len(buffer) >= RESPONSE_PACKET_SIZE:
                        response_data = bytes(buffer[:RESPONSE_PACKET_SIZE])
                        try:
                            response = self._parse_response(response_data)
                            self.stats['responses_received'] += 1
                            self.last_response_time = time.time()
                            return response
                        except ParamCRCError as e:
                            self.stats['crc_errors'] += 1
                            logger.warning(f"CRC error: {e}")
                            # Discard this packet and keep looking
                            buffer = buffer[1:]
                        except ValueError as e:
                            logger.warning(f"Parse error: {e}")
                            # Discard this packet and keep looking
                            buffer = buffer[1:]

            # Small delay to avoid busy-waiting
            await asyncio.sleep(0.01)

    async def list_params(self) -> list[dict]:
        """
        List all parameters.

        Returns:
            List of parameter dictionaries with keys:
            - index: int
            - group: str
            - name: str
            - param_type: int
            - param_access: int (0=readonly, 1=readwrite)
            - value: float

        Raises:
            ParamConnectionError: Not connected
            ParamTimeoutError: Timeout waiting for response
        """
        async with self.lock:
            # Send LIST request for index 0 to get total_params count
            packet = self._build_request(PARAM_CMD_LIST, 0)
            response = await self._send_request_and_wait_response(packet)

            total_params = response['total_params']
            params = []

            # Request each parameter
            for idx in range(total_params):
                packet = self._build_request(PARAM_CMD_LIST, idx)
                try:
                    resp = await self._send_request_and_wait_response(packet)

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

        Raises:
            ParamConnectionError: Not connected
            ParamTimeoutError: Timeout waiting for response
            ParamNotFoundError: Parameter not found
        """
        async with self.lock:
            packet = self._build_request(PARAM_CMD_GET, param_index)
            response = await self._send_request_and_wait_response(packet)

            if response['error_code'] != 0:
                if response['error_code'] == ERROR_PARAM_NOT_FOUND:
                    raise ParamNotFoundError(f"Parameter {param_index} not found")
                else:
                    self.stats['errors'] += 1
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

        Raises:
            ParamConnectionError: Not connected
            ParamTimeoutError: Timeout waiting for response
            ParamNotFoundError: Parameter not found
            ParamReadOnlyError: Parameter is read-only
        """
        async with self.lock:
            packet = self._build_request(PARAM_CMD_SET, param_index, value)
            response = await self._send_request_and_wait_response(packet)

            if response['error_code'] != 0:
                if response['error_code'] == ERROR_PARAM_NOT_FOUND:
                    raise ParamNotFoundError(f"Parameter {param_index} not found")
                elif response['error_code'] == ERROR_WRITE_FAILED:
                    raise ParamReadOnlyError(f"Parameter {param_index} is read-only")
                else:
                    self.stats['errors'] += 1
                    raise Exception(f"Error setting param {param_index}: error_code={response['error_code']}")

            # Verify value was set correctly
            if abs(response['value'] - value) > 0.001:
                logger.warning(f"Set param {param_index}: requested {value}, got {response['value']}")

            # Callback
            if self.on_param_changed:
                await self.on_param_changed(param_index, response['value'])

            logger.info(f"Set param {param_index} = {response['value']}")
            return True

    def get_stats(self) -> dict:
        """
        Get statistics.

        Returns:
            Dictionary with keys:
            - requests_sent: int
            - responses_received: int
            - timeouts: int
            - crc_errors: int
            - errors: int
            - last_response_time: float | None
        """
        return {
            **self.stats,
            'last_response_time': self.last_response_time,
        }

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        for key in self.stats:
            self.stats[key] = 0
        self.last_response_time = None


# === Smoke Test ===

async def _smoke_test():
    """Smoke test for ParamUARTBridge."""
    import sys

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # List available ports
    ports = ParamUARTBridge.list_ports()
    print(f"Available ports: {ports}")

    if not ports:
        print("❌ No serial ports found")
        return

    # Use first port for testing (or specify manually)
    port = ports[0] if len(sys.argv) < 2 else sys.argv[1]
    print(f"Testing with port: {port}")

    bridge = ParamUARTBridge(timeout=2.0)

    try:
        # Connect
        await bridge.connect(port, 115200)

        # List all params
        print("\n=== LIST ALL PARAMS ===")
        params = await bridge.list_params()
        for p in params:
            access = "rw" if p['param_access'] == 1 else "ro"
            print(f"  [{p['index']}] {p['group']}.{p['name']} = {p['value']} ({access})")

        if params:
            # Get first param
            print(f"\n=== GET PARAM 0 ===")
            value = await bridge.get_param(0)
            print(f"  Value: {value}")

            # Set first param (if readwrite)
            if params[0]['param_access'] == 1:
                print(f"\n=== SET PARAM 0 = 300.5 ===")
                await bridge.set_param(0, 300.5)

                # Verify
                value = await bridge.get_param(0)
                print(f"  New value: {value}")

        # Stats
        print(f"\n=== STATS ===")
        stats = bridge.get_stats()
        for key, val in stats.items():
            print(f"  {key}: {val}")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await bridge.disconnect()


if __name__ == '__main__':
    asyncio.run(_smoke_test())
