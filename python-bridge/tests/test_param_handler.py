"""
Tests for ParamHandler - PARAM request/response handling.
"""

import asyncio
import struct
import time
from unittest.mock import AsyncMock

import pytest

from app.core.param_handler import (
    ParamCRCError,
    ParamHandler,
    ParamNotFoundError,
    ParamReadOnlyError,
    ParamTimeoutError,
)
from app.utils.crc import crc16_x25
from app.utils.protocol import MAGIC_BYTE, PROTOCOL_VERSION, PacketType, ParamCommand, ParamError


class TestBuildRequest:
    """Test PARAM request packet building."""

    def test_build_list_request(self):
        """Test building LIST request."""
        handler = ParamHandler()
        packet = handler.build_request(ParamCommand.LIST, 0)

        # Verify packet size (10 header + 6 payload + 2 CRC = 18 bytes)
        assert len(packet) == 18

        # Parse and verify
        magic, version, pkt_type, flags, seq, timestamp_us = struct.unpack("<BBBBHI", packet[0:10])
        command, param_index, value = struct.unpack("<BBf", packet[10:16])
        crc = struct.unpack("<H", packet[16:18])[0]

        assert magic == MAGIC_BYTE
        assert version == PROTOCOL_VERSION
        assert pkt_type == PacketType.PARAM_REQUEST
        assert flags == 0
        assert seq == 1  # First request
        assert command == ParamCommand.LIST
        assert param_index == 0
        assert value == 0.0

        # Verify CRC
        crc_calc = crc16_x25(packet[:-2])
        assert crc == crc_calc

    def test_build_get_request(self):
        """Test building GET request."""
        handler = ParamHandler()
        packet = handler.build_request(ParamCommand.GET, 5)

        command, param_index, value = struct.unpack("<BBf", packet[10:16])
        assert command == ParamCommand.GET
        assert param_index == 5
        assert value == 0.0

    def test_build_set_request(self):
        """Test building SET request."""
        handler = ParamHandler()
        packet = handler.build_request(ParamCommand.SET, 10, 123.456)

        command, param_index, value = struct.unpack("<BBf", packet[10:16])
        assert command == ParamCommand.SET
        assert param_index == 10
        assert abs(value - 123.456) < 0.001

    def test_sequence_counter_increments(self):
        """Test sequence counter increments."""
        handler = ParamHandler()

        packet1 = handler.build_request(ParamCommand.GET, 0)
        packet2 = handler.build_request(ParamCommand.GET, 1)
        packet3 = handler.build_request(ParamCommand.GET, 2)

        seq1 = struct.unpack("<H", packet1[4:6])[0]
        seq2 = struct.unpack("<H", packet2[4:6])[0]
        seq3 = struct.unpack("<H", packet3[4:6])[0]

        assert seq1 == 1
        assert seq2 == 2
        assert seq3 == 3

    def test_stats_increment(self):
        """Test statistics increment."""
        handler = ParamHandler()
        assert handler.stats["requests_sent"] == 0

        handler.build_request(ParamCommand.LIST, 0)
        assert handler.stats["requests_sent"] == 1

        handler.build_request(ParamCommand.GET, 5)
        assert handler.stats["requests_sent"] == 2


