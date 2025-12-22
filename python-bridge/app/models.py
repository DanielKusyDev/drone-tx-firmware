"""
Pydantic models for API request/response validation.

Author: Claude + Daniel
Date: 2025-12-20
"""

from typing import Any
from pydantic import BaseModel, Field


# === Telemetry Models ===


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Health status: 'healthy' or 'unhealthy'")
    last_packet_age_s: float | None = Field(None, description="Seconds since last packet")
    packets_received: int = Field(..., description="Total packets received")
    is_alive: bool = Field(..., description="Bridge is running")


class StatsResponse(BaseModel):
    """Comprehensive statistics response."""
    packets_parsed: int = Field(..., description="Total packets parsed")
    crc_errors: int = Field(..., description="CRC validation errors")
    unknown_types: int = Field(..., description="Unknown packet types")
    invalid_headers: int = Field(..., description="Invalid headers")
    bytes_discarded: int = Field(..., description="Bytes discarded during sync")
    packets_by_type: dict[str, int] = Field(..., description="Packet counts by type")
    last_packet_time: float | None = Field(None, description="Last packet timestamp")


class AttitudePacket(BaseModel):
    """ATTITUDE packet (roll, pitch, yaw + rates)."""
    type: str = Field("ATT", description="Packet type")
    ts_us: int = Field(..., description="Timestamp in microseconds")
    seq: int = Field(..., description="Sequence number")
    roll_deg: float = Field(..., description="Roll angle in degrees")
    pitch_deg: float = Field(..., description="Pitch angle in degrees")
    yaw_deg: float = Field(..., description="Yaw angle in degrees")
    roll_rate_dps: float = Field(..., description="Roll rate in degrees/sec")
    pitch_rate_dps: float = Field(..., description="Pitch rate in degrees/sec")
    yaw_rate_dps: float = Field(..., description="Yaw rate in degrees/sec")


class MotorsPacket(BaseModel):
    """MOTORS packet (motor commands, throttle)."""
    type: str = Field("MOT", description="Packet type")
    ts_us: int = Field(..., description="Timestamp in microseconds")
    seq: int = Field(..., description="Sequence number")
    motors: list[int] = Field(..., description="Motor commands (4 motors)")
    motors_actual: list[int] = Field(..., description="Actual motor outputs (4 motors)")
    throttle: int = Field(..., description="Throttle value")
    mixer_id: int = Field(..., description="Mixer table ID")


class StatusPacket(BaseModel):
    """STATUS packet (armed, flags, link quality)."""
    type: str = Field("STA", description="Packet type")
    ts_us: int = Field(..., description="Timestamp in microseconds")
    seq: int = Field(..., description="Sequence number")
    armed: bool = Field(..., description="Armed state")
    mode: int = Field(..., description="Flight mode")
    ground_state: int = Field(..., description="Ground state")
    link_quality: int = Field(..., description="Link quality (0-100)")
    battery_pct: int = Field(..., description="Battery percentage")
    uptime_s: int = Field(..., description="Uptime in seconds")
    loop_rate_hz: float = Field(..., description="Loop rate in Hz")
    flags: dict[str, bool] = Field(..., description="Safety flags")


class ControlPacket(BaseModel):
    """CONTROL packet (PID setpoints and outputs)."""
    type: str = Field("CTL", description="Packet type")
    ts_us: int = Field(..., description="Timestamp in microseconds")
    seq: int = Field(..., description="Sequence number")
    set_roll_deg: float = Field(..., description="Roll setpoint in degrees")
    set_pitch_deg: float = Field(..., description="Pitch setpoint in degrees")
    set_yaw_rate_dps: float = Field(..., description="Yaw rate setpoint in degrees/sec")
    rate_set_roll_dps: float = Field(..., description="Roll rate setpoint")
    rate_set_pitch_dps: float = Field(..., description="Pitch rate setpoint")
    out_roll: float = Field(..., description="Roll PID output")
    out_pitch: float = Field(..., description="Pitch PID output")
    out_yaw: float = Field(..., description="Yaw PID output")
    pid_gains_scale: float = Field(..., description="PID gains scale")
    throttle_gain_scale: float = Field(..., description="Throttle gain scale")


class SensorsPacket(BaseModel):
    """SENSORS packet (raw IMU data)."""
    type: str = Field("SENS", description="Packet type")
    ts_us: int = Field(..., description="Timestamp in microseconds")
    seq: int = Field(..., description="Sequence number")
    accel_mg: list[int] = Field(..., description="Accelerometer [x,y,z] in millig")
    gyro_mdps: list[int] = Field(..., description="Gyroscope [x,y,z] in milli-dps")
    mag_mgauss: list[int] = Field(..., description="Magnetometer [x,y,z] in milligauss")
    temperature_c: float = Field(..., description="Temperature in Celsius")


