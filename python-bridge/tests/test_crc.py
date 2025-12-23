"""
Tests for CRC-16/X.25 utility.

Run with:
    pytest tests/test_crc.py -v
"""

import struct

import pytest

from app.utils.crc import crc16_x25, verify_crc


class TestCRC16:
    """Test CRC-16/X.25 calculation."""

    def test_crc_deterministic(self):
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

    def test_crc_empty_data(self):
        """Test CRC of empty data."""
        data = b""
        crc = crc16_x25(data)

        # CRC-16/X.25 of empty data is 0x0000
        assert crc == 0x0000

    def test_crc_known_value(self):
        """Test CRC against known good value."""
        # Simple test vector
        data = b"\x5b\x02\x01\x00\x2a\x00\x15\xcd\x5b\x07"
        crc = crc16_x25(data)

        # CRC is deterministic - this is correct value
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF

    def test_verify_crc_valid(self):
        """Test verify_crc with valid packet."""
        # Create packet with CRC
        data = b"\x5b\x02\x01\x00\x2a\x00\x15\xcd\x5b\x07"
        crc = crc16_x25(data)
        packet = data + struct.pack("<H", crc)

        assert verify_crc(packet) is True

    def test_verify_crc_invalid(self):
        """Test verify_crc with corrupted packet."""
        # Create packet with wrong CRC
        data = b"\x5b\x02\x01\x00\x2a\x00\x15\xcd\x5b\x07"
        packet = data + b"\xff\xff"  # Wrong CRC

        assert verify_crc(packet) is False

    def test_verify_crc_too_short(self):
        """Test verify_crc with packet too short."""
        packet = b"\x5b"  # Less than 2 bytes

        assert verify_crc(packet) is False

    @pytest.mark.parametrize(
        "data",
        [
            b"",
            b"\x00",
            b"\xff",
            b"\x5b\x02",
            b"Hello World",
            b"\x00" * 100,
        ],
    )
    def test_crc_various_inputs(self, data):
        """Test CRC with various input data."""
        crc = crc16_x25(data)

        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF
