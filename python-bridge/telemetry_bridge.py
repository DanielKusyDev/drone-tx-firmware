"""
Telemetry Bridge - Orchestration Layer
Manages serial reader and provides clean interface for backends (FastAPI, WebSocket, etc.)

This is the main entry point for integrating telemetry into any application.

Author: Claude + Daniel
Date: 2025-12-03
"""

import logging
from typing import Optional, Dict, Any, List, Callable
from serial_reader import SerialReader, list_serial_ports
from telemetry_parser import TelemetryPacketType
import time

logger = logging.getLogger(__name__)


class TelemetryBridge:
    """
    High-level telemetry bridge.

    Manages serial reader and provides:
    - Latest packet cache (quick access to most recent data)
    - Packet history (rolling buffer)
    - Statistics and health monitoring
    - Event callbacks for real-time processing

    This class is designed to be backend-agnostic. You can:
    - Subscribe to packet events
    - Query latest data
    - Get packet history
    - Monitor health/statistics

    Usage with callback (e.g., FastAPI WebSocket):
        bridge = TelemetryBridge('COM3', 115200)

        def on_packet(packet):
            # Send to WebSocket clients
            await websocket.send_json(packet)

        bridge.set_packet_callback(on_packet)
        bridge.start()

    Usage with polling (e.g., FastAPI REST endpoint):
        bridge = TelemetryBridge('COM3', 115200)
        bridge.start()

        @app.get("/telemetry/latest")
        def get_latest():
            return bridge.get_latest_packets()
    """

    def __init__(self, port: str, baudrate: int = 115200,
                 history_size: int = 1000):
        """
        Initialize telemetry bridge.

        Args:
            port: Serial port path
            baudrate: Baud rate (default: 115200)
            history_size: Max packets to keep in history (default: 1000)
        """
        self.port = port
        self.baudrate = baudrate
        self.history_size = history_size

        self.reader = SerialReader(port, baudrate)

        # Latest packet cache (one per packet type)
        self._latest_packets: Dict[str, Dict[str, Any]] = {}

        # Packet history (rolling buffer)
        self._packet_history: List[Dict[str, Any]] = []

        # User callback
        self._user_callback: Optional[Callable[[Dict[str, Any]], None]] = None

        # Register internal callback
        self.reader.set_packet_callback(self._on_packet)

        # Health monitoring
        self._health = {
            'last_packet_time': None,
            'packets_received': 0,
            'packets_by_type': {},
        }

    def set_packet_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Set callback for real-time packet processing.

        The callback will be called from the reader thread.

        Args:
            callback: Function(packet_dict) to call for each packet
        """
        self._user_callback = callback

    def start(self):
        """Start telemetry bridge."""
        logger.info(f"Starting telemetry bridge: {self.port} @ {self.baudrate}")
        self.reader.start()
        logger.info("Telemetry bridge started")

    def stop(self):
        """Stop telemetry bridge."""
        logger.info("Stopping telemetry bridge...")
        self.reader.stop()
        logger.info("Telemetry bridge stopped")

    def _on_packet(self, packet: Dict[str, Any]):
        """
        Internal packet handler (called from reader thread).

        Updates cache, history, health stats, and calls user callback.

        Args:
            packet: Parsed packet dictionary
        """
        packet_type = packet['type']

        # Update latest packet cache
        self._latest_packets[packet_type] = packet

        # Update packet history (rolling buffer)
        self._packet_history.append(packet)
        if len(self._packet_history) > self.history_size:
            self._packet_history.pop(0)

        # Update health stats
        self._health['last_packet_time'] = time.time()
        self._health['packets_received'] += 1
        if packet_type not in self._health['packets_by_type']:
            self._health['packets_by_type'][packet_type] = 0
        self._health['packets_by_type'][packet_type] += 1

        # Call user callback
        if self._user_callback:
            try:
                self._user_callback(packet)
            except Exception as e:
                logger.error(f"Error in user callback: {e}", exc_info=True)

    # === Latest Data API (for REST endpoints) ===

    def get_latest_packets(self) -> Dict[str, Dict[str, Any]]:
        """
        Get latest packet of each type.

        Returns:
            Dictionary mapping packet type to latest packet:
            {
                'ATT': {...},
                'MOT': {...},
                'STA': {...},
            }
        """
        return self._latest_packets.copy()

    def get_latest_packet(self, packet_type: str) -> Optional[Dict[str, Any]]:
        """
        Get latest packet of specific type.

        Args:
            packet_type: Packet type ('ATT', 'MOT', 'STA', etc.)

        Returns:
            Latest packet or None if not received yet
        """
        return self._latest_packets.get(packet_type)

    def get_latest_attitude(self) -> Optional[Dict[str, Any]]:
        """Get latest ATTITUDE packet."""
        return self.get_latest_packet('ATT')

    def get_latest_motors(self) -> Optional[Dict[str, Any]]:
        """Get latest MOTORS packet."""
        return self.get_latest_packet('MOT')

    def get_latest_status(self) -> Optional[Dict[str, Any]]:
        """Get latest STATUS packet."""
        return self.get_latest_packet('STA')

    # === History API ===

    def get_packet_history(self, packet_type: Optional[str] = None,
                          max_count: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get packet history.

        Args:
            packet_type: Filter by packet type (None = all types)
            max_count: Max packets to return (None = all)

        Returns:
            List of packets (newest last)
        """
        history = self._packet_history

        if packet_type:
            history = [p for p in history if p['type'] == packet_type]

        if max_count:
            history = history[-max_count:]

        return history

    # === Health Monitoring API ===

    def get_health(self) -> Dict[str, Any]:
        """
        Get bridge health status.

        Returns:
            Dictionary with:
            - is_alive: bool
            - last_packet_age_s: float (seconds since last packet)
            - packets_received: int
            - packets_by_type: dict
            - serial_stats: dict
        """
        health = {
            'is_alive': self.reader.is_running(),
            'packets_received': self._health['packets_received'],
            'packets_by_type': self._health['packets_by_type'].copy(),
            'serial_stats': self.reader.get_stats(),
        }

        if self._health['last_packet_time']:
            health['last_packet_age_s'] = time.time() - self._health['last_packet_time']
        else:
            health['last_packet_age_s'] = None

        return health

    def is_healthy(self, max_age_s: float = 5.0) -> bool:
        """
        Check if bridge is healthy.

        Args:
            max_age_s: Max age of last packet (default: 5.0 seconds)

        Returns:
            True if healthy (receiving recent packets)
        """
        if not self.reader.is_running():
            return False

        if self._health['last_packet_time'] is None:
            return False

        age = time.time() - self._health['last_packet_time']
        return age < max_age_s

    # === Statistics API ===

    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics.

        Returns:
            Dictionary with bridge, reader, and parser stats
        """
        return {
            'bridge': {
                'history_size': len(self._packet_history),
                'latest_packet_types': list(self._latest_packets.keys()),
                **self._health,
            },
            'reader': self.reader.get_stats(),
        }

    def reset_stats(self):
        """Reset all statistics counters."""
        self._health = {
            'last_packet_time': None,
            'packets_received': 0,
            'packets_by_type': {},
        }
        self.reader.parser.reset_stats()

    # === Utility Methods ===

    @staticmethod
    def list_ports():
        """List available serial ports."""
        return list_serial_ports()

    def __enter__(self):
        """Context manager enter."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


if __name__ == '__main__':
    # Simple test
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=== Telemetry Bridge Test ===\n")

    print("Available serial ports:")
    for port in TelemetryBridge.list_ports():
        print(f"  {port['device']}: {port['description']}")
    print()

    # Uncomment to test with real serial port
    # port = input("Enter serial port (e.g., COM3 or /dev/ttyUSB0): ")
    #
    # def print_packet(packet):
    #     print(f"[{packet['type']}] seq={packet['seq']}")
    #
    # with TelemetryBridge(port, 115200) as bridge:
    #     bridge.set_packet_callback(print_packet)
    #
    #     try:
    #         while True:
    #             time.sleep(5)
    #             stats = bridge.get_stats()
    #             print(f"\nStats: {stats['bridge']['packets_received']} packets received")
    #             print(f"Health: {'✅ OK' if bridge.is_healthy() else '❌ STALE'}")
    #
    #             latest = bridge.get_latest_packets()
    #             if 'ATT' in latest:
    #                 att = latest['ATT']
    #                 print(f"Latest attitude: roll={att['roll_deg']:.2f}° pitch={att['pitch_deg']:.2f}°")
    #
    #     except KeyboardInterrupt:
    #         print("\nStopping...")
