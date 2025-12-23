"""
Tests for protocol utilities and helper functions.
"""

from app.utils.protocol import (
    MAGIC_BYTE,
    PACKET_SIZES,
    PROTOCOL_VERSION,
    PacketType,
    ParamCommand,
    ParamError,
    get_packet_type_name,
    is_param_packet,
    is_telemetry_packet,
)


class TestProtocolConstants:
    """Test protocol constants."""

    def test_magic_byte(self):
        """Test magic byte value."""
        assert MAGIC_BYTE == 0x5B

    def test_protocol_version(self):
        """Test protocol version."""
        assert PROTOCOL_VERSION == 2


class TestPacketType:
    """Test PacketType enum."""

    def test_telemetry_types(self):
        """Test telemetry packet type values."""
        assert PacketType.ATTITUDE == 0x01
        assert PacketType.CONTROL == 0x02
        assert PacketType.MOTORS == 0x03
        assert PacketType.STATUS == 0x04
        assert PacketType.SENSORS == 0x05
        assert PacketType.SAFETY == 0x06
        assert PacketType.PERFORMANCE == 0x07

    def test_param_types(self):
        """Test PARAM packet type values."""
        assert PacketType.PARAM_REQUEST == 0x10
        assert PacketType.PARAM_RESPONSE == 0x11


class TestParamCommand:
    """Test ParamCommand enum."""

    def test_param_commands(self):
        """Test PARAM command values."""
        assert ParamCommand.LIST == 0x01
        assert ParamCommand.GET == 0x02
        assert ParamCommand.SET == 0x03


class TestParamError:
    """Test ParamError enum."""

    def test_param_errors(self):
        """Test PARAM error codes."""
        assert ParamError.INDEX_OUT_OF_RANGE == 1
        assert ParamError.PARAM_NOT_FOUND == 2
        assert ParamError.READ_FAILED == 3
        assert ParamError.WRITE_FAILED == 4
        assert ParamError.UNKNOWN_COMMAND == 5


class TestPacketSizes:
    """Test PACKET_SIZES dictionary."""

    def test_telemetry_packet_sizes(self):
        """Test telemetry packet sizes."""
        assert PACKET_SIZES[PacketType.ATTITUDE] == 24  # 10 header + 12 payload + 2 CRC
        assert PACKET_SIZES[PacketType.CONTROL] == 30  # 10 header + 18 payload + 2 CRC
        assert PACKET_SIZES[PacketType.MOTORS] == 31  # 10 header + 19 payload + 2 CRC
        assert PACKET_SIZES[PacketType.STATUS] == 24  # 10 header + 12 payload + 2 CRC
        assert PACKET_SIZES[PacketType.SENSORS] == 30  # 10 header + 18 payload + 2 CRC
        assert PACKET_SIZES[PacketType.SAFETY] == 20  # 10 header + 8 payload + 2 CRC
        assert PACKET_SIZES[PacketType.PERFORMANCE] == 22  # 10 header + 10 payload + 2 CRC

    def test_param_packet_sizes(self):
        """Test PARAM packet sizes."""
        assert PACKET_SIZES[PacketType.PARAM_REQUEST] == 18  # 10 header + 6 payload + 2 CRC
        assert PACKET_SIZES[PacketType.PARAM_RESPONSE] == 54  # 10 header + 42 payload + 2 CRC


class TestIsParamPacket:
    """Test is_param_packet() helper function."""

    def test_param_request_is_param(self):
        """Test PARAM_REQUEST is PARAM."""
        assert is_param_packet(PacketType.PARAM_REQUEST) is True

    def test_param_response_is_param(self):
        """Test PARAM_RESPONSE is PARAM."""
        assert is_param_packet(PacketType.PARAM_RESPONSE) is True

    def test_attitude_not_param(self):
        """Test ATTITUDE is not PARAM."""
        assert is_param_packet(PacketType.ATTITUDE) is False

    def test_motors_not_param(self):
        """Test MOTORS is not PARAM."""
        assert is_param_packet(PacketType.MOTORS) is False

    def test_unknown_type_not_param(self):
        """Test unknown type is not PARAM."""
        assert is_param_packet(0xFF) is False


class TestIsTelemetryPacket:
    """Test is_telemetry_packet() helper function."""

    def test_attitude_is_telemetry(self):
        """Test ATTITUDE is telemetry."""
        assert is_telemetry_packet(PacketType.ATTITUDE) is True

    def test_motors_is_telemetry(self):
        """Test MOTORS is telemetry."""
        assert is_telemetry_packet(PacketType.MOTORS) is True

    def test_status_is_telemetry(self):
        """Test STATUS is telemetry."""
        assert is_telemetry_packet(PacketType.STATUS) is True

    def test_control_is_telemetry(self):
        """Test CONTROL is telemetry."""
        assert is_telemetry_packet(PacketType.CONTROL) is True

    def test_sensors_is_telemetry(self):
        """Test SENSORS is telemetry."""
        assert is_telemetry_packet(PacketType.SENSORS) is True

    def test_safety_is_telemetry(self):
        """Test SAFETY is telemetry."""
        assert is_telemetry_packet(PacketType.SAFETY) is True

    def test_performance_is_telemetry(self):
        """Test PERFORMANCE is telemetry."""
        assert is_telemetry_packet(PacketType.PERFORMANCE) is True

    def test_param_request_not_telemetry(self):
        """Test PARAM_REQUEST is not telemetry."""
        assert is_telemetry_packet(PacketType.PARAM_REQUEST) is False

    def test_param_response_not_telemetry(self):
        """Test PARAM_RESPONSE is not telemetry."""
        assert is_telemetry_packet(PacketType.PARAM_RESPONSE) is False

    def test_unknown_type_not_telemetry(self):
        """Test unknown type is not telemetry."""
        assert is_telemetry_packet(0xFF) is False


class TestGetPacketTypeName:
    """Test get_packet_type_name() helper function."""

    def test_get_name_for_attitude(self):
        """Test getting name for ATTITUDE."""
        assert get_packet_type_name(PacketType.ATTITUDE) == "ATT"

    def test_get_name_for_control(self):
        """Test getting name for CONTROL."""
        assert get_packet_type_name(PacketType.CONTROL) == "CTL"

    def test_get_name_for_motors(self):
        """Test getting name for MOTORS."""
        assert get_packet_type_name(PacketType.MOTORS) == "MOT"

    def test_get_name_for_status(self):
        """Test getting name for STATUS."""
        assert get_packet_type_name(PacketType.STATUS) == "STA"

    def test_get_name_for_sensors(self):
        """Test getting name for SENSORS."""
        assert get_packet_type_name(PacketType.SENSORS) == "SENS"

    def test_get_name_for_safety(self):
        """Test getting name for SAFETY."""
        assert get_packet_type_name(PacketType.SAFETY) == "SAFE"

    def test_get_name_for_performance(self):
        """Test getting name for PERFORMANCE."""
        assert get_packet_type_name(PacketType.PERFORMANCE) == "PERF"

    def test_get_name_for_param_request(self):
        """Test getting name for PARAM_REQUEST."""
        assert get_packet_type_name(PacketType.PARAM_REQUEST) == "PARAM_REQ"

    def test_get_name_for_param_response(self):
        """Test getting name for PARAM_RESPONSE."""
        assert get_packet_type_name(PacketType.PARAM_RESPONSE) == "PARAM_RESP"

    def test_get_name_for_unknown_type(self):
        """Test getting name for unknown type."""
        assert get_packet_type_name(0xFF) == "UNKNOWN_0xFF"
