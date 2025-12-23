"""
Tests for models.py - Pydantic models.
"""

import pytest
from pydantic import ValidationError

from app.models import (
    AttitudePacket,
    ControlPacket,
    HealthResponse,
    MotorsPacket,
    PacketHistoryResponse,
    ParamChangedBroadcast,
    ParamConnectionStatus,
    ParamConnectionStatusRest,
    ParamErrorResponse,
    ParamGetRequest,
    ParamGetResponse,
    ParamInfo,
    ParamListRequest,
    ParamListResponse,
    ParamRestResponse,
    ParamSetRequest,
    ParamSetResponse,
    ParamValueUpdate,
    PerformancePacket,
    SafetyPacket,
    SensorsPacket,
    StatusPacket,
)


class TestHealthResponse:
    """Test HealthResponse model."""

    def test_health_response_valid(self):
        """Test creating valid HealthResponse."""
        health = HealthResponse(
            status="healthy", last_packet_age_s=0.5, packets_received=100, is_alive=True
        )

        assert health.status == "healthy"
        assert health.last_packet_age_s == 0.5
        assert health.packets_received == 100
        assert health.is_alive is True

    def test_health_response_none_age(self):
        """Test HealthResponse with None age."""
        health = HealthResponse(status="unhealthy", last_packet_age_s=None, packets_received=0, is_alive=False)

        assert health.last_packet_age_s is None


class TestAttitudePacket:
    """Test AttitudePacket model."""

    def test_attitude_packet_valid(self):
        """Test creating valid AttitudePacket."""
        packet = AttitudePacket(
            ts_us=123456789,
            seq=42,
            roll_deg=-8.5,
            pitch_deg=10.2,
            yaw_deg=0.0,
            roll_rate_dps=-20.5,
            pitch_rate_dps=11.5,
            yaw_rate_dps=0.0,
        )

        assert packet.type == "ATT"
        assert packet.ts_us == 123456789
        assert packet.seq == 42
        assert packet.roll_deg == -8.5


class TestMotorsPacket:
    """Test MotorsPacket model."""

    def test_motors_packet_valid(self):
        """Test creating valid MotorsPacket."""
        packet = MotorsPacket(
            ts_us=123456789,
            seq=42,
            motors=[1000, 1000, 1000, 1000],
            motors_actual=[995, 998, 1002, 1000],
            throttle=500,
            mixer_id=1,
        )

        assert packet.type == "MOT"
        assert packet.motors == [1000, 1000, 1000, 1000]
        assert len(packet.motors_actual) == 4


class TestStatusPacket:
    """Test StatusPacket model."""

    def test_status_packet_valid(self):
        """Test creating valid StatusPacket."""
        packet = StatusPacket(
            ts_us=123456789,
            seq=42,
            armed=True,
            mode=1,
            ground_state=0,
            link_quality=95,
            battery_pct=80,
            uptime_s=3600,
            loop_rate_hz=500.0,
            flags={"HRZ": True, "CAL": True, "CALIB": False, "FAIL": False},
        )

        assert packet.type == "STA"
        assert packet.armed is True
        assert packet.link_quality == 95
        assert packet.flags["HRZ"] is True


class TestControlPacket:
    """Test ControlPacket model."""

    def test_control_packet_valid(self):
        """Test creating valid ControlPacket."""
        packet = ControlPacket(
            ts_us=123456789,
            seq=42,
            set_roll_deg=10.0,
            set_pitch_deg=5.0,
            set_yaw_rate_dps=0.0,
            rate_set_roll_dps=50.0,
            rate_set_pitch_dps=25.0,
            out_roll=0.5,
            out_pitch=0.3,
            out_yaw=0.0,
            pid_gains_scale=1.0,
            throttle_gain_scale=1.0,
        )

        assert packet.type == "CTL"
        assert packet.set_roll_deg == 10.0


class TestSensorsPacket:
    """Test SensorsPacket model."""

    def test_sensors_packet_valid(self):
        """Test creating valid SensorsPacket."""
        packet = SensorsPacket(
            ts_us=123456789,
            seq=42,
            accel_mg=[0, 0, 1000],
            gyro_mdps=[0, 0, 0],
            mag_mgauss=[200, 0, -400],
            temperature_c=25.5,
        )

        assert packet.type == "SENS"
        assert packet.accel_mg == [0, 0, 1000]
        assert packet.temperature_c == 25.5


class TestSafetyPacket:
    """Test SafetyPacket model."""

    def test_safety_packet_valid(self):
        """Test creating valid SafetyPacket."""
        packet = SafetyPacket(
            ts_us=123456789,
            seq=42,
            ground_confidence=0.95,
            safety_gates=0xFF,
            error_flags=0x00,
            total_flight_time_s=7200,
            crash_count=0,
        )

        assert packet.type == "SAFE"
        assert packet.ground_confidence == 0.95
        assert packet.crash_count == 0


class TestPerformancePacket:
    """Test PerformancePacket model."""

    def test_performance_packet_valid(self):
        """Test creating valid PerformancePacket."""
        packet = PerformancePacket(
            ts_us=123456789,
            seq=42,
            loop_time_us=2000,
            imu_time_us=500,
            control_time_us=300,
            cpu_usage_pct=25,
            free_heap_kb=150,
            stack_usage_pct=40,
        )

        assert packet.type == "PERF"
        assert packet.loop_time_us == 2000
        assert packet.cpu_usage_pct == 25


