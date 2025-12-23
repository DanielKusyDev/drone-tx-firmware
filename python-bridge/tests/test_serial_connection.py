"""
Tests for SerialConnection - async UART I/O management.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.serial_connection import SerialConnection, SerialConnectionError


class TestSerialConnectionInit:
    """Test SerialConnection initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default baudrate."""
        conn = SerialConnection("COM3")

        assert conn.port == "COM3"
        assert conn.baudrate == 115200
        assert conn._is_open is False
        assert conn._reader is None
        assert conn._writer is None

    def test_init_with_custom_baudrate(self):
        """Test initialization with custom baudrate."""
        conn = SerialConnection("/dev/ttyUSB0", 9600)

        assert conn.port == "/dev/ttyUSB0"
        assert conn.baudrate == 9600


class TestSerialConnectionOpen:
    """Test opening serial connection."""

    @pytest.mark.asyncio
    async def test_open_success(self):
        """Test successfully opening serial port."""
        conn = SerialConnection("COM3", 115200)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()

        with patch("app.core.serial_connection.serial_asyncio.open_serial_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            await conn.open()

            # Verify
            assert conn.is_open() is True
            assert conn._reader is mock_reader
            assert conn._writer is mock_writer

            mock_open.assert_called_once_with(url="COM3", baudrate=115200)

    @pytest.mark.asyncio
    async def test_open_failure(self):
        """Test failure opening serial port."""
        conn = SerialConnection("INVALID_PORT", 115200)

        with patch("app.core.serial_connection.serial_asyncio.open_serial_connection") as mock_open:
            mock_open.side_effect = Exception("Port not found")

            with pytest.raises(SerialConnectionError, match="Failed to open INVALID_PORT"):
                await conn.open()

            # Verify still closed
            assert conn.is_open() is False

    @pytest.mark.asyncio
    async def test_open_already_open(self):
        """Test opening already-open port."""
        conn = SerialConnection("COM3", 115200)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()

        with patch("app.core.serial_connection.serial_asyncio.open_serial_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            await conn.open()

            # Try to open again
            with pytest.raises(RuntimeError, match="already open"):
                await conn.open()


class TestSerialConnectionClose:
    """Test closing serial connection."""

    @pytest.mark.asyncio
    async def test_close_success(self):
        """Test successfully closing serial port."""
        conn = SerialConnection("COM3", 115200)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("app.core.serial_connection.serial_asyncio.open_serial_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            await conn.open()
            await conn.close()

            # Verify
            assert conn.is_open() is False
            assert conn._reader is None
            assert conn._writer is None

            mock_writer.close.assert_called_once()
            mock_writer.wait_closed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_not_open(self):
        """Test closing already-closed port."""
        conn = SerialConnection("COM3", 115200)

        # Should not raise
        await conn.close()

        assert conn.is_open() is False

    @pytest.mark.asyncio
    async def test_close_timeout(self):
        """Test close timeout."""
        conn = SerialConnection("COM3", 115200)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()

        # Simulate slow close
        async def slow_wait_closed():
            await asyncio.sleep(10)

        mock_writer.wait_closed = slow_wait_closed

        with patch("app.core.serial_connection.serial_asyncio.open_serial_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            await conn.open()

            # Close with short timeout (should log warning)
            await conn.close(timeout=0.1)

            # Should still mark as closed
            assert conn.is_open() is False


class TestSerialConnectionRead:
    """Test reading from serial connection."""

    @pytest.mark.asyncio
    async def test_read_success(self):
        """Test successfully reading data."""
        conn = SerialConnection("COM3", 115200)

        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=b"Hello World")
        mock_writer = MagicMock()

        with patch("app.core.serial_connection.serial_asyncio.open_serial_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            await conn.open()
            data = await conn.read(1024)

            assert data == b"Hello World"
            mock_reader.read.assert_awaited_once_with(1024)

    @pytest.mark.asyncio
    async def test_read_eof(self):
        """Test read EOF (port closed unexpectedly)."""
        conn = SerialConnection("COM3", 115200)

        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=b"")  # EOF
        mock_writer = MagicMock()

        with patch("app.core.serial_connection.serial_asyncio.open_serial_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            await conn.open()

            with pytest.raises(SerialConnectionError, match="closed unexpectedly"):
                await conn.read(1024)

            # Should mark as not open
            assert conn.is_open() is False

    @pytest.mark.asyncio
    async def test_read_not_open(self):
        """Test reading from closed port."""
        conn = SerialConnection("COM3", 115200)

        with pytest.raises(SerialConnectionError, match="not open"):
            await conn.read(1024)

    @pytest.mark.asyncio
    async def test_read_error(self):
        """Test read error."""
        conn = SerialConnection("COM3", 115200)

        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(side_effect=Exception("USB disconnected"))
        mock_writer = MagicMock()

        with patch("app.core.serial_connection.serial_asyncio.open_serial_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            await conn.open()

            with pytest.raises(SerialConnectionError, match="Read error"):
                await conn.read(1024)


class TestSerialConnectionWrite:
    """Test writing to serial connection."""

    @pytest.mark.asyncio
    async def test_write_success(self):
        """Test successfully writing data."""
        conn = SerialConnection("COM3", 115200)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()

        with patch("app.core.serial_connection.serial_asyncio.open_serial_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            await conn.open()
            await conn.write(b"Test data")

            mock_writer.write.assert_called_once_with(b"Test data")
            mock_writer.drain.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_write_not_open(self):
        """Test writing to closed port."""
        conn = SerialConnection("COM3", 115200)

        with pytest.raises(SerialConnectionError, match="not open"):
            await conn.write(b"Test")

    @pytest.mark.asyncio
    async def test_write_error(self):
        """Test write error."""
        conn = SerialConnection("COM3", 115200)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock(side_effect=Exception("USB disconnected"))

        with patch("app.core.serial_connection.serial_asyncio.open_serial_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            await conn.open()

            with pytest.raises(SerialConnectionError, match="Write error"):
                await conn.write(b"Test")


class TestSerialConnectionStatus:
    """Test connection status."""

    @pytest.mark.asyncio
    async def test_is_open_initially_false(self):
        """Test is_open() initially false."""
        conn = SerialConnection("COM3", 115200)
        assert conn.is_open() is False

    @pytest.mark.asyncio
    async def test_is_open_after_open(self):
        """Test is_open() after opening."""
        conn = SerialConnection("COM3", 115200)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()

        with patch("app.core.serial_connection.serial_asyncio.open_serial_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            await conn.open()
            assert conn.is_open() is True

    @pytest.mark.asyncio
    async def test_is_open_after_close(self):
        """Test is_open() after closing."""
        conn = SerialConnection("COM3", 115200)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("app.core.serial_connection.serial_asyncio.open_serial_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            await conn.open()
            await conn.close()
            assert conn.is_open() is False


class TestSerialConnectionListPorts:
    """Test listing serial ports."""

    def test_list_ports_success(self):
        """Test listing available ports."""
        # Mock port info
        mock_port1 = MagicMock()
        mock_port1.device = "COM3"
        mock_port1.description = "USB Serial Port"
        mock_port1.hwid = "USB VID:PID=1234:5678"

        mock_port2 = MagicMock()
        mock_port2.device = "COM4"
        mock_port2.description = "ESP32 UART"
        mock_port2.hwid = "USB VID:PID=10C4:EA60"

        with patch("serial.tools.list_ports.comports") as mock_comports:
            mock_comports.return_value = [mock_port1, mock_port2]

            ports = SerialConnection.list_ports()

            assert len(ports) == 2
            assert ports[0]["device"] == "COM3"
            assert ports[0]["description"] == "USB Serial Port"
            assert ports[1]["device"] == "COM4"
            assert ports[1]["description"] == "ESP32 UART"

    def test_list_ports_empty(self):
        """Test listing when no ports available."""
        with patch("serial.tools.list_ports.comports") as mock_comports:
            mock_comports.return_value = []

            ports = SerialConnection.list_ports()
            assert len(ports) == 0


class TestSerialConnectionContextManager:
    """Test async context manager support."""

    @pytest.mark.asyncio
    async def test_context_manager_success(self):
        """Test context manager opens and closes."""
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("app.core.serial_connection.serial_asyncio.open_serial_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            async with SerialConnection("COM3", 115200) as conn:
                assert conn.is_open() is True

            # Should be closed after exiting context
            assert conn.is_open() is False
            mock_writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self):
        """Test context manager closes even on exception."""
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("app.core.serial_connection.serial_asyncio.open_serial_connection") as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            with pytest.raises(ValueError):
                async with SerialConnection("COM3", 115200) as conn:
                    assert conn.is_open() is True
                    raise ValueError("Test error")

            # Should still be closed
            assert conn.is_open() is False
            mock_writer.close.assert_called_once()
