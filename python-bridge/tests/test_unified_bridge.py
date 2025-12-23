"""
Tests for UnifiedBridge - main coordinator for telemetry and PARAM communication.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.packet_router import RouteDestination
from app.services.unified_bridge import UnifiedBridge


class TestUnifiedBridgeInit:
    """Test UnifiedBridge initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        bridge = UnifiedBridge("COM3")

        assert bridge.port == "COM3"
        assert bridge.baudrate == 115200
        assert bridge.serial is not None
        assert bridge.parser is not None
        assert bridge.router is not None
        assert bridge.telemetry is not None
        assert bridge.param is not None
        assert bridge.health is not None
        assert bridge._running is False

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        bridge = UnifiedBridge("/dev/ttyUSB0", baudrate=9600, history_size=2000, param_timeout=5.0)

        assert bridge.port == "/dev/ttyUSB0"
        assert bridge.baudrate == 9600
        assert bridge.telemetry.history_size == 2000
        assert bridge.param.timeout == 5.0


class TestUnifiedBridgeLifecycle:
    """Test start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_success(self):
        """Test successfully starting bridge."""
        bridge = UnifiedBridge("COM3")

        with patch.object(bridge.serial, "open", new_callable=AsyncMock) as mock_open:
            with patch("asyncio.create_task") as mock_create_task:
                await bridge.start()

                # Verify
                mock_open.assert_awaited_once()
                mock_create_task.assert_called_once()
                assert bridge.is_running() is True

        # Cleanup
        bridge._running = False

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Test starting already-running bridge."""
        bridge = UnifiedBridge("COM3")
        bridge._running = True

        with pytest.raises(RuntimeError, match="already running"):
            await bridge.start()

    @pytest.mark.asyncio
    async def test_stop_success(self):
        """Test successfully stopping bridge."""
        bridge = UnifiedBridge("COM3")

        # Mock components
        bridge.serial.open = AsyncMock()
        bridge.serial.close = AsyncMock()

        # Start bridge
        await bridge.start()

        # Create a real task that completes immediately
        async def dummy_task():
            pass

        bridge._read_task = asyncio.create_task(dummy_task())

        # Stop
        await bridge.stop()

        # Verify
        assert bridge.is_running() is False
        bridge.serial.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_not_running(self):
        """Test stopping non-running bridge."""
        bridge = UnifiedBridge("COM3")

        # Should not raise
        await bridge.stop()
        assert bridge.is_running() is False

    @pytest.mark.asyncio
    async def test_stop_with_timeout_cancellation(self):
        """Test stop with read task timeout and cancellation."""
        bridge = UnifiedBridge("COM3")

        bridge.serial.open = AsyncMock()
        bridge.serial.close = AsyncMock()

        await bridge.start()

        # Create a task that never completes
        async def never_ending_task():
            while True:
                await asyncio.sleep(1)

        bridge._read_task = asyncio.create_task(never_ending_task())

        # Stop with very short timeout
        await bridge.stop(timeout=0.01)

        # Should be stopped and task cancelled
        assert bridge.is_running() is False
        assert bridge._read_task is None

    @pytest.mark.asyncio
    async def test_is_connected(self):
        """Test is_connected status."""
        bridge = UnifiedBridge("COM3")
        bridge.serial.is_open = MagicMock(return_value=True)

        assert bridge.is_connected() is True


