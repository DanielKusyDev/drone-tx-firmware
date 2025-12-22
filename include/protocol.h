#pragma once
#include <cstdint>
#include <cstddef>

#pragma pack(push,1)
struct RcPacket {
    uint8_t  magic;     // 0xA5
    uint8_t  version;   // 1
    uint16_t seq;       // sequence counter, wraps around
    uint16_t thr;       // 0..1000
    int16_t  yaw;       // -1000..1000
    int16_t  pitch;     // -1000..1000
    int16_t  roll;      // -1000..1000
    uint8_t  flags;     // bit0 = ARM state, bit1 = CALIBRATE
    uint8_t  rssi_hint; // optional RSSI info
    uint16_t crc;       // CRC-16/X.25 of all fields except crc
};

#pragma pack(pop)

// Packet constants
#define RC_PACKET_MAGIC   0xA5
#define RC_PACKET_VERSION 1
#define RC_FLAG_ARMED     0x01
#define RC_FLAG_CALIBRATE 0x02
#define RC_FLAG_DEBUG     0x04

// Telemetry safety_flags bitfield constants (used in TelemetryStatus packet)
// Updated flag mapping - removed redundant flags (linkAlive, cal_ok, cal_failed)
#define TELEM_HORIZON_BIT           0x01  // bit 0: horizon/level OK state
#define TELEM_FORCE_DISARM          0x02  // bit 1: force disarm triggered
#define TELEM_FLAG_CALIBRATING      0x04  // bit 2: calibration in progress
#define TELEM_LOW_BATTERY           0x08  // bit 3: low battery detected
#define TELEM_SENSOR_FAILURE        0x10  // bit 4: sensor failure (NaN/Inf/extreme values)
#define TELEM_FAILSAFE_ACTIVE       0x20  // bit 5: failsafe active (RC loss or emergency)
#define TELEM_ANGLE_LIMIT_EXCEEDED  0x40  // bit 6: angle limit exceeded (>22°)

// Telemetry armed bitfield constants (used in TelemetryStatus packet)
#define TELEM_ARMED_BIT        0x01  // bit 0: drone armed state

// CRC-16/X.25 calculation
uint16_t crc16_x25(const uint8_t* data, size_t len);

// ============================================================================
// Enhanced Telemetry System (Version 2)
// ============================================================================

// Enhanced telemetry packet types
enum TelemetryPacketType : uint8_t {
    TELEM_TYPE_ATTITUDE     = 0x01,  // Flight attitude data (20Hz)
    TELEM_TYPE_CONTROL      = 0x02,  // PID control data (10Hz)
    TELEM_TYPE_MOTORS       = 0x03,  // Motor and mixer data (5Hz)
    TELEM_TYPE_STATUS       = 0x04,  // System status (2.5Hz)
    TELEM_TYPE_SENSORS      = 0x05,  // Raw sensor data (1.25Hz)
    TELEM_TYPE_SAFETY       = 0x06,  // Safety and diagnostics (1.25Hz)
    TELEM_TYPE_PERFORMANCE  = 0x07,  // Performance metrics (0.625Hz)
    TELEM_TYPE_PARAM_REQUEST  = 0x10,  // Parameter request (on-demand)
    TELEM_TYPE_PARAM_RESPONSE = 0x11   // Parameter response (on-demand)
};

// Enhanced telemetry constants
#define TELEM_ENHANCED_MAGIC   0x5B
#define TELEM_ENHANCED_VERSION 2

// Packet flags
#define TELEM_FLAG_COMPRESSED  0x01
#define TELEM_FLAG_ACK_REQ     0x02

// Common header for all enhanced telemetry packets (10 bytes packed)
#pragma pack(push, 1)
struct TelemetryHeader {
    uint8_t magic;           // 0x5B (enhanced telemetry identifier)
    uint8_t version;         // 2 (enhanced version)
    uint8_t type;            // TelemetryPacketType
    uint8_t flags;           // Packet flags (compression, ack_req, etc.)
    uint16_t seq;            // Sequence number (per packet type)
    uint32_t timestamp_us;   // Microsecond timestamp
};

