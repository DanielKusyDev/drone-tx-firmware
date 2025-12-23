"""
Telemetry data store.

Manages storage of telemetry packets:
- Latest packet of each type (ATT, MOT, STA, etc.)
- Rolling history buffer (configurable size)
- Thread-safe access with RWLock
"""

import logging
import time
from typing import Any, Optional

import aiorwlock

logger = logging.getLogger(__name__)


class TelemetryStore:
    """
    Thread-safe storage for telemetry packets.

    Maintains:
    - Latest packet of each type (for quick access)
    - Rolling history buffer (FIFO, limited size)
    - Health monitoring (last packet time, counts)

    Usage:
        store = TelemetryStore(history_size=1000)

        # Add packets
        await store.add(packet)

        # Query latest
        latest = await store.get_latest('ATT')
        all_latest = await store.get_all_latest()

        # Query history
        history = await store.get_history('MOT', max_count=100)

        # Health check
        health = await store.get_health()
        is_healthy = await store.is_healthy(max_age_s=5.0)
    """

    def __init__(self, history_size: int = 1000):
        """
        Initialize telemetry store.

        Args:
            history_size: Maximum packets to keep in history buffer
        """
        self.history_size = history_size

        # Latest packets by type
        self._latest: dict[str, dict[str, Any]] = {}

        # Rolling history buffer (FIFO)
        self._history: list[dict[str, Any]] = []

        # Thread safety
        self._lock = aiorwlock.RWLock()

        # Health tracking
        self._health = {
            "last_packet_time": None,
            "packets_received": 0,
            "packets_by_type": {},
        }

    async def add(self, packet: dict[str, Any]) -> None:
        """
        Add packet to store.

        Updates latest packet cache and appends to history.

        Args:
            packet: Parsed telemetry packet with 'type' field
        """
        packet_type = packet.get("type")

        if not packet_type:
            logger.warning("Packet missing 'type' field, skipping store")
            return

        async with self._lock.writer_lock:
            # Update latest
            self._latest[packet_type] = packet

            # Append to history (FIFO)
            self._history.append(packet)
            if len(self._history) > self.history_size:
                self._history.pop(0)  # Remove oldest

            # Update health
            self._health["last_packet_time"] = time.time()
            self._health["packets_received"] += 1

            if packet_type not in self._health["packets_by_type"]:
                self._health["packets_by_type"][packet_type] = 0
            self._health["packets_by_type"][packet_type] += 1

    async def get_latest(self, packet_type: str) -> Optional[dict[str, Any]]:
        """
        Get latest packet of specific type.

        Args:
            packet_type: Packet type (e.g., 'ATT', 'MOT', 'STA')

        Returns:
            Latest packet or None if not received yet
        """
        async with self._lock.reader_lock:
            return self._latest.get(packet_type)

    async def get_all_latest(self) -> dict[str, Optional[dict[str, Any]]]:
        """
        Get latest packet of each telemetry type.

        Returns:
            Dictionary mapping packet type to latest packet (None if not received)
        """
        async with self._lock.reader_lock:
            return {
                "ATT": self._latest.get("ATT"),
                "MOT": self._latest.get("MOT"),
                "STA": self._latest.get("STA"),
                "CTL": self._latest.get("CTL"),
                "SENS": self._latest.get("SENS"),
                "SAFE": self._latest.get("SAFE"),
                "PERF": self._latest.get("PERF"),
            }

    async def get_history(
        self, packet_type: Optional[str] = None, max_count: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """
        Get packet history.

        Args:
            packet_type: Filter by packet type (None = all types)
            max_count: Max packets to return (None = all)

        Returns:
            List of packets (newest last)
        """
        async with self._lock.reader_lock:
            history = self._history.copy()

        # Filter by type
        if packet_type:
            history = [p for p in history if p.get("type") == packet_type]

        # Limit count
        if max_count:
            history = history[-max_count:]

        return history

    async def get_health(self) -> dict[str, Any]:
        """
        Get health status.

        Returns:
            Dictionary with:
            - last_packet_time: Unix timestamp of last packet
            - last_packet_age_s: Seconds since last packet (None if never received)
            - packets_received: Total packets received
            - packets_by_type: Count by type
        """
        async with self._lock.reader_lock:
            health = self._health.copy()

        # Calculate age
        if health["last_packet_time"]:
            health["last_packet_age_s"] = time.time() - health["last_packet_time"]
        else:
            health["last_packet_age_s"] = None

        return health

    async def is_healthy(self, max_age_s: float = 5.0) -> bool:
        """
        Check if store is healthy (receiving recent packets).

        Args:
            max_age_s: Maximum age of last packet (seconds)

        Returns:
            True if last packet was received within max_age_s
        """
        async with self._lock.reader_lock:
            if self._health["last_packet_time"] is None:
                return False

            age = time.time() - self._health["last_packet_time"]

        return age < max_age_s

    async def clear(self) -> None:
        """Clear all stored data (useful for testing)."""
        async with self._lock.writer_lock:
            self._latest.clear()
            self._history.clear()
            self._health = {
                "last_packet_time": None,
                "packets_received": 0,
                "packets_by_type": {},
            }

    def get_stats(self) -> dict[str, Any]:
        """
        Get store statistics (synchronous, no lock).

        Returns:
            Dictionary with basic stats (may be slightly stale)
        """
        return {
            "history_size": len(self._history),
            "history_capacity": self.history_size,
            "latest_types": list(self._latest.keys()),
        }