class TestParseResponse:
    """Test PARAM response parsing."""

    def _build_response(
        self,
        command: int = ParamCommand.GET,
        param_index: int = 0,
        param_type: int = 6,
        param_access: int = 1,
        value: float = 100.0,
        group: str = "PID",
        name: str = "P_GAIN",
        total_params: int = 10,
        error_code: int = 0,
    ) -> bytes:
        """Helper: Build valid PARAM response packet."""
        seq = 42
        timestamp_us = int(time.time() * 1_000_000) & 0xFFFFFFFF

        # Pack header + payload (without CRC)
        packet_no_crc = struct.pack(
            "<BBBBHI",  # Header
            MAGIC_BYTE,
            PROTOCOL_VERSION,
            PacketType.PARAM_RESPONSE,
            0,  # flags
            seq,
            timestamp_us,
        )

        # Encode strings (16 bytes each, null-padded)
        group_bytes = group.encode("utf-8")[:16].ljust(16, b"\x00")
        name_bytes = name.encode("utf-8")[:16].ljust(16, b"\x00")

        # Pack payload
        payload = struct.pack(
            "<BBBBf16s16sBB",
            command,
            param_index,
            param_type,
            param_access,
            value,
            group_bytes,
            name_bytes,
            total_params,
            error_code,
        )

        packet_no_crc += payload

        # Calculate and append CRC
        crc = crc16_x25(packet_no_crc)
        packet = packet_no_crc + struct.pack("<H", crc)

        return packet

    def test_parse_valid_response(self):
        """Test parsing valid response."""
        handler = ParamHandler()
        packet = self._build_response(
            command=ParamCommand.GET,
            param_index=5,
            value=250.5,
            group="PID",
            name="P_GAIN",
            total_params=20,
            error_code=0,
        )

        response = handler.parse_response(packet)

        assert response["command"] == ParamCommand.GET
        assert response["param_index"] == 5
        assert abs(response["value"] - 250.5) < 0.001
        assert response["group"] == "PID"
        assert response["name"] == "P_GAIN"
        assert response["total_params"] == 20
        assert response["error_code"] == 0
        assert handler.stats["responses_received"] == 1

    def test_parse_response_invalid_size(self):
        """Test parsing packet with invalid size."""
        handler = ParamHandler()

        with pytest.raises(ValueError, match="Invalid packet size"):
            handler.parse_response(b"\x00" * 10)  # Too short

    def test_parse_response_crc_error(self):
        """Test parsing packet with CRC error."""
        handler = ParamHandler()
        packet = self._build_response()

        # Corrupt CRC
        packet = packet[:-2] + b"\xFF\xFF"

        with pytest.raises(ParamCRCError, match="CRC mismatch"):
            handler.parse_response(packet)

        assert handler.stats["crc_errors"] == 1

    def test_parse_response_invalid_magic(self):
        """Test parsing packet with invalid magic byte."""
        handler = ParamHandler()
        packet = self._build_response()

        # Corrupt magic byte
        packet = b"\xFF" + packet[1:]

        # Recalculate CRC
        crc = crc16_x25(packet[:-2])
        packet = packet[:-2] + struct.pack("<H", crc)

        with pytest.raises(ValueError, match="Invalid magic"):
            handler.parse_response(packet)

    def test_parse_response_invalid_type(self):
        """Test parsing packet with invalid type."""
        handler = ParamHandler()
        packet = bytearray(self._build_response())

        # Change packet type to ATTITUDE (0x01)
        packet[2] = 0x01

        # Recalculate CRC
        crc = crc16_x25(packet[:-2])
        packet[-2:] = struct.pack("<H", crc)

        with pytest.raises(ValueError, match="Invalid packet type"):
            handler.parse_response(bytes(packet))

    def test_parse_response_string_decoding(self):
        """Test string decoding with various characters."""
        handler = ParamHandler()

        # Test with special characters
        packet = self._build_response(group="CTRL_123", name="YAW_RATE")
        response = handler.parse_response(packet)

        assert response["group"] == "CTRL_123"
        assert response["name"] == "YAW_RATE"

    def test_parse_response_empty_strings(self):
        """Test parsing with empty strings."""
        handler = ParamHandler()
        packet = self._build_response(group="", name="")
        response = handler.parse_response(packet)

        assert response["group"] == ""
        assert response["name"] == ""


