"""
Tests for PARAM UART Bridge.

Author: Claude + Daniel
Date: 2025-12-20
"""

import struct
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from app.services.param_uart_bridge import (
    ParamUARTBridge,
    crc16_x25,
    ParamTimeoutError,
    ParamNotFoundError,
    ParamReadOnlyError,
    ParamConnectionError,
    TELEM_PARAM_REQUEST,
    TELEM_PARAM_RESPONSE,
    PARAM_CMD_LIST,
    PARAM_CMD_GET,
    PARAM_CMD_SET,
    PARAM_CMD_LIST_RESP,
    PARAM_CMD_GET_RESP,
    PARAM_CMD_SET_RESP,
    PARAM_CMD_ERROR,
    ERROR_PARAM_NOT_FOUND,
    ERROR_WRITE_FAILED,
    MAGIC_BYTE,
    PROTOCOL_VERSION,
)


# === CRC Tests ===


def test_crc16_x25():
    """Test CRC-16/X.25 calculation."""
    # Known test vectors
    test_data = b'\x5B\x02\x10\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00'
    crc = crc16_x25(test_data)

    # CRC should be deterministic
    assert isinstance(crc, int)
    assert 0 <= crc <= 0xFFFF

    # Same input should give same output
    crc2 = crc16_x25(test_data)
    assert crc == crc2


def test_crc16_x25_empty():
    """Test CRC with empty data."""
    crc = crc16_x25(b'')
    # Empty data: init=0xFFFF, no processing, final XOR = 0
    assert crc == 0x0000


# === Packet Building Tests ===


def test_build_request_list():
    """Test building LIST request packet."""
    bridge = ParamUARTBridge()
    packet = bridge._build_request(PARAM_CMD_LIST, 0)

    assert len(packet) == 20  # REQUEST_PACKET_SIZE (12 header + 6 payload + 2 CRC)
    assert packet[0] == MAGIC_BYTE
    assert packet[1] == PROTOCOL_VERSION
    assert packet[2] == TELEM_PARAM_REQUEST

    # Verify CRC
    crc_calc = crc16_x25(packet[:-2])
    crc_packet = struct.unpack('<H', packet[-2:])[0]
    assert crc_calc == crc_packet


def test_build_request_get():
    """Test building GET request packet."""
    bridge = ParamUARTBridge()
    packet = bridge._build_request(PARAM_CMD_GET, 3)

    assert len(packet) == 20
    assert packet[0] == MAGIC_BYTE

    # Extract command and index
    command, param_index = struct.unpack('<BB', packet[12:14])
    assert command == PARAM_CMD_GET
    assert param_index == 3


def test_build_request_set():
    """Test building SET request packet."""
    bridge = ParamUARTBridge()
    packet = bridge._build_request(PARAM_CMD_SET, 0, 300.5)

    assert len(packet) == 20
    assert packet[0] == MAGIC_BYTE

    # Extract value
    value = struct.unpack('<f', packet[14:18])[0]
    assert abs(value - 300.5) < 0.001


# === Packet Parsing Tests ===


def test_parse_response_valid():
    """Test parsing valid response packet."""
    bridge = ParamUARTBridge()

    # Build fake response packet using correct format with padding
    import io
    buf = io.BytesIO()

    # Header (12 bytes with padding)
    buf.write(struct.pack('<BBBBHxxI',
        MAGIC_BYTE,             # magic
        PROTOCOL_VERSION,       # version
        TELEM_PARAM_RESPONSE,   # type
        0,                      # flags
        42,                     # seq (followed by 2-byte padding)
        123456789               # timestamp_us
    ))

    # Payload (43 bytes with padding after value)
    group = b'pid_attitude\x00\x00\x00\x00'
    name = b'roll_rate_kp\x00\x00\x00\x00'

    buf.write(struct.pack('<BBBBfx16s16sBB',
        PARAM_CMD_GET_RESP,     # command
        0,                      # param_index
        6,                      # param_type (float)
        1,                      # param_access (rw)
        250.0,                  # value (followed by 1-byte padding)
        group,                  # group[16]
        name,                   # name[16]
        6,                      # total_params
        0                       # error_code
    ))

    # Calculate and append CRC
    packet_data = buf.getvalue()
    crc = crc16_x25(packet_data)
    buf.write(struct.pack('<H', crc))

    # Parse
    response = bridge._parse_response(buf.getvalue())

    assert response['seq'] == 42
    assert response['command'] == PARAM_CMD_GET_RESP
    assert response['param_index'] == 0
    assert response['value'] == 250.0
    assert response['group'] == 'pid_attitude'
    assert response['name'] == 'roll_rate_kp'
    assert response['total_params'] == 6
    assert response['error_code'] == 0


