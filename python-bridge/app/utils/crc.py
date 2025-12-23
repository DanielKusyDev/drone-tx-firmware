"""
CRC-16/X.25 checksum calculation.

This module provides CRC calculation that must match firmware implementation exactly.
Used for validating telemetry packets and PARAM request/response packets.
"""


def crc16_x25(data: bytes) -> int:
    """
    Calculate CRC-16/X.25 checksum.

    Algorithm details:
    - Polynomial: 0x8408 (reflected 0x1021)
    - Initial value: 0xFFFF
    - Final XOR: 0xFFFF
    - Reflects input and output

    Args:
        data: Bytes to calculate CRC over (everything except the CRC itself)

    Returns:
        16-bit CRC value

    Example:
        >>> packet_data = b'\\x5B\\x02\\x01...'  # Header + payload
        >>> crc = crc16_x25(packet_data)
        >>> full_packet = packet_data + struct.pack('<H', crc)
    """
    crc = 0xFFFF

    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1

    return (~crc) & 0xFFFF


def verify_crc(data: bytes) -> bool:
    """
    Verify CRC of packet (data includes CRC at end).

    Args:
        data: Complete packet including 2-byte CRC at end

    Returns:
        True if CRC is valid, False otherwise

    Example:
        >>> packet = b'\\x5B\\x02\\x01...\\xAB\\xCD'  # Header + payload + CRC
        >>> if verify_crc(packet):
        ...     print("Valid packet")
    """
    if len(data) < 2:
        return False

    # Calculate CRC over everything except last 2 bytes
    calculated = crc16_x25(data[:-2])

    # Extract received CRC (last 2 bytes, little-endian)
    received = int.from_bytes(data[-2:], byteorder="little")

    return calculated == received