class SafetyPacket(BaseModel):
    """SAFETY packet (ground confidence, error flags)."""
    type: str = Field("SAFE", description="Packet type")
    ts_us: int = Field(..., description="Timestamp in microseconds")
    seq: int = Field(..., description="Sequence number")
    ground_confidence: float = Field(..., description="Ground confidence (0.0-1.0)")
    safety_gates: int = Field(..., description="Safety gates bitfield")
    error_flags: int = Field(..., description="Error flags")
    total_flight_time_s: int = Field(..., description="Total flight time in seconds")
    crash_count: int = Field(..., description="Crash count")


class PerformancePacket(BaseModel):
    """PERFORMANCE packet (loop timing, CPU, heap)."""
    type: str = Field("PERF", description="Packet type")
    ts_us: int = Field(..., description="Timestamp in microseconds")
    seq: int = Field(..., description="Sequence number")
    loop_time_us: int = Field(..., description="Loop time in microseconds")
    imu_time_us: int = Field(..., description="IMU update time in microseconds")
    control_time_us: int = Field(..., description="Control loop time in microseconds")
    cpu_usage_pct: int = Field(..., description="CPU usage percentage")
    free_heap_kb: int = Field(..., description="Free heap in KB")
    stack_usage_pct: int = Field(..., description="Stack usage percentage")


class LatestTelemetryResponse(BaseModel):
    """Latest packets of each type."""
    ATT: AttitudePacket | None = None
    MOT: MotorsPacket | None = None
    STA: StatusPacket | None = None
    CTL: ControlPacket | None = None
    SENS: SensorsPacket | None = None
    SAFE: SafetyPacket | None = None
    PERF: PerformancePacket | None = None


class PacketHistoryResponse(BaseModel):
    """Packet history response."""
    packet_type: str = Field(..., description="Packet type (ATT, MOT, STA, etc.)")
    count: int = Field(..., description="Number of packets in history")
    packets: list[dict[str, Any]] = Field(..., description="List of packets")


class PortsResponse(BaseModel):
    """Available serial ports response."""
    ports: list[str] = Field(..., description="List of available serial ports")


# === PARAM Models ===


class ParamInfo(BaseModel):
    """Parameter information."""
    index: int = Field(..., description="Parameter index (0-255)")
    group: str = Field(..., description="Parameter group name (max 16 chars)")
    name: str = Field(..., description="Parameter name (max 16 chars)")
    param_type: int = Field(..., description="Parameter type (6=float)")
    param_access: int = Field(..., description="Access: 0=readonly, 1=readwrite")
    value: float = Field(..., description="Current parameter value")


class ParamListResponse(BaseModel):
    """Response to LIST command."""
    type: str = Field("list_response", description="Response type")
    params: list[ParamInfo] = Field(..., description="List of all parameters")


class ParamGetResponse(BaseModel):
    """Response to GET command."""
    type: str = Field("get_response", description="Response type")
    index: int = Field(..., description="Parameter index")
    value: float = Field(..., description="Parameter value")
    status: str = Field(..., description="Status: 'success' or 'error'")


class ParamSetResponse(BaseModel):
    """Response to SET command."""
    type: str = Field("set_response", description="Response type")
    index: int = Field(..., description="Parameter index")
    value: float = Field(..., description="New parameter value")
    status: str = Field(..., description="Status: 'success' or 'error'")


class ParamErrorResponse(BaseModel):
    """Error response."""
    type: str = Field("error", description="Response type")
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    index: int | None = Field(None, description="Parameter index if applicable")


class ParamConnectionStatus(BaseModel):
    """PARAM connection status broadcast."""
    type: str = Field("connection_status", description="Message type")
    uart_connected: bool = Field(..., description="UART connection status")
    controller_connected: bool = Field(..., description="Controller sees drone")
    timestamp: str = Field(..., description="ISO timestamp")


class ParamChangedBroadcast(BaseModel):
    """Parameter changed broadcast."""
    type: str = Field("param_changed", description="Message type")
    index: int = Field(..., description="Parameter index")
    value: float = Field(..., description="New value")
    changed_by: str = Field(..., description="Client ID that changed the parameter")


# === PARAM Request Models (WebSocket) ===


class ParamListRequest(BaseModel):
    """LIST request."""
    action: str = Field("list", description="Action: 'list'")


class ParamGetRequest(BaseModel):
    """GET request."""
    action: str = Field("get", description="Action: 'get'")
    index: int = Field(..., description="Parameter index", ge=0, le=255)


class ParamSetRequest(BaseModel):
    """SET request."""
    action: str = Field("set", description="Action: 'set'")
    index: int = Field(..., description="Parameter index", ge=0, le=255)
    value: float = Field(..., description="New parameter value")


# === PARAM REST Models ===


class ParamValueUpdate(BaseModel):
    """Request body for PUT /api/params/{index}."""
    value: float = Field(..., description="New parameter value")


class ParamRestResponse(BaseModel):
    """Response for PUT /api/params/{index}."""
    status: str = Field(..., description="Status: 'success' or 'error'")
    value: float = Field(..., description="Parameter value")


class ParamConnectionStatusRest(BaseModel):
    """Response for GET /api/params/connection-status."""
    uart_connected: bool = Field(..., description="UART connection status")
    last_update: str | None = Field(None, description="ISO timestamp of last update")