def test_parse_response_invalid_magic():
    """Test parsing response with invalid magic byte."""
    bridge = ParamUARTBridge()

    # Build 57-byte packet with wrong magic but valid CRC
    import io
    buf = io.BytesIO()

    # Header with WRONG magic
    buf.write(struct.pack('<BBBBHxxI',
        0xFF,  # Wrong magic!
        PROTOCOL_VERSION,
        TELEM_PARAM_RESPONSE,
        0, 42, 123456789
    ))

    # Payload (43 bytes)
    group = b'\x00' * 16
    name = b'\x00' * 16
    buf.write(struct.pack('<BBBBfx16s16sBB',
        PARAM_CMD_GET_RESP, 0, 6, 1, 0.0, group, name, 0, 0
    ))

    # Calculate correct CRC
    packet_data = buf.getvalue()
    crc = crc16_x25(packet_data)
    buf.write(struct.pack('<H', crc))

    with pytest.raises(ValueError, match="Invalid magic"):
        bridge._parse_response(buf.getvalue())


def test_parse_response_crc_error():
    """Test parsing response with CRC error."""
    bridge = ParamUARTBridge()

    # Build packet with correct magic but wrong CRC
    import io
    buf = io.BytesIO()

    # Header (12 bytes with padding)
    buf.write(struct.pack('<BBBBHxxI',
        MAGIC_BYTE,
        PROTOCOL_VERSION,
        TELEM_PARAM_RESPONSE,
        0, 42, 123456789
    ))

    # Payload (43 bytes)
    buf.write(b'\x00' * 43)

    # Wrong CRC
    buf.write(struct.pack('<H', 0xFFFF))

    from app.services.param_uart_bridge import ParamCRCError
    with pytest.raises(ParamCRCError):
        bridge._parse_response(buf.getvalue())


# === Bridge Initialization Tests ===


@pytest.mark.anyio
async def test_bridge_init():
    """Test ParamUARTBridge initialization."""
    bridge = ParamUARTBridge(timeout=2.0, reconnect_interval=5.0)

    assert bridge.timeout == 2.0
    assert bridge.reconnect_interval == 5.0
    assert not bridge.is_connected()
    assert bridge.seq_counter == 0


@pytest.mark.anyio
async def test_bridge_list_ports():
    """Test listing serial ports."""
    ports = ParamUARTBridge.list_ports()
    assert isinstance(ports, list)
    # Ports may or may not be available, just check type


# === Mock Serial Tests ===


class MockSerial:
    """Mock serial.Serial for testing."""
    def __init__(self, *args, **kwargs):
        self.is_open = True
        self.in_waiting = 0
        self._buffer = bytearray()

    def write(self, data):
        return len(data)

    def flush(self):
        pass

    def read(self, size):
        result = bytes(self._buffer[:size])
        self._buffer = self._buffer[size:]
        self.in_waiting = len(self._buffer)
        return result

    def close(self):
        self.is_open = False

    def set_response(self, data):
        """Set mock response data."""
        self._buffer = bytearray(data)
        self.in_waiting = len(self._buffer)


@pytest.mark.anyio
async def test_bridge_connect_disconnect():
    """Test connect and disconnect."""
    with patch('serial.Serial', MockSerial):
        bridge = ParamUARTBridge()

        # Connect
        result = await bridge.connect("/dev/ttyUSB0", 115200)
        assert result is True
        assert bridge.is_connected()

        # Disconnect
        await bridge.disconnect()
        assert not bridge.is_connected()


@pytest.mark.anyio
async def test_get_param_success():
    """Test successful GET parameter."""
    with patch('serial.Serial', MockSerial) as mock_serial_class:
        bridge = ParamUARTBridge()
        await bridge.connect("/dev/ttyUSB0", 115200)

        # Build valid response (57 bytes with padding)
        import io
        buf = io.BytesIO()
        group = b'pid_attitude\x00\x00\x00\x00'
        name = b'roll_rate_kp\x00\x00\x00\x00'

        # Header (12 bytes)
        buf.write(struct.pack('<BBBBHxxI',
            MAGIC_BYTE, PROTOCOL_VERSION, TELEM_PARAM_RESPONSE,
            0, 1, 123456789
        ))
        # Payload (43 bytes)
        buf.write(struct.pack('<BBBBfx16s16sBB',
            PARAM_CMD_GET_RESP, 0, 6, 1, 250.0, group, name, 6, 0
        ))
        packet_data = buf.getvalue()
        crc = crc16_x25(packet_data)
        buf.write(struct.pack('<H', crc))

        # Set mock response
        bridge.serial.set_response(buf.getvalue())

        # Get param
        value = await bridge.get_param(0)
        assert value == 250.0


