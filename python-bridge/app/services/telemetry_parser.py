"""
Enhanced Telemetry Parser
Parses binary telemetry packets from ESP32 drone firmware.
"""

import logging
import struct
from typing import Any

from app.utils.crc import crc16_x25
from app.utils.protocol import (
    MAGIC_BYTE,
    PACKET_SIZES,
    PROTOCOL_VERSION,
    PacketType,
)

logger = logging.getLogger(__name__)

# Backward compatibility aliases
TELEM_ENHANCED_MAGIC = MAGIC_BYTE
TELEM_ENHANCED_VERSION = PROTOCOL_VERSION
TelemetryPacketType = PacketType


class TelemetryHeader:
    """
    Common telemetry header (10 bytes).
    Format: <BBBBHI (little-endian)

    Fields:
        magic: 0x5B
        version: 2
        type: TelemetryPacketType (0x01-0x07)
        flags: Packet flags (compression, ack_req, etc.)
        seq: Sequence number (per packet type, wraps at 65535)
        timestamp_us: Microsecond timestamp from drone
    """

    FORMAT = "<BBBBHI"  # magic, version, type, flags, seq, timestamp_us
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, data: bytes):
        """Parse header from bytes."""
        if len(data) < self.SIZE:
            raise ValueError(f"Header too short: {len(data)} < {self.SIZE}")

        unpacked = struct.unpack(self.FORMAT, data[: self.SIZE])
        self.magic = unpacked[0]
        self.version = unpacked[1]
        self.type = unpacked[2]
        self.flags = unpacked[3]
        self.seq = unpacked[4]
        self.timestamp_us = unpacked[5]

    def is_valid(self) -> bool:
        """Check if header is valid."""
        return self.magic == MAGIC_BYTE and self.version == PROTOCOL_VERSION

    def __repr__(self) -> str:
        return (
            f"Header(magic=0x{self.magic:02X}, ver={self.version}, "
            f"type=0x{self.type:02X}, seq={self.seq}, ts={self.timestamp_us})"
        )