class TestHandleResponse:
    """Test response handling and queueing."""

    @pytest.mark.asyncio
    async def test_handle_response_adds_to_queue(self):
        """Test that handle_response adds to queue."""
        handler = ParamHandler()
        response = {"param_index": 5, "value": 100.0}

        await handler.handle_response(response)

        # Verify it's in the queue
        queued_response = await asyncio.wait_for(handler._response_queue.get(), timeout=0.1)
        assert queued_response == response

    @pytest.mark.asyncio
    async def test_handle_response_queue_full(self):
        """Test handling QueueFull exception."""
        handler = ParamHandler()

        # Fill the queue (default maxsize is 0 = unlimited, so we need to set maxsize)
        handler._response_queue = asyncio.Queue(maxsize=1)

        # Add first response (fills queue)
        await handler.handle_response({"param_index": 1, "value": 1.0})

        # Try to add second response (should log warning but not raise)
        await handler.handle_response({"param_index": 2, "value": 2.0})

        # Queue should only have first response
        response = await handler._response_queue.get()
        assert response["param_index"] == 1

    @pytest.mark.asyncio
    async def test_wait_for_response_success(self):
        """Test waiting for response successfully."""
        handler = ParamHandler()
        response = {"param_index": 5, "value": 100.0}

        # Add response to queue
        await handler.handle_response(response)

        # Wait for it
        received = await handler.wait_for_response()
        assert received == response

    @pytest.mark.asyncio
    async def test_wait_for_response_timeout(self):
        """Test timeout when no response."""
        handler = ParamHandler(timeout=0.1)

        with pytest.raises(ParamTimeoutError, match="No response within 0.1s"):
            await handler.wait_for_response()

        assert handler.stats["timeouts"] == 1


class TestListParams:
    """Test list_params() method."""

    @pytest.mark.asyncio
    async def test_list_params_success(self):
        """Test listing parameters successfully."""
        handler = ParamHandler()
        sent_packets = []

        # Mock send function
        async def mock_send(packet: bytes):
            sent_packets.append(packet)

            # Parse request to determine response
            command = struct.unpack("<B", packet[10:11])[0]
            param_index = struct.unpack("<B", packet[11:12])[0]

            # Build response
            if param_index == 0:
                # First request - return total_params=3
                response_packet = self._build_response(
                    param_index=0,
                    group="PID",
                    name="P_GAIN",
                    value=100.0,
                    total_params=3,
                    error_code=0,
                )
            elif param_index == 1:
                response_packet = self._build_response(
                    param_index=1, group="PID", name="I_GAIN", value=50.0, total_params=3, error_code=0
                )
            elif param_index == 2:
                response_packet = self._build_response(
                    param_index=2, group="PID", name="D_GAIN", value=25.0, total_params=3, error_code=0
                )
            else:
                return

            # Parse and queue response
            parsed = handler.parse_response(response_packet)
            await handler.handle_response(parsed)

        params = await handler.list_params(mock_send)

        # Verify
        assert len(params) == 3
        assert params[0]["name"] == "P_GAIN"
        assert params[1]["name"] == "I_GAIN"
        assert params[2]["name"] == "D_GAIN"
        assert len(sent_packets) == 4  # 1 initial + 3 params

    @pytest.mark.asyncio
    async def test_list_params_with_errors(self):
        """Test listing parameters with some errors."""
        handler = ParamHandler()

        async def mock_send(packet: bytes):
            param_index = struct.unpack("<B", packet[11:12])[0]

            if param_index == 0:
                # First request - return total_params=3
                response_packet = self._build_response(
                    param_index=0, group="PID", name="P_GAIN", value=100.0, total_params=3, error_code=0
                )
            elif param_index == 1:
                # Second param has error
                response_packet = self._build_response(
                    param_index=1, group="", name="", value=0.0, total_params=3, error_code=2
                )
            elif param_index == 2:
                response_packet = self._build_response(
                    param_index=2, group="PID", name="D_GAIN", value=25.0, total_params=3, error_code=0
                )
            else:
                return

            parsed = handler.parse_response(response_packet)
            await handler.handle_response(parsed)

        params = await handler.list_params(mock_send)

        # Should only have 2 params (skipped the one with error_code=2)
        assert len(params) == 2
        assert params[0]["name"] == "P_GAIN"
        assert params[1]["name"] == "D_GAIN"

    @pytest.mark.asyncio
    async def test_list_params_with_timeout(self):
        """Test listing parameters with timeout on one param."""
        handler = ParamHandler(timeout=0.1)

        async def mock_send(packet: bytes):
            param_index = struct.unpack("<B", packet[11:12])[0]

            if param_index == 0:
                # First request - return total_params=3
                response_packet = self._build_response(
                    param_index=0, group="PID", name="P_GAIN", value=100.0, total_params=3, error_code=0
                )
                parsed = handler.parse_response(response_packet)
                await handler.handle_response(parsed)
            elif param_index == 1:
                # Timeout - don't send response
                await asyncio.sleep(0.2)
            elif param_index == 2:
                response_packet = self._build_response(
                    param_index=2, group="PID", name="D_GAIN", value=25.0, total_params=3, error_code=0
                )
                parsed = handler.parse_response(response_packet)
                await handler.handle_response(parsed)

        params = await handler.list_params(mock_send)

        # Should only have 2 params (skipped the one that timed out)
        assert len(params) == 2
        assert params[0]["name"] == "P_GAIN"
        assert params[1]["name"] == "D_GAIN"

    def _build_response(
        self,
        param_index: int,
        group: str,
        name: str,
        value: float,
        total_params: int,
        error_code: int,
    ) -> bytes:
        """Helper to build response packet."""
        seq = 42
        timestamp_us = int(time.time() * 1_000_000) & 0xFFFFFFFF

        packet_no_crc = struct.pack(
            "<BBBBHI",
            MAGIC_BYTE,
            PROTOCOL_VERSION,
            PacketType.PARAM_RESPONSE,
            0,
            seq,
            timestamp_us,
        )

        group_bytes = group.encode("utf-8")[:16].ljust(16, b"\x00")
        name_bytes = name.encode("utf-8")[:16].ljust(16, b"\x00")

        payload = struct.pack(
            "<BBBBf16s16sBB",
            ParamCommand.LIST,
            param_index,
            6,  # param_type
            1,  # param_access
            value,
            group_bytes,
            name_bytes,
            total_params,
            error_code,
        )

        packet_no_crc += payload
        crc = crc16_x25(packet_no_crc)
        return packet_no_crc + struct.pack("<H", crc)


