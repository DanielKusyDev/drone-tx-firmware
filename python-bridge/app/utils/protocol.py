"""
Protocol constants for ESP32 telemetry communication.

These constants must match the firmware implementation exactly.
See: firmware include/protocol.h
"""

from enum import IntEnum

# === Protocol Version ===

MAGIC_BYTE = 0x5B
PROTOCOL_VERSION = 2

# === Packet Types ===


class PacketType(IntEnum):
    """Telemetry packet types (must match firmware enum)."""

    # Telemetry packets (0x01-0x07)
    ATTITUDE = 0x01  # Roll, pitch, yaw + rates
    CONTROL = 0x02  # PID outputs and setpoints
    MOTORS = 0x03  # Motor outputs and mixer
    STATUS = 0x04  # System status and diagnostics
    SENSORS = 0x05  # Raw sensor data (IMU)
    SAFETY = 0x06  # Safety and ground detection
    PERFORMANCE = 0x07  # Timing and performance metrics

    # PARAM packets (0x10-0x11)
    PARAM_REQUEST = 0x10  # Parameter request (Python → ESP32)
    PARAM_RESPONSE = 0x11  # Parameter response (ESP32 → Python)


# === Packet Sizes (total including header + payload + CRC) ===

PACKET_SIZES = {
    PacketType.ATTITUDE: 24,  # 10 header + 12 payload + 2 CRC
    PacketType.CONTROL: 30,  # 10 header + 18 payload + 2 CRC
    PacketType.MOTORS: 31,  # 10 header + 19 payload + 2 CRC
    PacketType.STATUS: 24,  # 10 header + 12 payload + 2 CRC
    PacketType.SENSORS: 30,  # 10 header + 18 payload + 2 CRC
    PacketType.SAFETY: 20,  # 10 header + 8 payload + 2 CRC
    PacketType.PERFORMANCE: 22,  # 10 header + 10 payload + 2 CRC
    PacketType.PARAM_REQUEST: 18,  # 10 header + 6 payload + 2 CRC (NO padding)
    PacketType.PARAM_RESPONSE: 54,  # 10 header + 42 payload + 2 CRC (NO padding)
}

# === PARAM Command Codes ===


class ParamCommand(IntEnum):
    """PARAM protocol command codes."""

    # Request commands (Python → ESP32)
    LIST = 0x01  # List parameter info
    GET = 0x02  # Get parameter value
    SET = 0x03  # Set parameter value

    # Response commands (ESP32 → Python)
    LIST_RESP = 0x81  # List response
    GET_RESP = 0x82  # Get response
    SET_RESP = 0x83  # Set response
    ERROR = 0xFF  # Error response


# === PARAM Error Codes ===


class ParamError(IntEnum):
    """PARAM protocol error codes."""

    INDEX_OUT_OF_RANGE = 1
    PARAM_NOT_FOUND = 2
    READ_FAILED = 3
    WRITE_FAILED = 4
    UNKNOWN_COMMAND = 5


# === Packet Type Helpers ===


def is_telemetry_packet(packet_type: int) -> bool:
    """Check if packet type is telemetry (0x01-0x07)."""
    return 0x01 <= packet_type <= 0x07


def is_param_packet(packet_type: int) -> bool:
    """Check if packet type is PARAM (0x10-0x11)."""
    return packet_type in (PacketType.PARAM_REQUEST, PacketType.PARAM_RESPONSE)


def get_packet_type_name(packet_type: int) -> str:
    """
    Get human-readable packet type name.

    Args:
        packet_type: Packet type byte (0x01-0x11)

    Returns:
        Short name (e.g., 'ATT', 'MOT', 'PARAM_RESP')
    """
    names = {
        PacketType.ATTITUDE: "ATT",
        PacketType.CONTROL: "CTL",
        PacketType.MOTORS: "MOT",
        PacketType.STATUS: "STA",
        PacketType.SENSORS: "SENS",
        PacketType.SAFETY: "SAFE",
        PacketType.PERFORMANCE: "PERF",
        PacketType.PARAM_REQUEST: "PARAM_REQ",
        PacketType.PARAM_RESPONSE: "PARAM_RESP",
    }
    return names.get(packet_type, f"UNKNOWN_0x{packet_type:02X}")
