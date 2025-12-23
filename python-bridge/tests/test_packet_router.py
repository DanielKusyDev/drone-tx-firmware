"""
Tests for PacketRouter.

Run with:
    pytest tests/test_packet_router.py -v
"""

import pytest

from app.core.packet_router import PacketRouter, RouteDestination


class TestPacketRouter:
    """Test packet routing logic."""

    @pytest.fixture
    def router(self):
        """Create fresh router for each test."""
        return PacketRouter()

    def test_route_attitude(self, router):
        """Test routing ATTITUDE packet."""
        packet = {"type": "ATT", "seq": 1}
        destination = router.route(packet)

        assert destination == RouteDestination.TELEMETRY
        assert router.stats["telemetry_routed"] == 1

    def test_route_motors(self, router):
        """Test routing MOTORS packet."""
        packet = {"type": "MOT", "seq": 1}
        destination = router.route(packet)

        assert destination == RouteDestination.TELEMETRY
        assert router.stats["telemetry_routed"] == 1

    def test_route_status(self, router):
        """Test routing STATUS packet."""
        packet = {"type": "STA", "seq": 1}
        destination = router.route(packet)

        assert destination == RouteDestination.TELEMETRY
        assert router.stats["telemetry_routed"] == 1

    @pytest.mark.parametrize(
        "packet_type", ["ATT", "MOT", "STA", "CTL", "SENS", "SAFE", "PERF"]
    )
    def test_route_all_telemetry_types(self, router, packet_type):
        """Test routing all telemetry packet types."""
        packet = {"type": packet_type, "seq": 1}
        destination = router.route(packet)

        assert destination == RouteDestination.TELEMETRY

    def test_route_param_response(self, router):
        """Test routing PARAM response."""
        packet = {"type": "PARAM_RESP", "seq": 1}
        destination = router.route(packet)

        assert destination == RouteDestination.PARAM_RESPONSE
        assert router.stats["param_routed"] == 1

    def test_route_unknown(self, router):
        """Test routing unknown packet type."""
        packet = {"type": "UNKNOWN", "seq": 1}
        destination = router.route(packet)

        assert destination == RouteDestination.UNKNOWN
        assert router.stats["unknown_routed"] == 1

    def test_route_missing_type(self, router):
        """Test routing packet without type field."""
        packet = {"seq": 1}
        destination = router.route(packet)

        assert destination == RouteDestination.UNKNOWN
        assert router.stats["unknown_routed"] == 1

    def test_stats_tracking(self, router):
        """Test statistics tracking."""
        # Route multiple packets
        router.route({"type": "ATT"})
        router.route({"type": "MOT"})
        router.route({"type": "PARAM_RESP"})
        router.route({"type": "UNKNOWN"})

        stats = router.get_stats()

        assert stats["telemetry_routed"] == 2
        assert stats["param_routed"] == 1
        assert stats["unknown_routed"] == 1

    def test_reset_stats(self, router):
        """Test resetting statistics."""
        # Route some packets
        router.route({"type": "ATT"})
        router.route({"type": "MOT"})

        # Reset
        router.reset_stats()

        stats = router.get_stats()
        assert stats["telemetry_routed"] == 0
        assert stats["param_routed"] == 0
        assert stats["unknown_routed"] == 0