// 1. ATTITUDE (0x01) - Flight Attitude Data (24 bytes total)
struct TelemetryAttitude {
    TelemetryHeader header;      // 10 bytes
    int16_t roll_deg_x100;       // Roll angle in 0.01° units
    int16_t pitch_deg_x100;      // Pitch angle in 0.01° units
    int16_t yaw_deg_x100;        // Yaw angle in 0.01° units
    int16_t roll_rate_dps_x10;   // Roll rate in 0.1°/s units
    int16_t pitch_rate_dps_x10;  // Pitch rate in 0.1°/s units
    int16_t yaw_rate_dps_x10;    // Yaw rate in 0.1°/s units
    uint16_t crc;                // 12 bytes data + 2 CRC = 24 total
};

// 2. CONTROL (0x02) - PID Control Data (30 bytes total)
struct TelemetryControl {
    TelemetryHeader header;              // 10 bytes
    int16_t set_roll_deg_x100;           // Roll angle setpoint in 0.01° units (from RC)
    int16_t set_pitch_deg_x100;          // Pitch angle setpoint in 0.01° units (from RC)
    int16_t set_yaw_rate_dps_x10;        // Yaw rate setpoint in 0.1°/s units (from RC)
    int16_t rate_set_roll_dps_x10;       // Roll rate setpoint from angle PID in 0.1°/s units
    int16_t rate_set_pitch_dps_x10;      // Pitch rate setpoint from angle PID in 0.1°/s units
    int16_t out_roll_x10;                // Roll rate PID output x10
    int16_t out_pitch_x10;               // Pitch rate PID output x10
    int16_t out_yaw_x10;                 // Yaw rate PID output x10
    uint8_t pid_gains_scale_x100;        // Ground safety gain scaling factor x100
    uint8_t throttle_gain_scale_x100;    // Throttle-dependent gain scaling factor x100
    uint16_t crc;                        // 18 bytes data + 2 CRC = 30 total
};

// 3. MOTORS (0x03) - Motor and Mixer Data (31 bytes total)
struct TelemetryMotors {
    TelemetryHeader header;      // 10 bytes
    uint16_t motor_cmd[4];       // Motor commands 0-1000
    uint16_t motor_actual[4];    // Actual motor outputs (if feedback available)
    uint16_t throttle;           // Base throttle
    uint8_t mixer_table_id;      // Active mixer table ID
    uint16_t crc;                // 19 bytes data + 2 CRC = 31 total
};

// 4. STATUS (0x04) - System Status (24 bytes total)
struct TelemetryStatus {
    TelemetryHeader header;      // 10 bytes
    uint8_t armed;               // Arming state
    uint8_t flight_mode;         // Flight mode
    uint8_t safety_flags;        // Safety system flags
    uint8_t ground_state;        // Ground detection state
    uint8_t link_quality;        // RC link quality 0-100
    uint8_t battery_pct;         // Battery percentage (future use)
    uint16_t uptime_s;           // System uptime in seconds
    uint32_t loop_rate_hz_x10;   // Main loop rate x10
    uint16_t crc;                // 12 bytes data + 2 CRC = 24 total
};

// 5. SENSORS (0x05) - Raw Sensor Data (30 bytes total)
struct TelemetrySensors {
    TelemetryHeader header;      // 10 bytes
    int16_t accel_mg[3];         // Accelerometer in millig
    int16_t gyro_mdps[3];        // Gyroscope in milli-dps
    int16_t mag_mgauss[3];       // Magnetometer in milligauss (future)
    int16_t temperature_c_x10;   // Temperature in 0.1°C
    uint16_t crc;                // 18 bytes data + 2 CRC = 30 total
};

// 6. SAFETY (0x06) - Safety and Diagnostics (20 bytes total)
struct TelemetrySafety {
    TelemetryHeader header;      // 10 bytes
    uint8_t ground_confidence_x100;  // Ground detection confidence x100
    uint8_t safety_gates;        // Active safety gates bitmask
    uint16_t error_flags;        // System error flags
    uint32_t total_flight_time_s;// Total flight time
    uint16_t crash_count;        // Crash detection counter
    uint16_t crc;                // 8 bytes data + 2 CRC = 20 total
};

// 7. PERFORMANCE (0x07) - Performance Metrics (22 bytes total)
struct TelemetryPerformance {
    TelemetryHeader header;      // 10 bytes
    uint16_t loop_time_us;       // Main loop execution time
    uint16_t imu_time_us;        // IMU read time
    uint16_t control_time_us;    // Control computation time
    uint8_t cpu_usage_pct;       // CPU usage percentage
    uint16_t free_heap_kb;       // Free heap in KB
    uint8_t stack_usage_pct;     // Stack usage percentage
    uint16_t crc;                // 10 bytes data + 2 CRC = 22 total
};