class TestGetParam:
    """Test get_param() method."""

    @pytest.mark.asyncio
    async def test_get_param_success(self):
        """Test getting parameter value successfully."""
        handler = ParamHandler()

        async def mock_send(packet: bytes):
            # Build successful response
            response_packet = self._build_response(param_index=5, value=123.456, error_code=0)
            parsed = handler.parse_response(response_packet)
            await handler.handle_response(parsed)

        value = await handler.get_param(5, mock_send)
        assert abs(value - 123.456) < 0.001

    @pytest.mark.asyncio
    async def test_get_param_not_found(self):
        """Test getting non-existent parameter."""
        handler = ParamHandler()

        async def mock_send(packet: bytes):
            # Build error response
            response_packet = self._build_response(param_index=99, value=0.0, error_code=ParamError.PARAM_NOT_FOUND)
            parsed = handler.parse_response(response_packet)
            await handler.handle_response(parsed)

        with pytest.raises(ParamNotFoundError, match="Parameter 99 not found"):
            await handler.get_param(99, mock_send)

    @pytest.mark.asyncio
    async def test_get_param_timeout(self):
        """Test GET timeout."""
        handler = ParamHandler(timeout=0.1)

        async def mock_send(packet: bytes):
            # Don't send response - simulate timeout
            await asyncio.sleep(0.2)

        with pytest.raises(ParamTimeoutError):
            await handler.get_param(5, mock_send)

    @pytest.mark.asyncio
    async def test_get_param_unknown_error(self):
        """Test getting parameter with unknown error code."""
        handler = ParamHandler()

        async def mock_send(packet: bytes):
            # Build error response with unknown error code
            response_packet = self._build_response(param_index=5, value=0.0, error_code=99)
            parsed = handler.parse_response(response_packet)
            await handler.handle_response(parsed)

        with pytest.raises(Exception, match="Error getting param 5: error_code=99"):
            await handler.get_param(5, mock_send)

    def _build_response(self, param_index: int, value: float, error_code: int) -> bytes:
        """Helper to build response packet."""
        seq = 42
        timestamp_us = int(time.time() * 1_000_000) & 0xFFFFFFFF

        packet_no_crc = struct.pack(
            "<BBBBHI",
            MAGIC_BYTE,
            PROTOCOL_VERSION,
            PacketType.PARAM_RESPONSE,
            0,
            seq,
            timestamp_us,
        )

        group_bytes = b"PID\x00" * 4
        name_bytes = b"P_GAIN\x00" * 2 + b"\x00\x00\x00\x00"

        payload = struct.pack(
            "<BBBBf16s16sBB",
            ParamCommand.GET,
            param_index,
            6,
            1,
            value,
            group_bytes,
            name_bytes,
            10,
            error_code,
        )

        packet_no_crc += payload
        crc = crc16_x25(packet_no_crc)
        return packet_no_crc + struct.pack("<H", crc)