class TelemetryParser:
    """
    Parser for Enhanced Telemetry packets.

    This parser maintains an internal buffer and extracts complete packets
    as they arrive. It handles:
    - Magic byte synchronization
    - Header validation
    - CRC verification
    - Packet drop detection
    - Statistics tracking

    Usage:
        parser = TelemetryParser()

        # Feed incoming bytes
        packets = parser.feed(uart_data)

        # Process parsed packets
        for packet in packets:
            print(packet['type'], packet['seq'])

        # Check statistics
        stats = parser.get_stats()
        print(f"Parsed: {stats['packets_parsed']}, CRC errors: {stats['crc_errors']}")
    """

    def __init__(self):
        """Initialize parser with empty buffer and zero stats."""
        self.buffer = bytearray()
        self.stats = {
            "packets_parsed": 0,
            "crc_errors": 0,
            "unknown_types": 0,
            "invalid_headers": 0,
            "bytes_discarded": 0,
        }

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        """
        Feed data to parser.

        Args:
            data: Raw bytes from UART

        Returns:
            List of parsed packet dictionaries. Each packet has at minimum:
            - 'type': str - Packet type name (e.g., 'ATT', 'MOT', 'STA')
            - 'ts_us': int - Timestamp from drone in microseconds
            - 'seq': int - Sequence number
            Plus type-specific fields.
        """
        self.buffer.extend(data)
        packets = []

        # Keep parsing until we can't extract any more complete packets
        while True:
            packet = self._try_parse_packet()
            if packet is None:
                break
            packets.append(packet)

        # Trim buffer if too large (prevent unbounded memory growth)
        if len(self.buffer) > 4096:
            self._trim_buffer()

        return packets

    def _trim_buffer(self):
        """Trim buffer to prevent unbounded growth."""
        try:
            # Find next magic byte
            idx = self.buffer.index(TELEM_ENHANCED_MAGIC)
            discarded = idx
            self.buffer = self.buffer[idx:]
            self.stats["bytes_discarded"] += discarded
            if discarded > 0:
                logger.debug(f"Trimmed buffer: discarded {discarded} bytes")
        except ValueError:
            # No magic byte found, clear entire buffer
            discarded = len(self.buffer)
            self.buffer.clear()
            self.stats["bytes_discarded"] += discarded
            if discarded > 0:
                logger.warning(f"Buffer cleared: no magic byte found, discarded {discarded} bytes")

    def _try_parse_packet(self) -> dict[str, Any] | None:
        """
        Try to parse one packet from buffer.

        Returns:
            Parsed packet dict or None if not enough data
        """
        # Need at least header to proceed
        if len(self.buffer) < TelemetryHeader.SIZE:
            return None

        # Find magic byte
        try:
            magic_idx = self.buffer.index(TELEM_ENHANCED_MAGIC)
        except ValueError:
            # No magic byte found, clear buffer
            discarded = len(self.buffer)
            self.buffer.clear()
            self.stats["bytes_discarded"] += discarded
            return None

        # Discard bytes before magic
        if magic_idx > 0:
            logger.debug(f"Discarding {magic_idx} bytes before magic")
            self.stats["bytes_discarded"] += magic_idx
            self.buffer = self.buffer[magic_idx:]

        # Parse header
        if len(self.buffer) < TelemetryHeader.SIZE:
            return None

        try:
            header = TelemetryHeader(bytes(self.buffer[: TelemetryHeader.SIZE]))
        except Exception as e:
            logger.warning(f"Failed to parse header: {e}")
            self.buffer.pop(0)  # Skip this byte and try next
            return None

        # Validate header
        if not header.is_valid():
            logger.debug(f"Invalid header: {header}")
            self.stats["invalid_headers"] += 1
            self.buffer.pop(0)
            return None

        # Check if we know this packet type
        try:
            packet_type = TelemetryPacketType(header.type)
        except ValueError:
            logger.warning(f"Unknown packet type: 0x{header.type:02X}")
            self.stats["unknown_types"] += 1
            self.buffer.pop(0)
            return None

        # Check if we have full packet
        expected_size = PACKET_SIZES[packet_type]
        if len(self.buffer) < expected_size:
            return None  # Wait for more data

        # Extract packet
        packet_data = bytes(self.buffer[:expected_size])

        # Validate CRC
        crc_calculated = crc16_x25(packet_data[:-2])
        crc_received = struct.unpack("<H", packet_data[-2:])[0]

        if crc_calculated != crc_received:
            logger.warning(f"CRC error for {packet_type.name}: calc=0x{crc_calculated:04X} rcv=0x{crc_received:04X}")
            self.stats["crc_errors"] += 1
            self.buffer.pop(0)  # Skip this byte
            return None

        # Parse payload
        try:
            parsed = self._parse_packet_payload(packet_type, header, packet_data)
        except Exception as e:
            logger.error(f"Failed to parse {packet_type.name} payload: {e}")
            self.buffer.pop(0)
            return None

        # Remove parsed packet from buffer
        self.buffer = self.buffer[expected_size:]

        self.stats["packets_parsed"] += 1
        return parsed

    def _parse_packet_payload(
        self, packet_type: TelemetryPacketType, header: TelemetryHeader, data: bytes
    ) -> dict[str, Any]:
        """
        Parse payload based on packet type.

        Args:
            packet_type: Type of packet
            header: Parsed header
            data: Full packet data (including header and CRC)

        Returns:
            Parsed packet dictionary
        """
        if packet_type == TelemetryPacketType.ATTITUDE:
            return self._parse_attitude(header, data)
        elif packet_type == TelemetryPacketType.MOTORS:
            return self._parse_motors(header, data)
        elif packet_type == TelemetryPacketType.STATUS:
            return self._parse_status(header, data)
        elif packet_type == TelemetryPacketType.CONTROL:
            return self._parse_control(header, data)
        elif packet_type == TelemetryPacketType.SENSORS:
            return self._parse_sensors(header, data)
        elif packet_type == TelemetryPacketType.SAFETY:
            return self._parse_safety(header, data)
        elif packet_type == TelemetryPacketType.PERFORMANCE:
            return self._parse_performance(header, data)
        elif packet_type == TelemetryPacketType.PARAM_REQUEST:
            return self._parse_param_request(header, data)
        elif packet_type == TelemetryPacketType.PARAM_RESPONSE:
            return self._parse_param_response(header, data)
        else:
            # Unknown type (shouldn't reach here due to earlier check)
            return {
                "type": "UNKNOWN",
                "ts_us": header.timestamp_us,
                "seq": header.seq,
            }

    def _parse_attitude(self, header: TelemetryHeader, data: bytes) -> dict[str, Any]:
        """
        Parse ATTITUDE packet (24 bytes total).

        Payload (12 bytes):
            roll_deg_x100: int16 (roll angle x 100)
            pitch_deg_x100: int16 (pitch angle x 100)
            yaw_deg_x100: int16 (yaw angle x 100)
            roll_rate_dps_x10: int16 (roll rate x 10)
            pitch_rate_dps_x10: int16 (pitch rate x 10)
            yaw_rate_dps_x10: int16 (yaw rate x 10)
        """
        # Skip header (10 bytes), parse payload (12 bytes), skip CRC (2 bytes)
        payload = struct.unpack("<hhhhhh", data[10:22])

        return {
            "type": "ATT",
            "ts_us": header.timestamp_us,
            "seq": header.seq,
            "roll_deg": payload[0] / 100.0,
            "pitch_deg": payload[1] / 100.0,
            "yaw_deg": payload[2] / 100.0,
            "roll_rate_dps": payload[3] / 10.0,
            "pitch_rate_dps": payload[4] / 10.0,
            "yaw_rate_dps": payload[5] / 10.0,
        }

    def _parse_motors(self, header: TelemetryHeader, data: bytes) -> dict[str, Any]:
        """
        Parse MOTORS packet (31 bytes total).

        Payload (19 bytes):
            motor_cmd[4]: uint16[4] (motor commands)
            motor_actual[4]: uint16[4] (actual outputs)
            throttle: uint16
            mixer_table_id: uint8
        """
        # Skip header (10 bytes), parse payload (19 bytes), skip CRC (2 bytes)
        payload = struct.unpack("<HHHHHHHHHB", data[10:29])

        return {
            "type": "MOT",
            "ts_us": header.timestamp_us,
            "seq": header.seq,
            "motors": list(payload[0:4]),  # motor_cmd[4]
            "motors_actual": list(payload[4:8]),  # motor_actual[4]
            "throttle": payload[8],
            "mixer_id": payload[9],
        }

    def _parse_status(self, header: TelemetryHeader, data: bytes) -> dict[str, Any]:
        """
        Parse STATUS packet (24 bytes total).

        Payload (12 bytes):
            armed: uint8
            flight_mode: uint8
            safety_flags: uint8 (bitfield)
            ground_state: uint8
            link_quality: uint8
            battery_pct: uint8
            uptime_s: uint16
            loop_rate_hz_x10: uint32
        """
        # Skip header (10 bytes), parse payload (12 bytes), skip CRC (2 bytes)
        payload = struct.unpack("<BBBBBBHI", data[10:22])

        armed = payload[0]
        flight_mode = payload[1]
        safety_flags = payload[2]
        ground_state = payload[3]
        link_quality = payload[4]
        battery_pct = payload[5]
        uptime_s = payload[6]
        loop_rate_hz_x10 = payload[7]

        return {
            "type": "STA",
            "ts_us": header.timestamp_us,
            "seq": header.seq,
            "armed": bool(armed),
            "mode": flight_mode,
            "ground_state": ground_state,
            "link_quality": link_quality,
            "battery_pct": battery_pct,
            "uptime_s": uptime_s,
            "loop_rate_hz": loop_rate_hz_x10 / 10.0,
            "flags": {
                "ARM": bool(armed),
                "HRZ": bool(safety_flags & 0x01),  # bit 0: TELEM_HORIZON_BIT
                "DISARM": bool(safety_flags & 0x02),  # bit 1: TELEM_FORCE_DISARM
                "CALIB": bool(safety_flags & 0x04),  # bit 2: TELEM_FLAG_CALIBRATING
                "LOBAT": bool(safety_flags & 0x08),  # bit 3: TELEM_LOW_BATTERY
                "SENS": bool(safety_flags & 0x10),  # bit 4: TELEM_SENSOR_FAILURE
                "FS": bool(safety_flags & 0x20),  # bit 5: TELEM_FAILSAFE_ACTIVE
                "ANG": bool(safety_flags & 0x40),  # bit 6: TELEM_ANGLE_LIMIT_EXCEEDED
            },
        }

    def _parse_control(self, header: TelemetryHeader, data: bytes) -> dict[str, Any]:
        """
        Parse CONTROL packet (30 bytes total).

        Payload (18 bytes):
            set_roll_deg_x100: int16
            set_pitch_deg_x100: int16
            set_yaw_rate_dps_x10: int16
            rate_set_roll_dps_x10: int16
            rate_set_pitch_dps_x10: int16
            out_roll_x10: int16
            out_pitch_x10: int16
            out_yaw_x10: int16
            pid_gains_scale_x100: uint8
            throttle_gain_scale_x100: uint8
        """
        payload = struct.unpack("<hhhhhhhhBB", data[10:28])

        return {
            "type": "CTL",
            "ts_us": header.timestamp_us,
            "seq": header.seq,
            "set_roll_deg": payload[0] / 100.0,
            "set_pitch_deg": payload[1] / 100.0,
            "set_yaw_rate_dps": payload[2] / 10.0,
            "rate_set_roll_dps": payload[3] / 10.0,
            "rate_set_pitch_dps": payload[4] / 10.0,
            "out_roll": payload[5] / 10.0,
            "out_pitch": payload[6] / 10.0,
            "out_yaw": payload[7] / 10.0,
            "pid_gains_scale": payload[8] / 100.0,
            "throttle_gain_scale": payload[9] / 100.0,
        }

    def _parse_sensors(self, header: TelemetryHeader, data: bytes) -> dict[str, Any]:
        """
        Parse SENSORS packet (30 bytes total).

        Payload (18 bytes):
            accel_mg[3]: int16[3] (millig)
            gyro_mdps[3]: int16[3] (milli-dps)
            mag_mgauss[3]: int16[3] (milligauss)
            temperature_c_x10: int16
        """
        payload = struct.unpack("<hhhhhhhhhh", data[10:28])

        return {
            "type": "SENS",
            "ts_us": header.timestamp_us,
            "seq": header.seq,
            "accel_mg": list(payload[0:3]),  # [x, y, z] in millig
            "gyro_mdps": list(payload[3:6]),  # [x, y, z] in milli-dps
            "mag_mgauss": list(payload[6:9]),  # [x, y, z] in milligauss
            "temperature_c": payload[9] / 10.0,
        }

    def _parse_safety(self, header: TelemetryHeader, data: bytes) -> dict[str, Any]:
        """
        Parse SAFETY packet (20 bytes total).

        Payload (8 bytes):
            ground_confidence_x100: uint8
            safety_gates: uint8
            error_flags: uint16
            total_flight_time_s: uint32
            crash_count: uint16
        """
        payload = struct.unpack("<BBHIH", data[10:18])

        return {
            "type": "SAFE",
            "ts_us": header.timestamp_us,
            "seq": header.seq,
            "ground_confidence": payload[0] / 100.0,
            "safety_gates": payload[1],
            "error_flags": payload[2],
            "total_flight_time_s": payload[3],
            "crash_count": payload[4],
        }

    def _parse_performance(self, header: TelemetryHeader, data: bytes) -> dict[str, Any]:
        """
        Parse PERFORMANCE packet (22 bytes total).

        Payload (10 bytes):
            loop_time_us: uint16
            imu_time_us: uint16
            control_time_us: uint16
            cpu_usage_pct: uint8
            free_heap_kb: uint16
            stack_usage_pct: uint8
        """
        payload = struct.unpack("<HHHBHB", data[10:20])

        return {
            "type": "PERF",
            "ts_us": header.timestamp_us,
            "seq": header.seq,
            "loop_time_us": payload[0],
            "imu_time_us": payload[1],
            "control_time_us": payload[2],
            "cpu_usage_pct": payload[3],
            "free_heap_kb": payload[4],
            "stack_usage_pct": payload[5],
        }

    def _parse_param_request(self, header: TelemetryHeader, data: bytes) -> dict[str, Any]:
        """
        Parse PARAM_REQUEST packet (18 bytes total).

        Header: 10 bytes (packed, NO padding)
        Payload: 6 bytes
            command: uint8 (PARAM_CMD_LIST/GET/SET)
            param_index: uint8
            value: float (for SET commands)
        CRC: 2 bytes

        Note: PARAM_REQUEST is typically sent FROM controller TO drone,
        so receiving it here might indicate UART echo/loopback.
        TX firmware does NOT currently support PARAM forwarding.
        """
        return {
            "type": "PARAM_REQ",
            "ts_us": header.timestamp_us,
            "seq": header.seq,
            "raw_data": data,  # Include raw data for UnifiedBridge processing
        }

    def _parse_param_response(self, header: TelemetryHeader, data: bytes) -> dict[str, Any]:
        """
        Parse PARAM_RESPONSE packet (54 bytes total).

        Header: 10 bytes (packed, NO padding)
        Payload: 42 bytes
            command: uint8 (response command code)
            param_index: uint8
            param_type: uint8
            param_access: uint8
            value: float
            group: char[16]
            name: char[16]
            total_params: uint8
            error_code: uint8
        CRC: 2 bytes

        Note: TX firmware does NOT currently support PARAM forwarding.
        This packet type will only be received if drone firmware is connected
        directly via UART (not through TX).
        """
        return {
            "type": "PARAM_RESP",
            "ts_us": header.timestamp_us,
            "seq": header.seq,
            "raw_data": data,  # Include raw data for UnifiedBridge processing
        }

    def get_stats(self) -> dict[str, int]:
        """
        Get parser statistics.

        Returns:
            Dictionary with keys:
            - packets_parsed: Total successfully parsed packets
            - crc_errors: CRC validation failures
            - unknown_types: Unknown packet type IDs
            - invalid_headers: Invalid header magic/version
            - bytes_discarded: Bytes discarded during sync
        """
        return self.stats.copy()

    def reset_stats(self):
        """Reset all statistics counters to zero."""
        for key in self.stats:
            self.stats[key] = 0

    def clear_buffer(self):
        """Clear internal buffer (useful for testing or reset)."""
        self.buffer.clear()