class TestTelemetryFeatures:
    """Test telemetry-related features."""

    @pytest.mark.asyncio
    async def test_set_telemetry_callback(self):
        """Test setting telemetry callback."""
        bridge = UnifiedBridge("COM3")

        async def my_callback(packet):
            pass

        bridge.set_telemetry_callback(my_callback)
        assert bridge._telemetry_callback is my_callback

    @pytest.mark.asyncio
    async def test_get_latest_attitude(self):
        """Test getting latest ATTITUDE packet."""
        bridge = UnifiedBridge("COM3")

        # Mock telemetry store
        expected_packet = {"type": "ATT", "roll_deg": 10.5}
        bridge.telemetry.get_latest = AsyncMock(return_value=expected_packet)

        packet = await bridge.get_latest_attitude()
        assert packet == expected_packet
        bridge.telemetry.get_latest.assert_awaited_once_with("ATT")

    @pytest.mark.asyncio
    async def test_get_latest_motors(self):
        """Test getting latest MOTORS packet."""
        bridge = UnifiedBridge("COM3")

        expected_packet = {"type": "MOT", "motors": [100, 100, 100, 100]}
        bridge.telemetry.get_latest = AsyncMock(return_value=expected_packet)

        packet = await bridge.get_latest_motors()
        assert packet == expected_packet
        bridge.telemetry.get_latest.assert_awaited_once_with("MOT")

    @pytest.mark.asyncio
    async def test_get_latest_status(self):
        """Test getting latest STATUS packet."""
        bridge = UnifiedBridge("COM3")

        expected_packet = {"type": "STA", "armed": False}
        bridge.telemetry.get_latest = AsyncMock(return_value=expected_packet)

        packet = await bridge.get_latest_status()
        assert packet == expected_packet
        bridge.telemetry.get_latest.assert_awaited_once_with("STA")

    @pytest.mark.asyncio
    async def test_get_latest_packet(self):
        """Test getting latest packet by type."""
        bridge = UnifiedBridge("COM3")

        expected_packet = {"type": "CTL", "out_roll": 0.5}
        bridge.telemetry.get_latest = AsyncMock(return_value=expected_packet)

        packet = await bridge.get_latest_packet("CTL")
        assert packet == expected_packet
        bridge.telemetry.get_latest.assert_awaited_once_with("CTL")

    @pytest.mark.asyncio
    async def test_get_latest_packets(self):
        """Test getting all latest packets."""
        bridge = UnifiedBridge("COM3")

        expected_packets = {
            "ATT": {"type": "ATT", "roll_deg": 10.5},
            "MOT": None,
            "STA": {"type": "STA", "armed": False},
        }
        bridge.telemetry.get_all_latest = AsyncMock(return_value=expected_packets)

        packets = await bridge.get_latest_packets()
        assert packets == expected_packets

    @pytest.mark.asyncio
    async def test_get_packet_history(self):
        """Test getting packet history."""
        bridge = UnifiedBridge("COM3")

        expected_history = [
            {"type": "ATT", "seq": 1},
            {"type": "ATT", "seq": 2},
            {"type": "ATT", "seq": 3},
        ]
        bridge.telemetry.get_history = AsyncMock(return_value=expected_history)

        history = await bridge.get_packet_history("ATT", max_count=3)
        assert history == expected_history
        bridge.telemetry.get_history.assert_awaited_once_with("ATT", 3)


class TestParamFeatures:
    """Test PARAM-related features."""

    @pytest.mark.asyncio
    async def test_list_params(self):
        """Test listing parameters."""
        bridge = UnifiedBridge("COM3")

        expected_params = [
            {"index": 0, "name": "P_GAIN", "value": 100.0},
            {"index": 1, "name": "I_GAIN", "value": 50.0},
        ]
        bridge.param.list_params = AsyncMock(return_value=expected_params)

        params = await bridge.list_params()
        assert params == expected_params
        assert bridge.param.list_params.await_count == 1

    @pytest.mark.asyncio
    async def test_get_param(self):
        """Test getting parameter value."""
        bridge = UnifiedBridge("COM3")

        bridge.param.get_param = AsyncMock(return_value=123.456)

        value = await bridge.get_param(5)
        assert value == 123.456
        assert bridge.param.get_param.await_count == 1

    @pytest.mark.asyncio
    async def test_set_param(self):
        """Test setting parameter value."""
        bridge = UnifiedBridge("COM3")

        bridge.param.set_param = AsyncMock(return_value=True)

        result = await bridge.set_param(10, 999.0)
        assert result is True
        assert bridge.param.set_param.await_count == 1

    @pytest.mark.asyncio
    async def test_send_param_request(self):
        """Test sending PARAM request."""
        bridge = UnifiedBridge("COM3")

        bridge.serial.write = AsyncMock()
        packet = b"\x5B\x02\x10\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

        await bridge._send_param_request(packet)

        bridge.serial.write.assert_awaited_once_with(packet)
        assert bridge.health.get_stats()["bytes_written"] == len(packet)
        assert bridge.health.get_stats()["param_requests"] == 1