@pytest.mark.anyio
async def test_get_param_not_found():
    """Test GET parameter with not found error."""
    with patch('serial.Serial', MockSerial):
        bridge = ParamUARTBridge()
        await bridge.connect("/dev/ttyUSB0", 115200)

        # Build error response (57 bytes)
        import io
        buf = io.BytesIO()
        group = b'\x00' * 16
        name = b'\x00' * 16

        # Header (12 bytes)
        buf.write(struct.pack('<BBBBHxxI',
            MAGIC_BYTE, PROTOCOL_VERSION, TELEM_PARAM_RESPONSE,
            0, 1, 123456789
        ))
        # Payload (43 bytes)
        buf.write(struct.pack('<BBBBfx16s16sBB',
            PARAM_CMD_ERROR, 99, 6, 1, 0.0, group, name, 0, ERROR_PARAM_NOT_FOUND
        ))
        packet_data = buf.getvalue()
        crc = crc16_x25(packet_data)
        buf.write(struct.pack('<H', crc))

        bridge.serial.set_response(buf.getvalue())

        with pytest.raises(ParamNotFoundError):
            await bridge.get_param(99)


@pytest.mark.anyio
async def test_set_param_success():
    """Test successful SET parameter."""
    with patch('serial.Serial', MockSerial):
        bridge = ParamUARTBridge()
        await bridge.connect("/dev/ttyUSB0", 115200)

        # Build success response (57 bytes)
        import io
        buf = io.BytesIO()
        group = b'pid_attitude\x00\x00\x00\x00'
        name = b'roll_rate_kp\x00\x00\x00\x00'

        # Header (12 bytes)
        buf.write(struct.pack('<BBBBHxxI',
            MAGIC_BYTE, PROTOCOL_VERSION, TELEM_PARAM_RESPONSE,
            0, 1, 123456789
        ))
        # Payload (43 bytes)
        buf.write(struct.pack('<BBBBfx16s16sBB',
            PARAM_CMD_SET_RESP, 0, 6, 1, 300.5, group, name, 6, 0
        ))
        packet_data = buf.getvalue()
        crc = crc16_x25(packet_data)
        buf.write(struct.pack('<H', crc))

        bridge.serial.set_response(buf.getvalue())

        result = await bridge.set_param(0, 300.5)
        assert result is True


@pytest.mark.anyio
async def test_set_param_read_only():
    """Test SET parameter with read-only error."""
    with patch('serial.Serial', MockSerial):
        bridge = ParamUARTBridge()
        await bridge.connect("/dev/ttyUSB0", 115200)

        # Build error response (57 bytes)
        import io
        buf = io.BytesIO()
        group = b'\x00' * 16
        name = b'\x00' * 16

        # Header (12 bytes)
        buf.write(struct.pack('<BBBBHxxI',
            MAGIC_BYTE, PROTOCOL_VERSION, TELEM_PARAM_RESPONSE,
            0, 1, 123456789
        ))
        # Payload (43 bytes)
        buf.write(struct.pack('<BBBBfx16s16sBB',
            PARAM_CMD_ERROR, 0, 6, 0, 0.0, group, name, 0, ERROR_WRITE_FAILED
        ))
        packet_data = buf.getvalue()
        crc = crc16_x25(packet_data)
        buf.write(struct.pack('<H', crc))

        bridge.serial.set_response(buf.getvalue())

        with pytest.raises(ParamReadOnlyError):
            await bridge.set_param(0, 100.0)


# === Statistics Tests ===


@pytest.mark.anyio
async def test_statistics():
    """Test statistics tracking."""
    bridge = ParamUARTBridge()

    stats = bridge.get_stats()
    assert stats['requests_sent'] == 0
    assert stats['responses_received'] == 0
    assert stats['timeouts'] == 0
    assert stats['crc_errors'] == 0

    # Reset stats
    bridge.reset_stats()
    stats = bridge.get_stats()
    assert stats['requests_sent'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
