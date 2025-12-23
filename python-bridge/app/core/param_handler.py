"""
PARAM request/response handler.

Manages parameter communication:
- Building PARAM request packets
- Parsing PARAM response packets
- Request/response matching with timeout
- Sequential request handling (one at a time)
"""

import asyncio
import logging
import struct
import time

from app.utils.crc import crc16_x25
from app.utils.protocol import (
    MAGIC_BYTE,
    PROTOCOL_VERSION,
    PacketType,
    ParamCommand,
    ParamError,
)

logger = logging.getLogger(__name__)


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


# === PARAM Handler ===


class ParamHandler:
    """
    PARAM request/response handler.

    Handles:
    - Building binary PARAM request packets
    - Parsing binary PARAM response packets
    - Request/response matching via queue
    - Timeout handling
    - Sequential request processing (lock)

    Usage:
        handler = ParamHandler(timeout=2.0)

        # Build request
        request_packet = handler.build_request(ParamCommand.GET, index=0)

        # Send via serial (done by caller)
        await serial.write(request_packet)

        # Parse response when received
        response = await handler.wait_for_response()

        # Or handle response directly
        await handler.handle_response(packet)
    """

    def __init__(self, timeout: float = 2.0):
        """
        Initialize PARAM handler.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

        # Response queue (request/response matching)
        self._response_queue: asyncio.Queue[dict] = asyncio.Queue()

        # Sequential request lock (only one request at a time)
        self._request_lock = asyncio.Lock()

        # Sequence counter
        self._seq_counter = 0

        # Statistics
        self.stats = {
            "requests_sent": 0,
            "responses_received": 0,
            "timeouts": 0,
            "crc_errors": 0,
            "last_response_time": None,
        }

    def build_request(self, command: ParamCommand, param_index: int, value: float = 0.0) -> bytes:
        """
        Build PARAM request packet.

        Packet format (18 bytes total):
        - Header (10 bytes): magic, version, type, flags, seq, timestamp_us
        - Payload (6 bytes): command, param_index, value
        - CRC (2 bytes)

        Args:
            command: PARAM command (LIST, GET, SET)
            param_index: Parameter index (0-255)
            value: Parameter value (for SET command)

        Returns:
            Binary packet ready to send over UART
        """
        # Increment sequence counter
        self._seq_counter = (self._seq_counter + 1) & 0xFFFF

        # Timestamp
        timestamp_us = int(time.time() * 1_000_000) & 0xFFFFFFFF

        # Pack header + payload (without CRC)
        packet_no_crc = struct.pack(
            "<BBBBHIBBf",  # Little-endian, NO padding
            MAGIC_BYTE,
            PROTOCOL_VERSION,
            PacketType.PARAM_REQUEST,
            0,  # flags
            self._seq_counter,
            timestamp_us,
            command,
            param_index,
            value,
        )

        # Calculate and append CRC
        crc = crc16_x25(packet_no_crc)
        packet = packet_no_crc + struct.pack("<H", crc)

        self.stats["requests_sent"] += 1

        return packet

    def parse_response(self, data: bytes) -> dict:
        """
        Parse PARAM response packet.

        Packet format (54 bytes total):
        - Header (10 bytes): magic, version, type, flags, seq, timestamp_us
        - Payload (42 bytes):
          - command: uint8 (response command code)
          - param_index: uint8
          - param_type: uint8
          - param_access: uint8
          - value: float
          - group: char[16]
          - name: char[16]
          - total_params: uint8
          - error_code: uint8
        - CRC (2 bytes)

        Args:
            data: Raw binary packet (54 bytes)

        Returns:
            Parsed response dictionary

        Raises:
            ParamCRCError: If CRC validation fails
            ValueError: If packet format is invalid
        """
        if len(data) != 54:
            raise ValueError(f"Invalid packet size: {len(data)}, expected 54")

        # Verify CRC
        crc_calc = crc16_x25(data[:-2])
        crc_received = struct.unpack("<H", data[-2:])[0]

        if crc_calc != crc_received:
            self.stats["crc_errors"] += 1
            raise ParamCRCError(f"CRC mismatch: calc={crc_calc:04x}, recv={crc_received:04x}")

        # Parse header
        magic, _version, pkt_type, _, seq, timestamp_us = struct.unpack("<BBBBHI", data[0:10])

        if magic != MAGIC_BYTE:
            raise ValueError(f"Invalid magic: 0x{magic:02x}")

        if pkt_type != PacketType.PARAM_RESPONSE:
            raise ValueError(f"Invalid packet type: 0x{pkt_type:02x}")

        # Parse payload
        (
            command,
            param_index,
            param_type,
            param_access,
            value,
            group_bytes,
            name_bytes,
            total_params,
            error_code,
        ) = struct.unpack("<BBBBf16s16sBB", data[10:52])

        # Decode strings
        group = group_bytes.decode("utf-8", errors="ignore").rstrip("\x00")
        name = name_bytes.decode("utf-8", errors="ignore").rstrip("\x00")

        self.stats["responses_received"] += 1
        self.stats["last_response_time"] = time.time()

        return {
            "seq": seq,
            "timestamp_us": timestamp_us,
            "command": command,
            "param_index": param_index,
            "param_type": param_type,
            "param_access": param_access,
            "value": value,
            "group": group,
            "name": name,
            "total_params": total_params,
            "error_code": error_code,
        }

    async def handle_response(self, response: dict) -> None:
        """
        Handle received PARAM response.

        Puts response in queue for waiting request.

        Args:
            response: Parsed response dictionary
        """
        try:
            self._response_queue.put_nowait(response)
        except asyncio.QueueFull:
            logger.warning("PARAM response queue full, dropping response")

    async def wait_for_response(self) -> dict:
        """
        Wait for PARAM response with timeout.

        Returns:
            Parsed response dictionary

        Raises:
            ParamTimeoutError: No response within timeout
        """
        try:
            response = await asyncio.wait_for(self._response_queue.get(), timeout=self.timeout)
            return response
        except TimeoutError as exc:
            self.stats["timeouts"] += 1
            raise ParamTimeoutError(f"No response within {self.timeout}s") from exc

    async def list_params(self, send_func) -> list[dict]:
        """
        List all parameters.

        Args:
            send_func: Async function to send request packet (e.g., serial.write)

        Returns:
            List of parameter info dictionaries

        Raises:
            ParamTimeoutError: Request timeout
        """
        async with self._request_lock:
            # Get total count first
            packet = self.build_request(ParamCommand.LIST, 0)
            await send_func(packet)
            response = await self.wait_for_response()

            total_params = response["total_params"]
            params = []

            # Request each parameter
            for idx in range(total_params):
                packet = self.build_request(ParamCommand.LIST, idx)
                await send_func(packet)

                try:
                    resp = await self.wait_for_response()

                    if resp["error_code"] == 0:
                        params.append(
                            {
                                "index": resp["param_index"],
                                "group": resp["group"],
                                "name": resp["name"],
                                "param_type": resp["param_type"],
                                "param_access": resp["param_access"],
                                "value": resp["value"],
                            }
                        )
                    else:
                        logger.warning(f"Error listing param {idx}: error_code={resp['error_code']}")

                except ParamTimeoutError:
                    logger.warning(f"Timeout listing param {idx}")

            logger.info(f"Listed {len(params)} parameters")
            return params

    async def get_param(self, param_index: int, send_func) -> float:
        """
        Get parameter value.

        Args:
            param_index: Parameter index (0-255)
            send_func: Async function to send request packet

        Returns:
            Parameter value

        Raises:
            ParamNotFoundError: Parameter not found
            ParamTimeoutError: Request timeout
        """
        async with self._request_lock:
            packet = self.build_request(ParamCommand.GET, param_index)
            await send_func(packet)
            response = await self.wait_for_response()

            if response["error_code"] != 0:
                if response["error_code"] == ParamError.PARAM_NOT_FOUND:
                    raise ParamNotFoundError(f"Parameter {param_index} not found")
                else:
                    raise Exception(f"Error getting param {param_index}: error_code={response['error_code']}")

            return response["value"]

    async def set_param(self, param_index: int, value: float, send_func) -> bool:
        """
        Set parameter value.

        Args:
            param_index: Parameter index (0-255)
            value: New parameter value
            send_func: Async function to send request packet

        Returns:
            True if successful

        Raises:
            ParamNotFoundError: Parameter not found
            ParamReadOnlyError: Parameter is read-only
            ParamTimeoutError: Request timeout
        """
        async with self._request_lock:
            packet = self.build_request(ParamCommand.SET, param_index, value)
            await send_func(packet)
            response = await self.wait_for_response()

            if response["error_code"] != 0:
                if response["error_code"] == ParamError.PARAM_NOT_FOUND:
                    raise ParamNotFoundError(f"Parameter {param_index} not found")
                elif response["error_code"] == ParamError.WRITE_FAILED:
                    raise ParamReadOnlyError(f"Parameter {param_index} is read-only")
                else:
                    raise Exception(f"Error setting param {param_index}: error_code={response['error_code']}")

            # Verify value
            if abs(response["value"] - value) > 0.001:
                logger.warning(f"Set param {param_index}: requested {value}, got {response['value']}")

            logger.info(f"Set param {param_index} = {response['value']}")
            return True

    def get_stats(self) -> dict:
        """Get PARAM handler statistics."""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        for key in self.stats:
            if key != "last_response_time":
                self.stats[key] = 0
        self.stats["last_response_time"] = None