class TestSetParam:
    """Test set_param() method."""

    @pytest.mark.asyncio
    async def test_set_param_success(self):
        """Test setting parameter value successfully."""
        handler = ParamHandler()

        async def mock_send(packet: bytes):
            # Parse request to get value
            value_requested = struct.unpack("<f", packet[12:16])[0]

            # Build successful response with same value
            response_packet = self._build_response(param_index=10, value=value_requested, error_code=0)
            parsed = handler.parse_response(response_packet)
            await handler.handle_response(parsed)

        result = await handler.set_param(10, 999.999, mock_send)
        assert result is True

    @pytest.mark.asyncio
    async def test_set_param_not_found(self):
        """Test setting non-existent parameter."""
        handler = ParamHandler()

        async def mock_send(packet: bytes):
            response_packet = self._build_response(param_index=99, value=0.0, error_code=ParamError.PARAM_NOT_FOUND)
            parsed = handler.parse_response(response_packet)
            await handler.handle_response(parsed)

        with pytest.raises(ParamNotFoundError, match="Parameter 99 not found"):
            await handler.set_param(99, 100.0, mock_send)

    @pytest.mark.asyncio
    async def test_set_param_read_only(self):
        """Test setting read-only parameter."""
        handler = ParamHandler()

        async def mock_send(packet: bytes):
            response_packet = self._build_response(param_index=5, value=0.0, error_code=ParamError.WRITE_FAILED)
            parsed = handler.parse_response(response_packet)
            await handler.handle_response(parsed)

        with pytest.raises(ParamReadOnlyError, match="Parameter 5 is read-only"):
            await handler.set_param(5, 100.0, mock_send)

    @pytest.mark.asyncio
    async def test_set_param_unknown_error(self):
        """Test setting parameter with unknown error code."""
        handler = ParamHandler()

        async def mock_send(packet: bytes):
            response_packet = self._build_response(param_index=10, value=0.0, error_code=99)
            parsed = handler.parse_response(response_packet)
            await handler.handle_response(parsed)

        with pytest.raises(Exception, match="Error setting param 10: error_code=99"):
            await handler.set_param(10, 100.0, mock_send)

    @pytest.mark.asyncio
    async def test_set_param_value_mismatch_warning(self):
        """Test warning when set value doesn't match returned value."""
        handler = ParamHandler()

        async def mock_send(packet: bytes):
            # Return different value than requested
            response_packet = self._build_response(param_index=10, value=95.0, error_code=0)
            parsed = handler.parse_response(response_packet)
            await handler.handle_response(parsed)

        # Should succeed but log warning (we requested 100.0, got 95.0)
        result = await handler.set_param(10, 100.0, mock_send)
        assert result is True

    def _build_response(self, param_index: int, value: float, error_code: int) -> bytes:
        """Helper to build response packet."""
        seq = 42
        timestamp_us = int(time.time() * 1_000_000) & 0xFFFFFFFF

        packet_no_crc = struct.pack(
            "<BBBBHI",
            MAGIC_BYTE,
            PROTOCOL_VERSION,
            PacketType.PARAM_RESPONSE,
            0,
            seq,
            timestamp_us,
        )

        group_bytes = b"PID\x00" * 4
        name_bytes = b"P_GAIN\x00" * 2 + b"\x00\x00\x00\x00"

        payload = struct.pack(
            "<BBBBf16s16sBB",
            ParamCommand.SET,
            param_index,
            6,
            1,
            value,
            group_bytes,
            name_bytes,
            10,
            error_code,
        )

        packet_no_crc += payload
        crc = crc16_x25(packet_no_crc)
        return packet_no_crc + struct.pack("<H", crc)