if __name__ == "__main__":
    # Simple smoke test
    logging.basicConfig(level=logging.DEBUG)

    parser = TelemetryParser()

    # Create a fake ATTITUDE packet
    import io

    buf = io.BytesIO()

    # Header
    buf.write(
        struct.pack(
            "<BBBBHI",
            0x5B,  # magic
            2,  # version
            0x01,  # type (ATTITUDE)
            0x00,  # flags
            42,  # seq
            123456789,  # timestamp_us
        )
    )

    # Payload (6 x int16)
    buf.write(
        struct.pack(
            "<hhhhhh",
            -898,  # roll (*100) = -8.98°
            924,  # pitch (*100) = 9.24°
            0,  # yaw
            -205,  # roll rate (*10) = -20.5°/s
            115,  # pitch rate (*10) = 11.5°/s
            0,  # yaw rate
        )
    )

    # Calculate and write CRC
    packet_data = buf.getvalue()
    crc = crc16_x25(packet_data)
    buf.write(struct.pack("<H", crc))

    # Parse
    packets = parser.feed(buf.getvalue())

    if packets:
        print("✅ Parser smoke test passed!")
        print(f"Parsed packet: {packets[0]}")
        print(f"Stats: {parser.get_stats()}")
    else:
        print("❌ Parser smoke test failed!")
