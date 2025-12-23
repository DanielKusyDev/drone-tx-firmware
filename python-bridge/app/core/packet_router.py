"""
Packet router - routes packets based on type.

Routes incoming packets to appropriate handlers:
- Telemetry packets (0x01-0x07) → telemetry stream
- PARAM responses (0x11) → PARAM request handler
"""

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RouteDestination(Enum):
    """Packet routing destinations."""

    TELEMETRY = "telemetry"  # Telemetry packets (ATT, MOT, STA, etc.)
    PARAM_RESPONSE = "param_response"  # PARAM response packets
    UNKNOWN = "unknown"  # Unknown packet type


class PacketRouter:
    """
    Routes packets to appropriate handlers based on type.

    Simple stateless router that examines packet['type'] and
    determines where it should be sent.

    Usage:
        router = PacketRouter()

        packet = {'type': 'ATT', ...}
        destination = router.route(packet)

        if destination == RouteDestination.TELEMETRY:
            await telemetry_store.add(packet)
        elif destination == RouteDestination.PARAM_RESPONSE:
            await param_handler.handle_response(packet)
    """

    def __init__(self):
        """Initialize packet router."""
        self.stats = {
            "telemetry_routed": 0,
            "param_routed": 0,
            "unknown_routed": 0,
        }

    def route(self, packet: dict[str, Any]) -> RouteDestination:
        """
        Determine routing destination for packet.

        Args:
            packet: Parsed packet dictionary with 'type' field

        Returns:
            RouteDestination indicating where packet should go
        """
        packet_type = packet.get("type")

        if not packet_type:
            logger.warning("Packet missing 'type' field")
            self.stats["unknown_routed"] += 1
            return RouteDestination.UNKNOWN

        # Telemetry packets (ATT, MOT, STA, CTL, SENS, SAFE, PERF)
        if packet_type in ("ATT", "MOT", "STA", "CTL", "SENS", "SAFE", "PERF"):
            self.stats["telemetry_routed"] += 1
            return RouteDestination.TELEMETRY

        # PARAM response
        elif packet_type == "PARAM_RESP":
            self.stats["param_routed"] += 1
            return RouteDestination.PARAM_RESPONSE

        # Unknown/unexpected packet types
        else:
            logger.debug(f"Unknown packet type for routing: {packet_type}")
            self.stats["unknown_routed"] += 1
            return RouteDestination.UNKNOWN

    def get_stats(self) -> dict[str, int]:
        """Get routing statistics."""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset routing statistics."""
        for key in self.stats:
            self.stats[key] = 0