class TestHealthAndStats:
    """Test health checking and statistics."""

    @pytest.mark.asyncio
    async def test_get_health(self):
        """Test getting health status."""
        bridge = UnifiedBridge("COM3")
        bridge._running = True

        # Mock telemetry health
        bridge.telemetry.get_health = AsyncMock(
            return_value={
                "packets_received": 100,
                "packets_by_type": {"ATT": 50, "MOT": 30},
                "last_packet_age_s": 0.5,
            }
        )

        health = await bridge.get_health()

        assert health["is_alive"] is True
        assert health["packets_received"] == 100
        assert health["packets_by_type"] == {"ATT": 50, "MOT": 30}
        assert health["last_packet_age_s"] == 0.5

    @pytest.mark.asyncio
    async def test_is_healthy(self):
        """Test health check."""
        bridge = UnifiedBridge("COM3")
        bridge._running = True

        bridge.telemetry.is_healthy = AsyncMock(return_value=True)

        healthy = await bridge.is_healthy(max_age_s=5.0)
        assert healthy is True
        bridge.telemetry.is_healthy.assert_awaited_once_with(5.0)

    @pytest.mark.asyncio
    async def test_is_healthy_not_running(self):
        """Test health check when not running."""
        bridge = UnifiedBridge("COM3")
        bridge._running = False

        healthy = await bridge.is_healthy()
        assert healthy is False

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting comprehensive statistics."""
        bridge = UnifiedBridge("COM3")

        stats = await bridge.get_stats()

        # Verify structure
        assert "health" in stats
        assert "parser" in stats
        assert "router" in stats
        assert "telemetry" in stats
        assert "param" in stats

    def test_get_param_stats(self):
        """Test getting PARAM statistics."""
        bridge = UnifiedBridge("COM3")

        param_stats = bridge.get_param_stats()
        assert "requests_sent" in param_stats
        assert "responses_received" in param_stats

    @pytest.mark.asyncio
    async def test_reset_stats(self):
        """Test resetting statistics."""
        bridge = UnifiedBridge("COM3")

        # Record some activity
        bridge.health.record_bytes_read(100)
        bridge.router.route({"type": "ATT"})
        bridge.param.build_request(0, 0)

        # Reset
        await bridge.reset_stats()

        # Verify reset
        health_stats = bridge.health.get_stats()
        router_stats = bridge.router.get_stats()
        param_stats = bridge.param.get_stats()

        assert health_stats["bytes_read"] == 0
        assert router_stats["telemetry_routed"] == 0
        assert param_stats["requests_sent"] == 0


class TestPacketRouting:
    """Test packet routing and handling."""

    @pytest.mark.asyncio
    async def test_route_telemetry_packet(self):
        """Test routing telemetry packet."""
        bridge = UnifiedBridge("COM3")

        bridge.router.route = MagicMock(return_value=RouteDestination.TELEMETRY)
        bridge.telemetry.add = AsyncMock()

        packet = {"type": "ATT", "roll_deg": 10.5}
        await bridge._route_packet(packet)

        bridge.telemetry.add.assert_awaited_once_with(packet)
        assert bridge.health.get_stats()["telemetry_packets"] == 1

    @pytest.mark.asyncio
    async def test_route_telemetry_with_callback(self):
        """Test routing telemetry with callback."""
        bridge = UnifiedBridge("COM3")
        callback_called = False

        async def my_callback(packet):
            nonlocal callback_called
            callback_called = True

        bridge.set_telemetry_callback(my_callback)
        bridge.router.route = MagicMock(return_value=RouteDestination.TELEMETRY)
        bridge.telemetry.add = AsyncMock()

        packet = {"type": "ATT", "roll_deg": 10.5}
        await bridge._route_packet(packet)

        assert callback_called is True

    @pytest.mark.asyncio
    async def test_route_telemetry_callback_exception(self):
        """Test routing telemetry handles callback exceptions."""
        bridge = UnifiedBridge("COM3")

        async def failing_callback(packet):
            raise RuntimeError("Callback failed")

        bridge.set_telemetry_callback(failing_callback)
        bridge.router.route = MagicMock(return_value=RouteDestination.TELEMETRY)
        bridge.telemetry.add = AsyncMock()

        packet = {"type": "ATT", "roll_deg": 10.5}

        # Should not raise (exception is caught and logged)
        await bridge._route_packet(packet)

        # Telemetry should still be stored
        bridge.telemetry.add.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_route_param_response(self):
        """Test routing PARAM response."""
        bridge = UnifiedBridge("COM3")

        bridge.router.route = MagicMock(return_value=RouteDestination.PARAM_RESPONSE)
        bridge.param.parse_response = MagicMock(return_value={"param_index": 0, "value": 100.0})
        bridge.param.handle_response = AsyncMock()

        # PARAM response packet with raw_data
        packet = {"type": "PARAM_RESP", "raw_data": b"\x5B" + b"\x00" * 53}
        await bridge._route_packet(packet)

        bridge.param.handle_response.assert_awaited_once()
        assert bridge.health.get_stats()["param_responses"] == 1

    @pytest.mark.asyncio
    async def test_route_param_response_parse_error(self):
        """Test routing PARAM response with parse error."""
        bridge = UnifiedBridge("COM3")

        bridge.router.route = MagicMock(return_value=RouteDestination.PARAM_RESPONSE)
        bridge.param.parse_response = MagicMock(side_effect=Exception("Parse failed"))

        # PARAM response packet with raw_data
        packet = {"type": "PARAM_RESP", "raw_data": b"\x5B" + b"\x00" * 53}

        # Should not raise (exception is caught and logged)
        await bridge._route_packet(packet)

        # Health stats should not increment param_responses
        assert bridge.health.get_stats()["param_responses"] == 0

    @pytest.mark.asyncio
    async def test_route_unknown_packet(self):
        """Test routing unknown packet type."""
        bridge = UnifiedBridge("COM3")

        bridge.router.route = MagicMock(return_value=RouteDestination.UNKNOWN)

        packet = {"type": "UNKNOWN", "data": "test"}
        # Should not raise
        await bridge._route_packet(packet)


class TestReadLoop:
    """Test read loop functionality."""

    @pytest.mark.asyncio
    async def test_read_loop_processes_packets(self):
        """Test read loop reads and routes packets."""
        bridge = UnifiedBridge("COM3")

        packets_routed = []

        # Mock serial read
        read_count = 0

        async def mock_read(size):
            nonlocal read_count
            read_count += 1
            if read_count == 1:
                return b"\x5B\x02\x01\x00\x01\x00\x00\x00\x00\x00" + b"\x00" * 14  # Partial packet
            else:
                # Stop loop
                bridge._running = False
                return b""

        async def mock_route_packet(packet):
            packets_routed.append(packet)

        bridge.serial.read = mock_read
        bridge.parser.feed = MagicMock(return_value=[{"type": "ATT", "seq": 1}])
        bridge._route_packet = mock_route_packet

        # Run loop briefly
        bridge._running = True
        await bridge._read_loop()

        # Verify read was called and packets were routed
        assert read_count >= 1
        assert len(packets_routed) >= 1

    @pytest.mark.asyncio
    async def test_read_loop_handles_serial_error(self):
        """Test read loop handles serial errors gracefully."""
        bridge = UnifiedBridge("COM3")

        # Mock serial read that raises error once then stops
        call_count = 0

        async def mock_read(size):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                from app.core.serial_connection import SerialConnectionError

                raise SerialConnectionError("USB disconnected")
            else:
                bridge._running = False
                return b""

        bridge.serial.read = mock_read

        # Run loop
        bridge._running = True
        await bridge._read_loop()

        # Should have recorded error
        assert bridge.health.get_stats()["read_errors"] >= 1

    @pytest.mark.asyncio
    async def test_read_loop_handles_general_exception(self):
        """Test read loop handles general exceptions gracefully."""
        bridge = UnifiedBridge("COM3")

        call_count = 0

        async def mock_read(size):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Raise general exception (not SerialConnectionError)
                raise RuntimeError("Unexpected error")
            else:
                bridge._running = False
                return b""

        bridge.serial.read = mock_read

        # Run loop
        bridge._running = True
        await bridge._read_loop()

        # Should have recorded error
        assert bridge.health.get_stats()["read_errors"] >= 1


class TestContextManager:
    """Test async context manager support."""

    @pytest.mark.asyncio
    async def test_context_manager_success(self):
        """Test context manager starts and stops."""
        bridge = UnifiedBridge("COM3")

        bridge.serial.open = AsyncMock()
        bridge.serial.close = AsyncMock()

        async with bridge:
            assert bridge.is_running() is True

        # Should be stopped
        assert bridge.is_running() is False
        bridge.serial.close.assert_awaited()

    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self):
        """Test context manager stops even on exception."""
        bridge = UnifiedBridge("COM3")

        bridge.serial.open = AsyncMock()
        bridge.serial.close = AsyncMock()

        with pytest.raises(ValueError):
            async with bridge:
                raise ValueError("Test error")

        # Should still be stopped
        assert bridge.is_running() is False
        bridge.serial.close.assert_awaited()


class TestUtilityMethods:
    """Test utility methods."""

    def test_list_ports(self):
        """Test listing serial ports."""
        mock_ports = [
            {"device": "COM3", "description": "USB Serial", "hwid": "1234"},
            {"device": "COM4", "description": "ESP32", "hwid": "5678"},
        ]

        with patch("app.core.serial_connection.SerialConnection.list_ports") as mock_list:
            mock_list.return_value = mock_ports

            ports = UnifiedBridge.list_ports()
            assert ports == mock_ports
