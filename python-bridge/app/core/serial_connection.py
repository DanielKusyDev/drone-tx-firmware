"""
Serial UART connection manager.

Handles opening, closing, reading and writing to serial port using asyncio.
"""

import asyncio
import logging

import serial_asyncio

logger = logging.getLogger(__name__)


class SerialConnectionError(Exception):
    """Serial connection error."""

    pass


class SerialConnection:
    """
    Async serial UART connection manager.

    Provides simple interface for reading/writing bytes over UART
    without dealing with asyncio stream details.

    Usage:
        conn = SerialConnection('COM3', 115200)
        await conn.open()

        # Write
        await conn.write(b'\\x5B\\x02...')

        # Read
        data = await conn.read(1024)

        await conn.close()
    """

    def __init__(self, port: str, baudrate: int = 115200):
        """
        Initialize serial connection.

        Args:
            port: Serial port path (e.g., 'COM3' or '/dev/ttyUSB0')
            baudrate: Baud rate (default: 115200)
        """
        self.port = port
        self.baudrate = baudrate

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._is_open = False

    async def open(self) -> None:
        """
        Open serial port.

        Raises:
            SerialConnectionError: If port cannot be opened
            RuntimeError: If already open
        """
        if self._is_open:
            raise RuntimeError(f"Serial port {self.port} already open")

        logger.info(f"Opening serial port: {self.port} @ {self.baudrate} baud")

        try:
            self._reader, self._writer = await serial_asyncio.open_serial_connection(
                url=self.port,
                baudrate=self.baudrate,
            )
            self._is_open = True
            logger.info(f"✅ Serial port opened: {self.port}")

        except Exception as e:
            logger.error(f"❌ Failed to open serial port {self.port}: {e}")
            raise SerialConnectionError(f"Failed to open {self.port}: {e}") from e

    async def close(self, timeout: float = 5.0) -> None:
        """
        Close serial port.

        Args:
            timeout: Max time to wait for clean shutdown (seconds)
        """
        if not self._is_open:
            return

        logger.info(f"Closing serial port: {self.port}")

        if self._writer:
            self._writer.close()

            try:
                await asyncio.wait_for(self._writer.wait_closed(), timeout=timeout)
            except TimeoutError:
                logger.warning(f"Timeout waiting for serial port {self.port} to close")

        self._reader = None
        self._writer = None
        self._is_open = False

        logger.info(f"✅ Serial port closed: {self.port}")

    async def read(self, size: int = 1024) -> bytes:
        """
        Read bytes from serial port.

        Args:
            size: Maximum bytes to read

        Returns:
            Bytes read (may be less than size)

        Raises:
            SerialConnectionError: If not open or read fails
        """
        if not self._is_open or not self._reader:
            raise SerialConnectionError("Serial port not open")

        try:
            data = await self._reader.read(size)

            if not data:
                # EOF - port closed unexpectedly
                logger.warning(f"Serial port {self.port} closed unexpectedly (EOF)")
                self._is_open = False
                raise SerialConnectionError("Serial port closed unexpectedly")

            return data

        except Exception as e:
            logger.error(f"Error reading from {self.port}: {e}")
            raise SerialConnectionError(f"Read error: {e}") from e

    async def write(self, data: bytes) -> None:
        """
        Write bytes to serial port.

        Args:
            data: Bytes to write

        Raises:
            SerialConnectionError: If not open or write fails
        """
        if not self._is_open or not self._writer:
            raise SerialConnectionError("Serial port not open")

        try:
            self._writer.write(data)
            await self._writer.drain()

        except Exception as e:
            logger.error(f"Error writing to {self.port}: {e}")
            raise SerialConnectionError(f"Write error: {e}") from e

    def is_open(self) -> bool:
        """Check if serial port is open."""
        return self._is_open

    @staticmethod
    def list_ports() -> list[dict[str, str]]:
        """
        List available serial ports.

        Returns:
            List of dicts with 'device', 'description', 'hwid' keys
        """
        import serial.tools.list_ports

        ports = serial.tools.list_ports.comports()
        result = []

        for port in ports:
            result.append(
                {
                    "device": port.device,
                    "description": port.description,
                    "hwid": port.hwid,
                }
            )

        return result

    # Context manager support
    async def __aenter__(self):
        """Async context manager entry."""
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