class TestPacketHistoryResponse:
    """Test PacketHistoryResponse model."""

    def test_packet_history_response(self):
        """Test creating PacketHistoryResponse."""
        response = PacketHistoryResponse(
            packet_type="ATT",
            count=3,
            packets=[
                {"type": "ATT", "seq": 1, "roll_deg": 0.0},
                {"type": "ATT", "seq": 2, "roll_deg": 1.0},
                {"type": "ATT", "seq": 3, "roll_deg": 2.0},
            ],
        )

        assert response.packet_type == "ATT"
        assert response.count == 3
        assert len(response.packets) == 3


class TestParamInfo:
    """Test ParamInfo model."""

    def test_param_info_valid(self):
        """Test creating valid ParamInfo."""
        param = ParamInfo(
            index=0, group="PID", name="P_GAIN", param_type=6, param_access=1, value=100.0
        )

        assert param.index == 0
        assert param.group == "PID"
        assert param.name == "P_GAIN"
        assert param.value == 100.0


class TestParamListResponse:
    """Test ParamListResponse model."""

    def test_param_list_response(self):
        """Test creating ParamListResponse."""
        response = ParamListResponse(
            params=[
                ParamInfo(index=0, group="PID", name="P_GAIN", param_type=6, param_access=1, value=100.0),
                ParamInfo(index=1, group="PID", name="I_GAIN", param_type=6, param_access=1, value=50.0),
            ]
        )

        assert response.type == "list_response"
        assert len(response.params) == 2


class TestParamGetResponse:
    """Test ParamGetResponse model."""

    def test_param_get_response_success(self):
        """Test successful GET response."""
        response = ParamGetResponse(index=0, value=100.0, status="success")

        assert response.type == "get_response"
        assert response.index == 0
        assert response.value == 100.0
        assert response.status == "success"


class TestParamSetResponse:
    """Test ParamSetResponse model."""

    def test_param_set_response_success(self):
        """Test successful SET response."""
        response = ParamSetResponse(index=0, value=200.0, status="success")

        assert response.type == "set_response"
        assert response.value == 200.0


class TestParamErrorResponse:
    """Test ParamErrorResponse model."""

    def test_param_error_response(self):
        """Test error response."""
        response = ParamErrorResponse(code="PARAM_NOT_FOUND", message="Parameter not found", index=99)

        assert response.type == "error"
        assert response.code == "PARAM_NOT_FOUND"
        assert response.index == 99

    def test_param_error_response_no_index(self):
        """Test error response without index."""
        response = ParamErrorResponse(code="UNKNOWN", message="Unknown error")

        assert response.index is None


class TestParamConnectionStatus:
    """Test ParamConnectionStatus model."""

    def test_param_connection_status(self):
        """Test connection status broadcast."""
        status = ParamConnectionStatus(
            uart_connected=True, controller_connected=True, timestamp="2025-12-23T10:00:00Z"
        )

        assert status.type == "connection_status"
        assert status.uart_connected is True


class TestParamChangedBroadcast:
    """Test ParamChangedBroadcast model."""

    def test_param_changed_broadcast(self):
        """Test parameter changed broadcast."""
        broadcast = ParamChangedBroadcast(index=0, value=150.0, changed_by="client123")

        assert broadcast.type == "param_changed"
        assert broadcast.index == 0
        assert broadcast.changed_by == "client123"


class TestParamRequests:
    """Test PARAM request models."""

    def test_param_list_request(self):
        """Test LIST request."""
        request = ParamListRequest()
        assert request.action == "list"

    def test_param_get_request(self):
        """Test GET request."""
        request = ParamGetRequest(index=5)
        assert request.action == "get"
        assert request.index == 5

    def test_param_get_request_validation(self):
        """Test GET request validation."""
        with pytest.raises(ValidationError):
            ParamGetRequest(index=256)  # Out of range

        with pytest.raises(ValidationError):
            ParamGetRequest(index=-1)  # Negative

    def test_param_set_request(self):
        """Test SET request."""
        request = ParamSetRequest(index=10, value=123.456)
        assert request.action == "set"
        assert request.index == 10
        assert request.value == 123.456

    def test_param_set_request_validation(self):
        """Test SET request validation."""
        with pytest.raises(ValidationError):
            ParamSetRequest(index=256, value=100.0)  # Index out of range


class TestParamRestModels:
    """Test PARAM REST API models."""

    def test_param_value_update(self):
        """Test ParamValueUpdate model."""
        update = ParamValueUpdate(value=999.999)
        assert update.value == 999.999

    def test_param_rest_response(self):
        """Test ParamRestResponse model."""
        response = ParamRestResponse(status="success", value=500.0)
        assert response.status == "success"
        assert response.value == 500.0

    def test_param_connection_status_rest(self):
        """Test ParamConnectionStatusRest model."""
        status = ParamConnectionStatusRest(uart_connected=True, last_update="2025-12-23T10:00:00Z")
        assert status.uart_connected is True
        assert status.last_update == "2025-12-23T10:00:00Z"

    def test_param_connection_status_rest_no_update(self):
        """Test ParamConnectionStatusRest without last_update."""
        status = ParamConnectionStatusRest(uart_connected=False)
        assert status.last_update is None
