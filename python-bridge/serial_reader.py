"""
Serial Reader for Telemetry
Reads binary telemetry from UART and parses packets.

This module is designed to be easily integrated with any backend:
- FastAPI
- WebSocket server
- File logger
- etc.

Author: Claude + Daniel
Date: 2025-12-03
"""

import serial
import threading
import logging
import time
from typing import Callable, Optional, Dict, Any, List
from queue import Queue, Empty
from telemetry_parser import TelemetryParser

logger = logging.getLogger(__name__)


class SerialReader:
    """
    Serial reader with background thread.

    Reads from serial port in a background thread and feeds data to parser.
    Parsed packets are queued for consumption by main application.

    This class is framework-agnostic - it just provides packets via:
    - Callback function (push model)
    - Queue (pull model)

    Usage:
        # Create reader
        reader = SerialReader('/dev/ttyUSB0', 115200)

        # Option 1: Callback (push)
        reader.set_packet_callback(lambda pkt: print(pkt))

        # Option 2: Queue (pull)
        reader.start()
        while True:
            packet = reader.get_packet(timeout=1.0)
            if packet:
                print(packet)

        # Cleanup
        reader.stop()
    """

    def __init__(self, port: str, baudrate: int = 115200,
                 read_size: int = 1024, timeout: float = 1.0):
        """
        Initialize serial reader.

        Args:
            port: Serial port path (e.g., 'COM3' or '/dev/ttyUSB0')
            baudrate: Baud rate (default: 115200)
            read_size: Bytes to read per iteration (default: 1024)
            timeout: Serial read timeout in seconds (default: 1.0)
        """
        self.port = port
        self.baudrate = baudrate
        self.read_size = read_size
        self.timeout = timeout

        self.parser = TelemetryParser()
        self.packet_queue: Queue = Queue(maxsize=1000)  # Buffer up to 1000 packets
        self.packet_callback: Optional[Callable[[Dict[str, Any]], None]] = None

        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._serial: Optional[serial.Serial] = None

        # Statistics
        self.stats = {
            'bytes_read': 0,
            'packets_queued': 0,
            'packets_dropped': 0,  # Dropped due to full queue
            'read_errors': 0,
            'start_time': None,
        }

    def set_packet_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Set callback for packet processing (push model).

        The callback will be called from the reader thread for each
        parsed packet. Keep the callback fast to avoid blocking reads.

        Args:
            callback: Function(packet_dict) to call for each packet
        """
        self.packet_callback = callback

    def start(self):
        """
        Start serial reader thread.

        Raises:
            RuntimeError: If already running
            serial.SerialException: If port cannot be opened
        """
        if self._running:
            raise RuntimeError("SerialReader already running")

        logger.info(f"Starting serial reader: {self.port} @ {self.baudrate}")

        # Open serial port
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            logger.info(f"Serial port opened: {self._serial.name}")
        except serial.SerialException as e:
            logger.error(f"Failed to open serial port: {e}")
            raise

        # Start reader thread
        self._running = True
        self.stats['start_time'] = time.time()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

        logger.info("Serial reader thread started")

    def stop(self, timeout: float = 5.0):
        """
        Stop serial reader thread.

        Args:
            timeout: Max time to wait for thread to stop (default: 5.0 seconds)
        """
        if not self._running:
            return

        logger.info("Stopping serial reader...")
        self._running = False

        if self._thread:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("Reader thread did not stop cleanly")
            self._thread = None

        if self._serial and self._serial.is_open:
            self._serial.close()
            logger.info("Serial port closed")

        logger.info("Serial reader stopped")

    def get_packet(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Get next packet from queue (pull model).

        Args:
            timeout: Max time to wait for packet (None = wait forever)

        Returns:
            Packet dictionary or None if timeout
        """
        try:
            return self.packet_queue.get(timeout=timeout)
        except Empty:
            return None

    def get_packets(self, max_count: int = 100) -> List[Dict[str, Any]]:
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
            except Empty:
                break
        return packets

    def get_stats(self) -> Dict[str, Any]:
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
        """
        stats = self.stats.copy()
        stats['parser_stats'] = self.parser.get_stats()
        stats['queue_size'] = self.packet_queue.qsize()

        if stats['start_time']:
            stats['uptime_s'] = time.time() - stats['start_time']
        else:
            stats['uptime_s'] = 0

        return stats

    def _read_loop(self):
        """
        Main read loop (runs in background thread).

        Continuously reads from serial port, feeds data to parser,
        and dispatches parsed packets via callback or queue.
        """
        logger.info("Read loop started")

        while self._running:
            try:
                # Read available data
                if self._serial.in_waiting > 0 or True:  # Always try to read
                    data = self._serial.read(self.read_size)
                    if data:
                        self.stats['bytes_read'] += len(data)

                        # Parse packets
                        packets = self.parser.feed(data)

                        # Dispatch packets
                        for packet in packets:
                            self._dispatch_packet(packet)

            except serial.SerialException as e:
                logger.error(f"Serial read error: {e}")
                self.stats['read_errors'] += 1
                time.sleep(0.1)  # Brief pause before retry

            except Exception as e:
                logger.error(f"Unexpected error in read loop: {e}", exc_info=True)
                time.sleep(0.1)

        logger.info("Read loop stopped")

    def _dispatch_packet(self, packet: Dict[str, Any]):
        """
        Dispatch packet via callback and/or queue.

        Args:
            packet: Parsed packet dictionary
        """
        # Call callback if set (push model)
        if self.packet_callback:
            try:
                self.packet_callback(packet)
            except Exception as e:
                logger.error(f"Error in packet callback: {e}", exc_info=True)

        # Queue packet (pull model)
        try:
            self.packet_queue.put_nowait(packet)
            self.stats['packets_queued'] += 1
        except:
            # Queue full, drop packet
            self.stats['packets_dropped'] += 1
            logger.warning(f"Packet queue full, dropped {packet['type']} packet")

    def is_running(self) -> bool:
        """Check if reader is currently running."""
        return self._running

    def get_parser(self) -> TelemetryParser:
        """Get underlying parser instance (for advanced usage)."""
        return self.parser


def list_serial_ports():
    """
    List available serial ports.

    Returns:
        List of port info dictionaries
    """
    import serial.tools.list_ports

    ports = serial.tools.list_ports.comports()
    result = []

    for port in ports:
        result.append({
            'device': port.device,
            'description': port.description,
            'hwid': port.hwid,
        })

    return result


if __name__ == '__main__':
    # Simple test
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Available serial ports:")
    for port in list_serial_ports():
        print(f"  {port['device']}: {port['description']}")

    # Uncomment to test with real serial port
    # reader = SerialReader('COM3', 115200)
    # reader.set_packet_callback(lambda pkt: print(f"Got packet: {pkt['type']} seq={pkt['seq']}"))
    # reader.start()
    #
    # try:
    #     while True:
    #         time.sleep(1)
    #         stats = reader.get_stats()
    #         print(f"Stats: {stats['packets_queued']} packets, {stats['bytes_read']} bytes")
    # except KeyboardInterrupt:
    #     print("\nStopping...")
    #     reader.stop()
