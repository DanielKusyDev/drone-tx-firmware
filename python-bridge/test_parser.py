"""
Test script for telemetry parser.
Creates synthetic packets and verifies parsing.

Author: Claude + Daniel
Date: 2025-12-03
"""

import struct
import logging
from telemetry_parser import (
    TelemetryParser,
    crc16_x25,
    TELEM_ENHANCED_MAGIC,
    TELEM_ENHANCED_VERSION,
    TelemetryPacketType
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def create_attitude_packet(seq: int = 42) -> bytes:
    """Create a test ATTITUDE packet."""
    import io
    buf = io.BytesIO()

    # Header (10 bytes)
    buf.write(struct.pack('<BBBBHI',
        TELEM_ENHANCED_MAGIC,   # magic
        TELEM_ENHANCED_VERSION,  # version
        TelemetryPacketType.ATTITUDE,  # type
        0x00,                    # flags
        seq,                     # seq
        123456789                # timestamp_us
    ))

    # Payload (12 bytes): 6 x int16
    buf.write(struct.pack('<hhhhhh',
        -898,   # roll (*100) = -8.98°
        924,    # pitch (*100) = 9.24°
        0,      # yaw
        -205,   # roll rate (*10) = -20.5°/s
        115,    # pitch rate (*10) = 11.5°/s
        0       # yaw rate
    ))

    # Calculate and write CRC
    packet_data = buf.getvalue()
    crc = crc16_x25(packet_data)
    buf.write(struct.pack('<H', crc))

    return buf.getvalue()


def create_motors_packet(seq: int = 100) -> bytes:
    """Create a test MOTORS packet."""
    import io
    buf = io.BytesIO()

    # Header (10 bytes)
    buf.write(struct.pack('<BBBBHI',
        TELEM_ENHANCED_MAGIC,
        TELEM_ENHANCED_VERSION,
        TelemetryPacketType.MOTORS,
        0x00,
        seq,
        123456800
    ))

    # Payload (19 bytes): 8 x uint16 + 1 x uint16 + 1 x uint8
    buf.write(struct.pack('<HHHHHHHHB',
        0,      # motor_cmd[0]
        5120,   # motor_cmd[1]
        31488,  # motor_cmd[2]
        4864,   # motor_cmd[3]
        0,      # motor_actual[0]
        5120,   # motor_actual[1]
        31488,  # motor_actual[2]
        4864,   # motor_actual[3]
        2686,   # throttle
        0       # mixer_id
    ))

    # CRC
    packet_data = buf.getvalue()
    crc = crc16_x25(packet_data)
    buf.write(struct.pack('<H', crc))

    return buf.getvalue()


def create_status_packet(seq: int = 200) -> bytes:
    """Create a test STATUS packet."""
    import io
    buf = io.BytesIO()

    # Header (10 bytes)
    buf.write(struct.pack('<BBBBHI',
        TELEM_ENHANCED_MAGIC,
        TELEM_ENHANCED_VERSION,
        TelemetryPacketType.STATUS,
        0x00,
        seq,
        123456820
    ))

    # Payload (12 bytes): 6 x uint8 + 1 x uint16 + 1 x uint32
    safety_flags = 0x01 | 0x02 | 0x08  # HRZ | LINK | CAL
    buf.write(struct.pack('<BBBBBBHI',
        1,              # armed
        0,              # flight_mode
        safety_flags,   # safety_flags
        0,              # ground_state
        100,            # link_quality
        85,             # battery_pct
        45,             # uptime_s
        5000            # loop_rate_hz_x10 (500.0 Hz)
    ))

    # CRC
    packet_data = buf.getvalue()
    crc = crc16_x25(packet_data)
    buf.write(struct.pack('<H', crc))

    return buf.getvalue()


def test_single_packet():
    """Test parsing a single ATTITUDE packet."""
    print("\n=== Test 1: Single ATTITUDE Packet ===")

    parser = TelemetryParser()
    packet_data = create_attitude_packet()

    packets = parser.feed(packet_data)

    assert len(packets) == 1, f"Expected 1 packet, got {len(packets)}"

    pkt = packets[0]
    assert pkt['type'] == 'ATT'
    assert pkt['seq'] == 42
    assert pkt['ts_us'] == 123456789
    assert abs(pkt['roll_deg'] - (-8.98)) < 0.01
    assert abs(pkt['pitch_deg'] - 9.24) < 0.01
    assert abs(pkt['roll_rate_dps'] - (-20.5)) < 0.01
    assert abs(pkt['pitch_rate_dps'] - 11.5) < 0.01

    print("✅ Single packet test passed!")
    print(f"   Parsed: {pkt}")


def test_multiple_packets():
    """Test parsing multiple packets in one feed."""
    print("\n=== Test 2: Multiple Packets ===")

    parser = TelemetryParser()

    # Create stream with 3 different packets
    stream = b''
    stream += create_attitude_packet(seq=1)
    stream += create_motors_packet(seq=2)
    stream += create_status_packet(seq=3)

    packets = parser.feed(stream)

    assert len(packets) == 3, f"Expected 3 packets, got {len(packets)}"

    assert packets[0]['type'] == 'ATT'
    assert packets[0]['seq'] == 1

    assert packets[1]['type'] == 'MOT'
    assert packets[1]['seq'] == 2
    assert packets[1]['throttle'] == 2686

    assert packets[2]['type'] == 'STA'
    assert packets[2]['seq'] == 3
    assert packets[2]['armed'] == True
    assert packets[2]['flags']['HRZ'] == True
    assert packets[2]['flags']['CAL'] == True
    assert packets[2]['loop_rate_hz'] == 500.0

    print("✅ Multiple packets test passed!")
    print(f"   Parsed {len(packets)} packets")


def test_garbage_data():
    """Test parser with garbage data before valid packet."""
    print("\n=== Test 3: Garbage Data Before Packet ===")

    parser = TelemetryParser()

    # Create stream with garbage followed by valid packet
    stream = b'\xFF\xFF\x00\x00\xAA\xBB\xCC\xDD'  # Garbage
    stream += create_attitude_packet()

    packets = parser.feed(stream)

    assert len(packets) == 1, f"Expected 1 packet, got {len(packets)}"
    assert packets[0]['type'] == 'ATT'

    stats = parser.get_stats()
    assert stats['bytes_discarded'] >= 8  # Garbage was discarded

    print("✅ Garbage data test passed!")
    print(f"   Discarded {stats['bytes_discarded']} bytes of garbage")


def test_crc_error():
    """Test parser with corrupted CRC."""
    print("\n=== Test 4: CRC Error Detection ===")

    parser = TelemetryParser()

    # Create valid packet
    packet_data = bytearray(create_attitude_packet())

    # Corrupt CRC (last 2 bytes)
    packet_data[-1] ^= 0xFF

    packets = parser.feed(bytes(packet_data))

    assert len(packets) == 0, "Should not parse packet with bad CRC"

    stats = parser.get_stats()
    assert stats['crc_errors'] > 0

    print("✅ CRC error detection test passed!")
    print(f"   CRC errors: {stats['crc_errors']}")


def test_partial_packet():
    """Test parser with partial packet (need more data)."""
    print("\n=== Test 5: Partial Packet ===")

    parser = TelemetryParser()

    # Create full packet
    full_packet = create_attitude_packet()

    # Feed only first 10 bytes (just header, no payload)
    packets = parser.feed(full_packet[:10])

    assert len(packets) == 0, "Should not parse partial packet"

    # Feed rest of packet
    packets = parser.feed(full_packet[10:])

    assert len(packets) == 1, "Should parse complete packet now"
    assert packets[0]['type'] == 'ATT'

    print("✅ Partial packet test passed!")


def test_statistics():
    """Test parser statistics tracking."""
    print("\n=== Test 6: Statistics Tracking ===")

    parser = TelemetryParser()

    # Parse multiple packets
    for i in range(10):
        packet_data = create_attitude_packet(seq=i)
        parser.feed(packet_data)

    stats = parser.get_stats()

    assert stats['packets_parsed'] == 10
    assert stats['crc_errors'] == 0
    assert stats['unknown_types'] == 0

    print("✅ Statistics test passed!")
    print(f"   Stats: {stats}")

    # Reset and verify
    parser.reset_stats()
    stats = parser.get_stats()
    assert stats['packets_parsed'] == 0

    print("✅ Statistics reset test passed!")


def run_all_tests():
    """Run all parser tests."""
    print("=" * 60)
    print("Telemetry Parser Test Suite")
    print("=" * 60)

    try:
        test_single_packet()
        test_multiple_packets()
        test_garbage_data()
        test_crc_error()
        test_partial_packet()
        test_statistics()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return True

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)