class TestStatistics:
    """Test statistics tracking."""

    def test_get_stats(self):
        """Test getting statistics."""
        handler = ParamHandler()

        # Build some requests
        handler.build_request(ParamCommand.GET, 0)
        handler.build_request(ParamCommand.SET, 1, 100.0)

        stats = handler.get_stats()
        assert stats["requests_sent"] == 2
        assert stats["responses_received"] == 0

    def test_reset_stats(self):
        """Test resetting statistics."""
        handler = ParamHandler()

        # Build requests
        handler.build_request(ParamCommand.GET, 0)
        handler.stats["timeouts"] = 5
        handler.stats["crc_errors"] = 3

        handler.reset_stats()

        assert handler.stats["requests_sent"] == 0
        assert handler.stats["responses_received"] == 0
        assert handler.stats["timeouts"] == 0
        assert handler.stats["crc_errors"] == 0
        assert handler.stats["last_response_time"] is None


class TestSequentialRequests:
    """Test request locking (sequential requests)."""

    @pytest.mark.asyncio
    async def test_requests_are_sequential(self):
        """Test that requests are processed sequentially."""
        handler = ParamHandler(timeout=0.5)
        request_order = []

        async def mock_send(packet: bytes):
            # Record request
            param_index = struct.unpack("<B", packet[11:12])[0]
            request_order.append(param_index)

            # Simulate processing delay
            await asyncio.sleep(0.1)

            # Send response
            response_packet = self._build_response(param_index=param_index, value=100.0, error_code=0)
            parsed = handler.parse_response(response_packet)
            await handler.handle_response(parsed)

        # Launch 3 concurrent requests
        tasks = [
            asyncio.create_task(handler.get_param(0, mock_send)),
            asyncio.create_task(handler.get_param(1, mock_send)),
            asyncio.create_task(handler.get_param(2, mock_send)),
        ]

        await asyncio.gather(*tasks)

        # Verify sequential execution (order preserved)
        assert request_order == [0, 1, 2]

    def _build_response(self, param_index: int, value: float, error_code: int) -> bytes:
        """Helper to build response packet."""
        seq = 42
        timestamp_us = int(time.time() * 1_000_000) & 0xFFFFFFFF

        packet_no_crc = struct.pack(
            "<BBBBHI",
            MAGIC_BYTE,
            PROTOCOL_VERSION,
            PacketType.PARAM_RESPONSE,
            0,
            seq,
            timestamp_us,
        )

        group_bytes = b"PID\x00" * 4
        name_bytes = b"P_GAIN\x00" * 2 + b"\x00\x00\x00\x00"

        payload = struct.pack(
            "<BBBBf16s16sBB",
            ParamCommand.GET,
            param_index,
            6,
            1,
            value,
            group_bytes,
            name_bytes,
            10,
            error_code,
        )

        packet_no_crc += payload
        crc = crc16_x25(packet_no_crc)
        return packet_no_crc + struct.pack("<H", crc)
