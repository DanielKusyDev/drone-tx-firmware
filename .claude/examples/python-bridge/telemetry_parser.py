"""
Enhanced Telemetry Parser
Parses binary telemetry packets from ESP32 drone firmware.
"""

import struct
from enum import IntEnum
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class TelemetryPacketType(IntEnum):
    """Telemetry packet types (must match firmware enum)."""
    ATTITUDE = 0x01
    CONTROL = 0x02
    MOTORS = 0x03
    STATUS = 0x04
    SENSORS = 0x05
    SAFETY = 0x06
    PERFORMANCE = 0x07


# Protocol constants
TELEM_ENHANCED_MAGIC = 0x5B
TELEM_ENHANCED_VERSION = 2

# Packet sizes (total including header and CRC)
PACKET_SIZES = {
    TelemetryPacketType.ATTITUDE: 24,
    TelemetryPacketType.CONTROL: 30,
    TelemetryPacketType.MOTORS: 31,
    TelemetryPacketType.STATUS: 24,
    TelemetryPacketType.SENSORS: 30,
    TelemetryPacketType.SAFETY: 20,
    TelemetryPacketType.PERFORMANCE: 22,
}


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
            if crc & 1:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return crc ^ 0xFFFF


class TelemetryHeader:
    """
    Common telemetry header (10 bytes).
    Format: <BBBBHHI (little-endian)
    """
    FORMAT = '<BBBBHI'  # magic, version, type, flags, seq, timestamp_us
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, data: bytes):
        """Parse header from bytes."""
        if len(data) < self.SIZE:
            raise ValueError(f"Header too short: {len(data)} < {self.SIZE}")

        unpacked = struct.unpack(self.FORMAT, data[:self.SIZE])
        self.magic = unpacked[0]
        self.version = unpacked[1]
        self.type = unpacked[2]
        self.flags = unpacked[3]
        self.seq = unpacked[4]
        self.timestamp_us = unpacked[5]

    def is_valid(self) -> bool:
        """Check if header is valid."""
        return (self.magic == TELEM_ENHANCED_MAGIC and
                self.version == TELEM_ENHANCED_VERSION)

    def __repr__(self) -> str:
        return (f"Header(magic=0x{self.magic:02X}, ver={self.version}, "
                f"type=0x{self.type:02X}, seq={self.seq}, ts={self.timestamp_us})")