// ============================================================================
// PARAM System (Version 2) - Dynamic Parameter Management
// ============================================================================

// PARAM command types
enum ParamCommand : uint8_t {
    PARAM_CMD_LIST = 0x01,          // List parameters
    PARAM_CMD_GET = 0x02,           // Get parameter value
    PARAM_CMD_SET = 0x03,           // Set parameter value
    PARAM_CMD_LIST_RESP = 0x81,     // List response
    PARAM_CMD_GET_RESP = 0x82,      // Get response
    PARAM_CMD_SET_RESP = 0x83,      // Set response
    PARAM_CMD_ERROR = 0xFF          // Error response
};

// PARAM error codes
enum ParamErrorCode : uint8_t {
    PARAM_ERROR_NONE = 0,
    PARAM_ERROR_INDEX_OUT_OF_RANGE = 1,
    PARAM_ERROR_NOT_FOUND = 2,
    PARAM_ERROR_READ_FAILED = 3,
    PARAM_ERROR_WRITE_FAILED = 4,
    PARAM_ERROR_UNKNOWN_COMMAND = 5
};

// PARAM type codes
enum ParamType : uint8_t {
    PARAM_TYPE_FLOAT = 0x06
};

// PARAM access modes
enum ParamAccess : uint8_t {
    PARAM_ACCESS_READONLY = 0x00,
    PARAM_ACCESS_READWRITE = 0x01
};

// 8. PARAM_REQUEST (0x10) - Parameter Request Packet (20 bytes total)
struct TelemetryParamRequest {
    // Header (12 bytes with padding)
    uint8_t magic;           // 0x5B (enhanced telemetry identifier)
    uint8_t version;         // 2 (enhanced version)
    uint8_t type;            // 0x10 (TELEM_TYPE_PARAM_REQUEST)
    uint8_t flags;           // Packet flags (0 for PARAM)
    uint16_t seq;            // Sequence number
    uint8_t _padding[2];     // 2-byte padding for alignment
    uint32_t timestamp_us;   // Microsecond timestamp

    // Payload (6 bytes)
    uint8_t command;         // ParamCommand (LIST/GET/SET)
    uint8_t param_index;     // Parameter index (0-255)
    float value;             // New value (for SET command only)

    // Footer (2 bytes)
    uint16_t crc;            // CRC-16/X.25 (all bytes except CRC)
};
// Total: 20 bytes

// 9. PARAM_RESPONSE (0x11) - Parameter Response Packet (57 bytes total)
struct TelemetryParamResponse {
    // Header (12 bytes with padding)
    uint8_t magic;           // 0x5B
    uint8_t version;         // 2
    uint8_t type;            // 0x11 (TELEM_TYPE_PARAM_RESPONSE)
    uint8_t flags;           // Packet flags (0 for PARAM)
    uint16_t seq;            // Sequence number (matches request)
    uint8_t _padding[2];     // 2-byte padding
    uint32_t timestamp_us;   // Timestamp

    // Payload (43 bytes with padding)
    uint8_t command;         // ParamCommand (LIST_RESP/GET_RESP/SET_RESP/ERROR)
    uint8_t param_index;     // Parameter index
    uint8_t param_type;      // ParamType (0x06 = float)
    uint8_t param_access;    // ParamAccess (0x00 = readonly, 0x01 = readwrite)
    float value;             // Current parameter value
    uint8_t _padding2;       // 1-byte padding after float
    char group[16];          // Parameter group name (null-terminated)
    char name[16];           // Parameter name (null-terminated)
    uint8_t total_params;    // Total number of parameters (for LIST)
    uint8_t error_code;      // ParamErrorCode (0 = success, >0 = error)

    // Footer (2 bytes)
    uint16_t crc;            // CRC-16/X.25
};
// Total: 57 bytes

#pragma pack(pop)

// Enhanced telemetry validation helper
inline bool isEnhancedTelemetry(const uint8_t* data, size_t len) {
    if (len < sizeof(TelemetryHeader)) return false;
    return data[0] == TELEM_ENHANCED_MAGIC && data[1] == TELEM_ENHANCED_VERSION;
}