"""
Serial Reader for Telemetry (Asyncio version)
Reads binary telemetry from UART and parses packets using asyncio.

This module is designed to be easily integrated with any async backend:
- FastAPI
- WebSocket server
- File logger
- etc.

Author: Claude + Daniel
Date: 2025-12-14
"""

import asyncio
import logging
import time
from typing import Callable, Any, Awaitable

import serial  # Base pyserial module for SerialException
import serial_asyncio

from app.services.telemetry_parser import TelemetryParser

logger = logging.getLogger(__name__)


class SerialReader:
    """
    Async serial reader.

    Reads from serial port using asyncio and feeds data to parser.
    Parsed packets are available via:
    - Async callback function (push model)
    - Async queue (pull model)

    Usage:
        # Create reader
        reader = SerialReader('/dev/ttyUSB0', 115200)

        # Option 1: Callback (push)
        async def on_packet(pkt):
            print(pkt)

        reader.set_packet_callback(on_packet)
        await reader.start()

        # Option 2: Queue (pull)
        await reader.start()
        async for packet in reader:
            print(packet)

        # Cleanup
        await reader.stop()
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        read_size: int = 1024,
        queue_maxsize: int = 1000,
    ) -> None:
        """
        Initialize serial reader.

        Args:
            port: Serial port path (e.g., 'COM3' or '/dev/ttyUSB0')
            baudrate: Baud rate (default: 115200)
            read_size: Bytes to read per iteration (default: 1024)
            queue_maxsize: Max packets to queue (default: 1000)
        """
        self.port = port
        self.baudrate = baudrate
        self.read_size = read_size

        self.parser = TelemetryParser()
        self.packet_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=queue_maxsize)
        self.packet_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None

        self._task: asyncio.Task | None = None
        self._running = False
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

        # Statistics
        self.stats = {
            "bytes_read": 0,
            "packets_queued": 0,
            "packets_dropped": 0,  # Dropped due to full queue
            "read_errors": 0,
            "start_time": None,
        }

    def set_packet_callback(
        self, callback: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        Set async callback for packet processing (push model).

        The callback will be awaited for each parsed packet.

        Args:
            callback: Async function(packet_dict) to call for each packet
        """
        self.packet_callback = callback

    async def start(self) -> None:
        """
        Start serial reader task.

        Raises:
            RuntimeError: If already running
            serial.SerialException: If port cannot be opened
        """
        if self._running:
            raise RuntimeError("SerialReader already running")

        logger.info(f"Starting serial reader: {self.port} @ {self.baudrate}")

        # Open serial port (async)
        try:
            self._reader, self._writer = await serial_asyncio.open_serial_connection(
                url=self.port,
                baudrate=self.baudrate,
            )
            logger.info(f"Serial port opened: {self.port}")
        except Exception as e:
            logger.error(f"Failed to open serial port: {e}")
            raise

        # Start reader task
        self._running = True
        self.stats["start_time"] = time.time()
        self._task = asyncio.create_task(self._read_loop())

        logger.info("Serial reader task started")

    async def stop(self, timeout: float = 5.0) -> None:
        """
        Stop serial reader task.

        Args:
            timeout: Max time to wait for task to stop (default: 5.0 seconds)
        """
        if not self._running:
            return

        logger.info("Stopping serial reader...")
        self._running = False

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Reader task did not stop cleanly, cancelling...")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            self._task = None

        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            logger.info("Serial port closed")

        logger.info("Serial reader stopped")

    async def get_packet(self, timeout: float | None = None) -> dict[str, Any] | None:
        """
        Get next packet from queue (pull model).

        Args:
            timeout: Max time to wait for packet (None = wait forever)

        Returns:
            Packet dictionary or None if timeout
        """
        try:
            if timeout is None:
                return await self.packet_queue.get()
            else:
                return await asyncio.wait_for(self.packet_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def get_packets(self, max_count: int = 100) -> list[dict[str, Any]]:
        """
        Get multiple packets from queue (non-blocking).

        Args:
            max_count: Maximum number of packets to retrieve

        Returns:
            List of packet dictionaries (may be empty)
        """
        packets = []
        for _ in range(max_count):
            try:
                packet = self.packet_queue.get_nowait()
                packets.append(packet)
            except asyncio.QueueEmpty:
                break
        return packets

    def get_stats(self) -> dict[str, Any]:
        """
        Get reader statistics.

        Returns:
            Dictionary with:
            - bytes_read: Total bytes read from serial
            - packets_queued: Total packets queued
            - packets_dropped: Packets dropped due to full queue
            - read_errors: Read errors encountered
            - parser_stats: Parser statistics (CRC errors, etc.)
            - uptime_s: Seconds since start
            - queue_size: Current queue size
            - is_open: Serial port open status
        """
        stats = self.stats.copy()
        stats["parser_stats"] = self.parser.get_stats()
        stats["queue_size"] = self.packet_queue.qsize()
        stats["is_open"] = self._reader is not None and self._running

        if stats["start_time"]:
            stats["uptime_s"] = time.time() - stats["start_time"]
        else:
            stats["uptime_s"] = 0

        return stats

    async def _read_loop(self) -> None:
        """
        Main read loop (runs as asyncio task).

        Continuously reads from serial port, feeds data to parser,
        and dispatches parsed packets via callback or queue.
        """
        logger.info(f"Read loop started")

        try:
            while self._running:
                try:
                    # Read available data (async)
                    data = await self._reader.read(self.read_size)
                    if not data:
                        # EOF or port closed
                        logger.warning("Serial port closed unexpectedly")
                        break

                    self.stats["bytes_read"] += len(data)

                    # Parse packets
                    packets = self.parser.feed(data)

                    # Dispatch packets
                    for packet in packets:
                        await self._dispatch_packet(packet)

                except serial.SerialException as e:
                    logger.error(e)
                    # Handle spurious "device reports readiness but no data" errors
                    # This commonly occurs when transmitter changes modes or starts/stops
                    if "device reports readiness to read but returned no data" in str(e):
                        logger.debug(f"Serial port state change detected (transmitter mode switch?): {e}")
                        await asyncio.sleep(0.05)  # Brief pause to let port stabilize
                        continue
                    else:
                        # Other serial exceptions are more serious
                        logger.error(f"Serial error in read loop: {e}", exc_info=True)
                        self.stats["read_errors"] += 1
                        await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Error in read loop: {e}", exc_info=True)
                    self.stats["read_errors"] += 1
                    await asyncio.sleep(0.1)  # Brief pause before retry

        finally:
            logger.info("Read loop stopped")

    async def _dispatch_packet(self, packet: dict[str, Any]) -> None:
        """
        Dispatch packet via callback and/or queue.

        Args:
            packet: Parsed packet dictionary
        """
        # Call async callback if set (push model)
        if self.packet_callback:
            try:
                await self.packet_callback(packet)
            except Exception as e:
                logger.error(f"Error in packet callback: {e}", exc_info=True)

        # Queue packet only if no callback is set (pull model)
        # This prevents queue buildup when using callback-based consumption
        if not self.packet_callback:
            try:
                self.packet_queue.put_nowait(packet)
                self.stats["packets_queued"] += 1
            except asyncio.QueueFull:
                # Queue full, drop packet
                self.stats["packets_dropped"] += 1
                logger.warning(f"Packet queue full, dropped {packet['type']} packet")

    def is_running(self) -> bool:
        """Check if reader is currently running."""
        return self._running

    def get_parser(self) -> TelemetryParser:
        """Get underlying parser instance (for advanced usage)."""
        return self.parser

    # Async iterator protocol for convenient packet streaming
    def __aiter__(self):
        """Make reader async iterable."""
        return self

    async def __anext__(self) -> dict[str, Any]:
        """Get next packet (for async iteration)."""
        if not self._running:
            raise StopAsyncIteration

        packet = await self.get_packet()
        if packet is None:
            raise StopAsyncIteration

        return packet


def list_serial_ports() -> list[dict[str, str]]:
    """
    List available serial ports.

    Returns:
        List of port info dictionaries
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
