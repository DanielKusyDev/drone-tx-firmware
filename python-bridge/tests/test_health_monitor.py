"""
Tests for HealthMonitor.

Run with:
    pytest tests/test_health_monitor.py -v
"""

import time

import pytest

from app.core.health_monitor import HealthMonitor


class TestHealthMonitor:
    """Test health monitoring and statistics."""

    @pytest.fixture
    def monitor(self):
        """Create fresh monitor for each test."""
        return HealthMonitor()

    def test_initial_stats(self, monitor):
        """Test initial statistics are zero."""
        stats = monitor.get_stats()

        assert stats["bytes_read"] == 0
        assert stats["bytes_written"] == 0
        assert stats["telemetry_packets"] == 0
        assert stats["param_requests"] == 0
        assert stats["param_responses"] == 0
        assert stats["read_errors"] == 0
        assert stats["param_timeouts"] == 0
        assert stats["param_crc_errors"] == 0

    def test_record_bytes_read(self, monitor):
        """Test recording bytes read."""
        monitor.record_bytes_read(1024)
        monitor.record_bytes_read(512)

        stats = monitor.get_stats()
        assert stats["bytes_read"] == 1536

    def test_record_bytes_written(self, monitor):
        """Test recording bytes written."""
        monitor.record_bytes_written(100)
        monitor.record_bytes_written(200)

        stats = monitor.get_stats()
        assert stats["bytes_written"] == 300

    def test_record_telemetry_packet(self, monitor):
        """Test recording telemetry packets."""
        monitor.record_telemetry_packet()
        monitor.record_telemetry_packet()
        monitor.record_telemetry_packet()

        stats = monitor.get_stats()
        assert stats["telemetry_packets"] == 3

    def test_record_param_request(self, monitor):
        """Test recording PARAM requests."""
        monitor.record_param_request()
        monitor.record_param_request()

        stats = monitor.get_stats()
        assert stats["param_requests"] == 2

    def test_record_param_response(self, monitor):
        """Test recording PARAM responses."""
        monitor.record_param_response()

        stats = monitor.get_stats()
        assert stats["param_responses"] == 1

    def test_record_errors(self, monitor):
        """Test recording various errors."""
        monitor.record_read_error()
        monitor.record_param_timeout()
        monitor.record_param_crc_error()

        stats = monitor.get_stats()
        assert stats["read_errors"] == 1
        assert stats["param_timeouts"] == 1
        assert stats["param_crc_errors"] == 1

    def test_get_uptime(self, monitor):
        """Test uptime calculation."""
        # Small delay
        time.sleep(0.01)

        uptime = monitor.get_uptime()
        assert uptime >= 0.01

    def test_uptime_in_stats(self, monitor):
        """Test uptime is included in stats."""
        time.sleep(0.01)

        stats = monitor.get_stats()
        assert "uptime_s" in stats
        assert stats["uptime_s"] >= 0.01

    def test_reset(self, monitor):
        """Test resetting counters."""
        # Record some data
        monitor.record_bytes_read(1024)
        monitor.record_telemetry_packet()
        monitor.record_read_error()

        # Get uptime before reset
        time.sleep(0.01)
        uptime_before = monitor.get_uptime()

        # Reset
        monitor.reset()

        stats = monitor.get_stats()

        # Counters should be zero
        assert stats["bytes_read"] == 0
        assert stats["telemetry_packets"] == 0
        assert stats["read_errors"] == 0

        # Uptime should be unchanged (reset doesn't reset start_time)
        assert monitor.get_uptime() >= uptime_before

    def test_comprehensive_scenario(self, monitor):
        """Test realistic usage scenario."""
        # Simulate receiving data
        monitor.record_bytes_read(1024)
        monitor.record_telemetry_packet()
        monitor.record_bytes_read(512)
        monitor.record_telemetry_packet()

        # Simulate PARAM request
        monitor.record_bytes_written(18)
        monitor.record_param_request()
        monitor.record_bytes_read(54)
        monitor.record_param_response()

        # Simulate error
        monitor.record_read_error()

        stats = monitor.get_stats()

        assert stats["bytes_read"] == 1024 + 512 + 54
        assert stats["bytes_written"] == 18
        assert stats["telemetry_packets"] == 2
        assert stats["param_requests"] == 1
        assert stats["param_responses"] == 1
        assert stats["read_errors"] == 1
        assert stats["uptime_s"] >= 0
