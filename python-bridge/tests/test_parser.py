"""
Pytest test suite for telemetry parser.
Tests binary packet parsing, CRC validation, and error handling.

Run with:
    pytest tests/test_parser.py -v
    pytest tests/test_parser.py -v -k "attitude"  # Run only attitude tests
    pytest tests/test_parser.py -v --cov=app.services.telemetry_parser

Author: Claude + Daniel
Date: 2025-12-14
"""

import struct
from io import BytesIO

import pytest

from app.services.telemetry_parser import (
    TELEM_ENHANCED_MAGIC,
    TELEM_ENHANCED_VERSION,
    TelemetryPacketType,
    TelemetryParser,
)
from app.utils.crc import crc16_x25

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def parser():
    """Create a fresh parser instance for each test."""
    return TelemetryParser()


@pytest.fixture
def attitude_packet():
    """Create a valid ATTITUDE packet with default values."""
    return _create_attitude_packet(seq=42)


@pytest.fixture
def motors_packet():
    """Create a valid MOTORS packet with default values."""
    return _create_motors_packet(seq=100)


@pytest.fixture
def status_packet():
    """Create a valid STATUS packet with default values."""
    return _create_status_packet(seq=200)


# ============================================================================
# Packet Factory Functions
# ============================================================================


def _create_attitude_packet(seq: int = 42, roll_deg: float = -8.98, pitch_deg: float = 9.24) -> bytes:
    """
    Create a test ATTITUDE packet.

    Args:
        seq: Sequence number
        roll_deg: Roll angle in degrees
        pitch_deg: Pitch angle in degrees

    Returns:
        Complete binary packet with valid CRC
    """
    buf = BytesIO()

    # Header (10 bytes)
    buf.write(
        struct.pack(
            "<BBBBHI",
            TELEM_ENHANCED_MAGIC,
            TELEM_ENHANCED_VERSION,
            TelemetryPacketType.ATTITUDE,
            0x00,  # flags
            seq,
            123456789,  # timestamp_us
        )
    )

    # Payload (12 bytes): 6 x int16
    buf.write(
        struct.pack(
            "<hhhhhh",
            int(roll_deg * 100),  # roll (*100)
            int(pitch_deg * 100),  # pitch (*100)
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

    return buf.getvalue()


def _create_motors_packet(seq: int = 100) -> bytes:
    """Create a test MOTORS packet."""
    buf = BytesIO()

    # Header (10 bytes)
    buf.write(
        struct.pack(
            "<BBBBHI",
            TELEM_ENHANCED_MAGIC,
            TELEM_ENHANCED_VERSION,
            TelemetryPacketType.MOTORS,
            0x00,
            seq,
            123456800,
        )
    )

    # Payload (19 bytes)
    buf.write(
        struct.pack(
            "<HHHHHHHHHB",
            0,  # motor_cmd[0]
            5120,  # motor_cmd[1]
            31488,  # motor_cmd[2]
            4864,  # motor_cmd[3]
            0,  # motor_actual[0]
            5120,  # motor_actual[1]
            31488,  # motor_actual[2]
            4864,  # motor_actual[3]
            2686,  # throttle
            0,  # mixer_id
        )
    )

    # CRC
    packet_data = buf.getvalue()
    crc = crc16_x25(packet_data)
    buf.write(struct.pack("<H", crc))

    return buf.getvalue()


def _create_status_packet(seq: int = 200) -> bytes:
    """Create a test STATUS packet."""
    buf = BytesIO()

    # Header (10 bytes)
    buf.write(
        struct.pack(
            "<BBBBHI",
            TELEM_ENHANCED_MAGIC,
            TELEM_ENHANCED_VERSION,
            TelemetryPacketType.STATUS,
            0x00,
            seq,
            123456820,
        )
    )

    # Payload (12 bytes)
    safety_flags = 0x01 | 0x04 | 0x10  # HRZ | CALIB | SENS
    buf.write(
        struct.pack(
            "<BBBBBBHI",
            1,  # armed
            0,  # flight_mode
            safety_flags,
            0,  # ground_state
            100,  # link_quality
            85,  # battery_pct
            45,  # uptime_s
            5000,  # loop_rate_hz_x10 (500.0 Hz)
        )
    )

    # CRC
    packet_data = buf.getvalue()
    crc = crc16_x25(packet_data)
    buf.write(struct.pack("<H", crc))

    return buf.getvalue()


# ============================================================================
# Basic Parsing Tests
# ============================================================================


class TestBasicParsing:
    """Test basic packet parsing functionality."""

    def test_single_attitude_packet(self, parser, attitude_packet):
        """Test parsing a single ATTITUDE packet."""
        packets = parser.feed(attitude_packet)

        assert len(packets) == 1
        pkt = packets[0]

        assert pkt["type"] == "ATT"
        assert pkt["seq"] == 42
        assert pkt["ts_us"] == 123456789
        assert abs(pkt["roll_deg"] - (-8.98)) < 0.01
        assert abs(pkt["pitch_deg"] - 9.24) < 0.01
        assert abs(pkt["roll_rate_dps"] - (-20.5)) < 0.01
        assert abs(pkt["pitch_rate_dps"] - 11.5) < 0.01

    def test_single_motors_packet(self, parser, motors_packet):
        """Test parsing a single MOTORS packet."""
        packets = parser.feed(motors_packet)

        assert len(packets) == 1
        pkt = packets[0]

        assert pkt["type"] == "MOT"
        assert pkt["seq"] == 100
        assert pkt["throttle"] == 2686
        assert pkt["motors"] == [0, 5120, 31488, 4864]
        assert pkt["motors_actual"] == [0, 5120, 31488, 4864]
        assert pkt["mixer_id"] == 0

    def test_single_status_packet(self, parser, status_packet):
        """Test parsing a single STATUS packet."""
        packets = parser.feed(status_packet)

        assert len(packets) == 1
        pkt = packets[0]

        assert pkt["type"] == "STA"
        assert pkt["seq"] == 200
        assert pkt["armed"] is True
        assert pkt["link_quality"] == 100
        assert pkt["battery_pct"] == 85
        assert pkt["loop_rate_hz"] == 500.0
        assert pkt["flags"]["HRZ"] is True
        assert pkt["flags"]["CALIB"] is True
        assert pkt["flags"]["SENS"] is True

    def test_multiple_packets_in_stream(self, parser):
        """Test parsing multiple packets in one feed."""
        stream = b""
        stream += _create_attitude_packet(seq=1)
        stream += _create_motors_packet(seq=2)
        stream += _create_status_packet(seq=3)

        packets = parser.feed(stream)

        assert len(packets) == 3
        assert packets[0]["type"] == "ATT"
        assert packets[0]["seq"] == 1
        assert packets[1]["type"] == "MOT"
        assert packets[1]["seq"] == 2
        assert packets[2]["type"] == "STA"
        assert packets[2]["seq"] == 3


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Test parser error handling and edge cases."""

    def test_garbage_data_before_packet(self, parser):
        """Test that parser skips garbage data before valid packet."""
        garbage = b"\xff\xff\x00\x00\xaa\xbb\xcc\xdd"
        stream = garbage + _create_attitude_packet()

        packets = parser.feed(stream)

        assert len(packets) == 1
        assert packets[0]["type"] == "ATT"

        stats = parser.get_stats()
        assert stats["bytes_discarded"] >= len(garbage)

    def test_crc_error_detection(self, parser):
        """Test that parser rejects packets with invalid CRC."""
        packet_data = bytearray(_create_attitude_packet())

        # Corrupt CRC (last byte)
        packet_data[-1] ^= 0xFF

        packets = parser.feed(bytes(packet_data))

        assert len(packets) == 0  # Should reject packet

        stats = parser.get_stats()
        assert stats["crc_errors"] > 0
        assert stats["packets_parsed"] == 0

    def test_partial_packet_buffering(self, parser):
        """Test that parser buffers partial packets correctly."""
        full_packet = _create_attitude_packet()

        # Feed only header (first 10 bytes)
        packets = parser.feed(full_packet[:10])
        assert len(packets) == 0  # Should not parse partial packet

        # Feed rest of packet
        packets = parser.feed(full_packet[10:])
        assert len(packets) == 1
        assert packets[0]["type"] == "ATT"

    def test_invalid_magic_byte(self, parser):
        """Test that parser rejects packets with invalid magic byte."""
        buf = BytesIO()
        buf.write(
            struct.pack(
                "<BBBBHI",
                0xFF,  # Invalid magic byte
                TELEM_ENHANCED_VERSION,
                TelemetryPacketType.ATTITUDE,
                0x00,
                42,
                123456789,
            )
        )
        buf.write(b"\x00" * 12)  # Dummy payload
        packet_data = buf.getvalue()
        crc = crc16_x25(packet_data)
        buf.write(struct.pack("<H", crc))

        packets = parser.feed(buf.getvalue())

        assert len(packets) == 0
        stats = parser.get_stats()
        assert stats["invalid_headers"] > 0

    def test_unknown_packet_type(self, parser):
        """Test that parser handles unknown packet types gracefully."""
        buf = BytesIO()
        buf.write(
            struct.pack(
                "<BBBBHI",
                TELEM_ENHANCED_MAGIC,
                TELEM_ENHANCED_VERSION,
                0xFF,  # Unknown packet type
                0x00,
                42,
                123456789,
            )
        )

        packets = parser.feed(buf.getvalue())

        assert len(packets) == 0
        stats = parser.get_stats()
        assert stats["unknown_types"] > 0


# ============================================================================
# Statistics Tests
# ============================================================================


class TestStatistics:
    """Test parser statistics tracking."""

    def test_statistics_tracking(self, parser):
        """Test that parser tracks statistics correctly."""
        # Parse multiple packets
        for i in range(10):
            packet = _create_attitude_packet(seq=i)
            parser.feed(packet)

        stats = parser.get_stats()

        assert stats["packets_parsed"] == 10
        assert stats["crc_errors"] == 0
        assert stats["unknown_types"] == 0
        assert stats["invalid_headers"] == 0

    def test_statistics_reset(self, parser):
        """Test that parser statistics can be reset."""
        # Parse some packets
        for i in range(5):
            parser.feed(_create_attitude_packet(seq=i))

        stats_before = parser.get_stats()
        assert stats_before["packets_parsed"] == 5

        # Reset
        parser.reset_stats()

        stats_after = parser.get_stats()
        assert stats_after["packets_parsed"] == 0
        assert stats_after["crc_errors"] == 0

    def test_error_statistics_increment(self, parser):
        """Test that error counters increment correctly."""
        # Feed garbage data
        parser.feed(b"\xff\xff\xff\xff")

        # Feed packet with bad CRC
        bad_packet = bytearray(_create_attitude_packet())
        bad_packet[-1] ^= 0xFF
        parser.feed(bytes(bad_packet))

        stats = parser.get_stats()
        assert stats["crc_errors"] >= 1
        assert stats["bytes_discarded"] >= 4


# ============================================================================
# Parametrized Tests
# ============================================================================


class TestParametrized:
    """Parametrized tests for various scenarios."""

    @pytest.mark.parametrize(
        "seq,roll,pitch",
        [
            (0, 0.0, 0.0),
            (1, 10.5, -5.3),
            (100, -45.0, 45.0),
            (65535, 89.99, -89.99),
        ],
    )
    def test_attitude_packet_values(self, parser, seq, roll, pitch):
        """Test ATTITUDE packet with various values."""
        packet = _create_attitude_packet(seq=seq, roll_deg=roll, pitch_deg=pitch)
        packets = parser.feed(packet)

        assert len(packets) == 1
        pkt = packets[0]

        assert pkt["seq"] == seq
        assert abs(pkt["roll_deg"] - roll) < 0.01
        assert abs(pkt["pitch_deg"] - pitch) < 0.01

    @pytest.mark.parametrize(
        "garbage_size",
        [1, 5, 10, 100, 1000],
    )
    def test_garbage_data_various_sizes(self, parser, garbage_size):
        """Test parser handles various sizes of garbage data."""
        garbage = b"\xff" * garbage_size
        stream = garbage + _create_attitude_packet()

        packets = parser.feed(stream)

        assert len(packets) == 1
        stats = parser.get_stats()
        assert stats["bytes_discarded"] >= garbage_size

    @pytest.mark.parametrize(
        "split_point",
        [1, 5, 10, 15, 20],
    )
    def test_partial_packets_split_points(self, parser, split_point):
        """Test partial packet handling at various split points."""
        packet = _create_attitude_packet()

        # Feed first part
        packets1 = parser.feed(packet[:split_point])
        assert len(packets1) == 0

        # Feed second part
        packets2 = parser.feed(packet[split_point:])
        assert len(packets2) == 1


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_mixed_packet_stream(self, parser):
        """Test parsing a realistic stream with mixed packet types."""
        stream = b""

        # Add 5 attitude packets
        for i in range(5):
            stream += _create_attitude_packet(seq=i)

        # Add 2 motors packets
        for i in range(2):
            stream += _create_motors_packet(seq=100 + i)

        # Add 1 status packet
        stream += _create_status_packet(seq=200)

        packets = parser.feed(stream)

        assert len(packets) == 8

        # Verify packet types
        att_packets = [p for p in packets if p["type"] == "ATT"]
        mot_packets = [p for p in packets if p["type"] == "MOT"]
        sta_packets = [p for p in packets if p["type"] == "STA"]

        assert len(att_packets) == 5
        assert len(mot_packets) == 2
        assert len(sta_packets) == 1

    def test_incremental_feed_realistic_scenario(self, parser):
        """Test incremental feeding simulating serial port reads."""
        full_stream = b""
        for i in range(10):
            full_stream += _create_attitude_packet(seq=i)

        # Feed in chunks of 50 bytes (simulating serial reads)
        chunk_size = 50
        all_packets = []

        for i in range(0, len(full_stream), chunk_size):
            chunk = full_stream[i : i + chunk_size]
            packets = parser.feed(chunk)
            all_packets.extend(packets)

        assert len(all_packets) == 10
        assert all_packets[0]["seq"] == 0
        assert all_packets[-1]["seq"] == 9

    def test_robustness_with_errors_and_valid_data(self, parser):
        """Test parser continues working after encountering errors."""
        stream = b""

        # Add garbage
        stream += b"\xff\xff\xff\xff"

        # Add valid packet
        stream += _create_attitude_packet(seq=1)

        # Add packet with bad CRC
        bad_packet = bytearray(_create_motors_packet(seq=2))
        bad_packet[-1] ^= 0xFF
        stream += bytes(bad_packet)

        # Add another valid packet
        stream += _create_status_packet(seq=3)

        # Feed all data
        all_packets = parser.feed(stream)

        # Parser stops after CRC error, need to feed again to get remaining packets
        # (simulates real-world incremental feeding)
        # Keep feeding empty bytes until buffer is empty
        max_iterations = 100  # Safety limit
        for _ in range(max_iterations):
            more_packets = parser.feed(b"")
            if more_packets:
                all_packets.extend(more_packets)
            # Stop when buffer is fully processed
            if len(parser.buffer) == 0:
                break

        # Should get 2 valid packets (seq 1 and 3)
        assert len(all_packets) == 2
        assert all_packets[0]["seq"] == 1
        assert all_packets[1]["seq"] == 3

        # Check stats show errors
        stats = parser.get_stats()
        assert stats["packets_parsed"] == 2
        assert stats["crc_errors"] >= 1
        assert stats["bytes_discarded"] >= 4


# ============================================================================
# Performance Tests (marked as slow)
# ============================================================================


@pytest.mark.slow
class TestPerformance:
    """Performance tests (run with: pytest -m slow)."""

    def test_large_packet_stream(self, parser):
        """Test parsing a large stream of packets."""
        stream = b""
        num_packets = 1000

        for i in range(num_packets):
            stream += _create_attitude_packet(seq=i)

        packets = parser.feed(stream)

        assert len(packets) == num_packets
        assert packets[0]["seq"] == 0
        assert packets[-1]["seq"] == num_packets - 1

    def test_parser_with_large_buffer(self, parser):
        """Test parser doesn't leak memory with large garbage buffer."""
        # Feed 10KB of garbage followed by valid packet
        garbage = b"\xff" * 10000
        stream = garbage + _create_attitude_packet()

        packets = parser.feed(stream)

        assert len(packets) == 1
        stats = parser.get_stats()
        assert stats["bytes_discarded"] >= 10000


# ============================================================================
# CRC Utility Tests
# ============================================================================


class TestCRCUtility:
    """Test CRC-16/X.25 calculation function."""

    def test_crc_calculation_deterministic(self):
        """Test that CRC calculation is deterministic."""
        data = b"test data"
        crc1 = crc16_x25(data)
        crc2 = crc16_x25(data)

        assert crc1 == crc2

    def test_crc_different_for_different_data(self):
        """Test that different data produces different CRC."""
        data1 = b"test data 1"
        data2 = b"test data 2"

        crc1 = crc16_x25(data1)
        crc2 = crc16_x25(data2)

        assert crc1 != crc2

    def test_crc_known_value(self):
        """Test CRC against known good value."""
        # Empty data should produce specific CRC
        data = b""
        crc = crc16_x25(data)

        # CRC-16/X.25 of empty data is 0x0000 (0xFFFF initial XOR 0xFFFF final)
        assert crc == 0x0000