class TelemetryParser:
    """
    Parser for Enhanced Telemetry packets.

    Usage:
        parser = TelemetryParser()
        packets = parser.feed(uart_data)
        for packet in packets:
            print(packet)
    """

    def __init__(self):
        """Initialize parser."""
        self.buffer = bytearray()
        self.stats = {
            'packets_parsed': 0,
            'crc_errors': 0,
            'unknown_types': 0,
            'invalid_headers': 0,
        }

    def feed(self, data: bytes) -> List[Dict[str, Any]]:
        """
        Feed data to parser.

        Args:
            data: Raw bytes from UART

        Returns:
            List of parsed packet dictionaries
        """
        self.buffer.extend(data)
        packets = []

        while True:
            packet = self._try_parse_packet()
            if packet is None:
                break
            packets.append(packet)

        # Trim buffer if too large (prevent memory growth)
        if len(self.buffer) > 4096:
            self._trim_buffer()

        return packets

    def _trim_buffer(self):
        """Trim buffer to prevent unbounded growth."""
        try:
            idx = self.buffer.index(TELEM_ENHANCED_MAGIC)
            self.buffer = self.buffer[idx:]
        except ValueError:
            # No magic byte found, clear buffer
            self.buffer.clear()

    def _try_parse_packet(self) -> Optional[Dict[str, Any]]:
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
            self.buffer.clear()
            return None

        # Discard bytes before magic
        if magic_idx > 0:
            logger.debug(f"Discarding {magic_idx} bytes before magic")
            self.buffer = self.buffer[magic_idx:]

        # Parse header
        if len(self.buffer) < TelemetryHeader.SIZE:
            return None

        try:
            header = TelemetryHeader(bytes(self.buffer[:TelemetryHeader.SIZE]))
        except Exception as e:
            logger.warning(f"Failed to parse header: {e}")
            self.buffer.pop(0)
            return None

        # Validate header
        if not header.is_valid():
            logger.debug(f"Invalid header: {header}")
            self.stats['invalid_headers'] += 1
            self.buffer.pop(0)
            return None

        # Check if we know this packet type
        try:
            packet_type = TelemetryPacketType(header.type)
        except ValueError:
            logger.warning(f"Unknown packet type: 0x{header.type:02X}")
            self.stats['unknown_types'] += 1
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
        crc_received = struct.unpack('<H', packet_data[-2:])[0]

        if crc_calculated != crc_received:
            logger.warning(
                f"CRC error for {packet_type.name}: "
                f"calc=0x{crc_calculated:04X} rcv=0x{crc_received:04X}"
            )
            self.stats['crc_errors'] += 1
            self.buffer.pop(0)
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

        self.stats['packets_parsed'] += 1
        return parsed

    def _parse_packet_payload(self, packet_type: TelemetryPacketType,
                               header: TelemetryHeader, data: bytes) -> Dict[str, Any]:
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
        else:
            # Unknown type (shouldn't reach here)
            return {
                'type': 'UNKNOWN',
                'ts_us': header.timestamp_us,
                'seq': header.seq,
            }

    def _parse_attitude(self, header: TelemetryHeader, data: bytes) -> Dict[str, Any]:
        """
        Parse ATTITUDE packet (24 bytes total).
        Payload: 6 x int16_t (12 bytes)
        """
        # Skip header (10 bytes), parse payload (12 bytes), skip CRC (2 bytes)
        payload = struct.unpack('<hhhhhh', data[10:22])

        return {
            'type': 'ATT',
            'ts_us': header.timestamp_us,
            'seq': header.seq,
            'roll_deg': payload[0] / 100.0,
            'pitch_deg': payload[1] / 100.0,
            'yaw_deg': payload[2] / 100.0,
            'roll_rate_dps': payload[3] / 10.0,
            'pitch_rate_dps': payload[4] / 10.0,
            'yaw_rate_dps': payload[5] / 10.0,
        }

    def _parse_motors(self, header: TelemetryHeader, data: bytes) -> Dict[str, Any]:
        """
        Parse MOTORS packet (31 bytes total).
        Payload: 8 x uint16_t + 1 x uint16_t + 1 x uint8_t (19 bytes)
        """
        # Skip header (10 bytes), parse payload (19 bytes), skip CRC (2 bytes)
        payload = struct.unpack('<HHHHHHHHB', data[10:29])

        return {
            'type': 'MOT',
            'ts_us': header.timestamp_us,
            'seq': header.seq,
            'motors': list(payload[0:4]),       # motor_cmd[4]
            'motors_actual': list(payload[4:8]), # motor_actual[4]
            'throttle': payload[8],
            'mixer_id': payload[9],
        }

    def _parse_status(self, header: TelemetryHeader, data: bytes) -> Dict[str, Any]:
        """
        Parse STATUS packet (24 bytes total).
        Payload: 6 x uint8_t + 1 x uint16_t + 1 x uint32_t (12 bytes)
        """
        # Skip header (10 bytes), parse payload (12 bytes), skip CRC (2 bytes)
        payload = struct.unpack('<BBBBBBHI', data[10:22])

        armed = payload[0]
        flight_mode = payload[1]
        safety_flags = payload[2]
        ground_state = payload[3]
        link_quality = payload[4]
        battery_pct = payload[5]
        uptime_s = payload[6]
        loop_rate_hz_x10 = payload[7]

        return {
            'type': 'STA',
            'ts_us': header.timestamp_us,
            'seq': header.seq,
            'armed': bool(armed),
            'mode': flight_mode,
            'ground_state': ground_state,
            'link_quality': link_quality,
            'battery_pct': battery_pct,
            'uptime_s': uptime_s,
            'loop_rate_hz': loop_rate_hz_x10 / 10.0,
            'flags': {
                'ARM': bool(armed),
                'HRZ': bool(safety_flags & 0x01),
                'LINK': bool(safety_flags & 0x02),
                'DISARM': bool(safety_flags & 0x04),
                'CAL': bool(safety_flags & 0x08),
                'CALIB': bool(safety_flags & 0x10),
                'FAIL': bool(safety_flags & 0x20),
            }
        }

    def _parse_control(self, header: TelemetryHeader, data: bytes) -> Dict[str, Any]:
        """
        Parse CONTROL packet (30 bytes total).
        Payload: 8 x int16_t + 2 x uint8_t (18 bytes)
        """
        payload = struct.unpack('<hhhhhhhhBB', data[10:28])

        return {
            'type': 'CTL',
            'ts_us': header.timestamp_us,
            'seq': header.seq,
            'set_roll_deg': payload[0] / 100.0,
            'set_pitch_deg': payload[1] / 100.0,
            'set_yaw_rate_dps': payload[2] / 10.0,
            'rate_set_roll_dps': payload[3] / 10.0,
            'rate_set_pitch_dps': payload[4] / 10.0,
            'out_roll': payload[5] / 10.0,
            'out_pitch': payload[6] / 10.0,
            'out_yaw': payload[7] / 10.0,
            'pid_gains_scale': payload[8] / 100.0,
            'throttle_gain_scale': payload[9] / 100.0,
        }

    def _parse_sensors(self, header: TelemetryHeader, data: bytes) -> Dict[str, Any]:
        """
        Parse SENSORS packet (30 bytes total).
        Payload: 9 x int16_t + 1 x int16_t (18 bytes)
        """
        payload = struct.unpack('<hhhhhhhhh', data[10:28])

        return {
            'type': 'SENS',
            'ts_us': header.timestamp_us,
            'seq': header.seq,
            'accel_mg': list(payload[0:3]),     # [x, y, z] in millig
            'gyro_mdps': list(payload[3:6]),    # [x, y, z] in milli-dps
            'mag_mgauss': list(payload[6:9]),   # [x, y, z] in milligauss
            'temperature_c': payload[9] / 10.0,
        }

    def _parse_safety(self, header: TelemetryHeader, data: bytes) -> Dict[str, Any]:
        """
        Parse SAFETY packet (20 bytes total).
        Payload: 2 x uint8_t + 1 x uint16_t + 1 x uint32_t + 1 x uint16_t (8 bytes)
        """
        payload = struct.unpack('<BBHIH', data[10:18])

        return {
            'type': 'SAFE',
            'ts_us': header.timestamp_us,
            'seq': header.seq,
            'ground_confidence': payload[0] / 100.0,
            'safety_gates': payload[1],
            'error_flags': payload[2],
            'total_flight_time_s': payload[3],
            'crash_count': payload[4],
        }

    def _parse_performance(self, header: TelemetryHeader, data: bytes) -> Dict[str, Any]:
        """
        Parse PERFORMANCE packet (22 bytes total).
        Payload: 3 x uint16_t + 1 x uint8_t + 1 x uint16_t + 1 x uint8_t (10 bytes)
        """
        payload = struct.unpack('<HHHBHB', data[10:20])

        return {
            'type': 'PERF',
            'ts_us': header.timestamp_us,
            'seq': header.seq,
            'loop_time_us': payload[0],
            'imu_time_us': payload[1],
            'control_time_us': payload[2],
            'cpu_usage_pct': payload[3],
            'free_heap_kb': payload[4],
            'stack_usage_pct': payload[5],
        }

    def get_stats(self) -> Dict[str, int]:
        """Get parser statistics."""
        return self.stats.copy()

    def reset_stats(self):
        """Reset statistics counters."""
        for key in self.stats:
            self.stats[key] = 0
