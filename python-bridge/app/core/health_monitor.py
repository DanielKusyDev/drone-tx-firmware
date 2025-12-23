"""
Health monitoring and statistics tracking.

Centralized monitoring for bridge health:
- Uptime tracking
- Byte counters (read/written)
- Packet counters (by type)
- Error counters
"""

import time
from typing import Any


class HealthMonitor:
    """
    Health and statistics monitor for unified bridge.

    Tracks:
    - Uptime
    - Bytes read/written
    - Packet counts (telemetry, PARAM)
    - Error counts (read errors, timeouts, CRC errors)

    Usage:
        monitor = HealthMonitor()

        # Record events
        monitor.record_bytes_read(1024)
        monitor.record_telemetry_packet()
        monitor.record_param_request()
        monitor.record_read_error()

        # Query stats
        stats = monitor.get_stats()
        uptime = monitor.get_uptime()
    """

    def __init__(self):
        """Initialize health monitor."""
        self.stats = {
            # Timing
            "start_time": time.time(),
            # Bytes
            "bytes_read": 0,
            "bytes_written": 0,
            # Packets
            "telemetry_packets": 0,
            "param_requests": 0,
            "param_responses": 0,
            # Errors
            "read_errors": 0,
            "param_timeouts": 0,
            "param_crc_errors": 0,
        }

    def record_bytes_read(self, count: int) -> None:
        """Record bytes read from serial port."""
        self.stats["bytes_read"] += count

    def record_bytes_written(self, count: int) -> None:
        """Record bytes written to serial port."""
        self.stats["bytes_written"] += count

    def record_telemetry_packet(self) -> None:
        """Record telemetry packet received."""
        self.stats["telemetry_packets"] += 1

    def record_param_request(self) -> None:
        """Record PARAM request sent."""
        self.stats["param_requests"] += 1

    def record_param_response(self) -> None:
        """Record PARAM response received."""
        self.stats["param_responses"] += 1

    def record_read_error(self) -> None:
        """Record serial read error."""
        self.stats["read_errors"] += 1

    def record_param_timeout(self) -> None:
        """Record PARAM request timeout."""
        self.stats["param_timeouts"] += 1

    def record_param_crc_error(self) -> None:
        """Record PARAM CRC error."""
        self.stats["param_crc_errors"] += 1

    def get_uptime(self) -> float:
        """
        Get bridge uptime in seconds.

        Returns:
            Seconds since start
        """
        return time.time() - self.stats["start_time"]

    def get_stats(self) -> dict[str, Any]:
        """
        Get all statistics.

        Returns:
            Dictionary with all stats + calculated uptime
        """
        stats = self.stats.copy()
        stats["uptime_s"] = self.get_uptime()
        return stats

    def reset(self) -> None:
        """Reset all counters (uptime unchanged)."""
        start_time = self.stats["start_time"]

        for key in self.stats:
            if key != "start_time":
                self.stats[key] = 0

        self.stats["start_time"] = start_time
