"""
Tests for TelemetryStore.

Run with:
    pytest tests/test_telemetry_store.py -v
"""

import asyncio

import pytest

from app.core.telemetry_store import TelemetryStore


@pytest.fixture
def store():
    """Create fresh store for each test."""
    return TelemetryStore(history_size=10)


@pytest.mark.asyncio
class TestTelemetryStore:
    """Test telemetry data storage."""

    async def test_add_packet(self, store):
        """Test adding packet to store."""
        packet = {"type": "ATT", "seq": 1, "roll_deg": 5.0}

        await store.add(packet)

        latest = await store.get_latest("ATT")
        assert latest == packet

    async def test_add_multiple_packets_same_type(self, store):
        """Test that latest overwrites previous."""
        packet1 = {"type": "ATT", "seq": 1, "roll_deg": 5.0}
        packet2 = {"type": "ATT", "seq": 2, "roll_deg": 10.0}

        await store.add(packet1)
        await store.add(packet2)

        latest = await store.get_latest("ATT")
        assert latest == packet2

    async def test_add_different_types(self, store):
        """Test adding different packet types."""
        att_packet = {"type": "ATT", "seq": 1}
        mot_packet = {"type": "MOT", "seq": 1}

        await store.add(att_packet)
        await store.add(mot_packet)

        assert await store.get_latest("ATT") == att_packet
        assert await store.get_latest("MOT") == mot_packet

    async def test_get_latest_not_received(self, store):
        """Test getting latest when packet never received."""
        latest = await store.get_latest("ATT")
        assert latest is None

    async def test_get_all_latest(self, store):
        """Test getting all latest packets."""
        att_packet = {"type": "ATT", "seq": 1}
        mot_packet = {"type": "MOT", "seq": 1}

        await store.add(att_packet)
        await store.add(mot_packet)

        all_latest = await store.get_all_latest()

        assert all_latest["ATT"] == att_packet
        assert all_latest["MOT"] == mot_packet
        assert all_latest["STA"] is None  # Not received

    async def test_history_fifo(self, store):
        """Test history buffer is FIFO."""
        # Add 15 packets (history size is 10)
        for i in range(15):
            await store.add({"type": "ATT", "seq": i})

        history = await store.get_history()

        # Should have only last 10
        assert len(history) == 10
        assert history[0]["seq"] == 5  # Oldest
        assert history[-1]["seq"] == 14  # Newest

    async def test_history_filter_by_type(self, store):
        """Test filtering history by type."""
        await store.add({"type": "ATT", "seq": 1})
        await store.add({"type": "MOT", "seq": 1})
        await store.add({"type": "ATT", "seq": 2})

        history = await store.get_history(packet_type="ATT")

        assert len(history) == 2
        assert all(p["type"] == "ATT" for p in history)

    async def test_history_max_count(self, store):
        """Test limiting history count."""
        for i in range(10):
            await store.add({"type": "ATT", "seq": i})

        history = await store.get_history(max_count=5)

        assert len(history) == 5
        assert history[-1]["seq"] == 9  # Newest

    async def test_health_tracking(self, store):
        """Test health status tracking."""
        await store.add({"type": "ATT", "seq": 1})
        await store.add({"type": "MOT", "seq": 1})

        health = await store.get_health()

        assert health["packets_received"] == 2
        assert health["packets_by_type"]["ATT"] == 1
        assert health["packets_by_type"]["MOT"] == 1
        assert health["last_packet_age_s"] is not None
        assert health["last_packet_age_s"] < 1.0  # Just added

    async def test_is_healthy(self, store):
        """Test health check."""
        # No packets yet
        assert await store.is_healthy() is False

        # Add packet
        await store.add({"type": "ATT", "seq": 1})
        assert await store.is_healthy() is True

        # Wait for packet to age
        await asyncio.sleep(0.1)
        assert await store.is_healthy(max_age_s=10.0) is True
        assert await store.is_healthy(max_age_s=0.01) is False

    async def test_clear(self, store):
        """Test clearing store."""
        await store.add({"type": "ATT", "seq": 1})
        await store.add({"type": "MOT", "seq": 1})

        await store.clear()

        assert await store.get_latest("ATT") is None
        assert await store.get_latest("MOT") is None

        history = await store.get_history()
        assert len(history) == 0

        health = await store.get_health()
        assert health["packets_received"] == 0

    async def test_add_packet_without_type(self, store):
        """Test adding packet without type field."""
        packet = {"seq": 1}

        await store.add(packet)

        # Should not be stored
        history = await store.get_history()
        assert len(history) == 0
