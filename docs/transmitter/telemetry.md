# Enhanced Telemetry System Documentation

## Overview

The Enhanced Telemetry System is a professional, configurable telemetry implementation designed for drone flight control systems. It provides efficient, bandwidth-optimized communication between the flight controller and ground station using ESP-NOW protocol.

## System Architecture

### Key Features
- **Multi-packet Architecture**: Different packet types for different data categories
- **Configurable Rates**: Each packet type can have independent transmission rates
- **Bandwidth Efficiency**: Only transmits relevant data when needed
- **Scalable Design**: Easy to add new packet types without breaking compatibility
- **Real-time Performance**: Critical data (attitude) sent at higher frequencies
- **Professional Structure**: Industry-standard telemetry practices

### Packet Types

The system defines 7 distinct telemetry packet types:

| Type | ID | Description | Default Rate | Size |
|------|----|-----------|----|------|
| **ATTITUDE** | 0x01 | Roll/pitch/yaw angles and rates | 20Hz (÷1) | ~22 bytes |
| **CONTROL** | 0x02 | PID setpoints and outputs | 10Hz (÷2) | ~21 bytes |
| **MOTORS** | 0x03 | Motor commands and mixer outputs | 5Hz (÷4) | ~26 bytes |
| **STATUS** | 0x04 | System status and diagnostics | 2.5Hz (÷8) | ~21 bytes |
| **SENSORS** | 0x05 | Raw IMU sensor data | 1.25Hz (÷16) | ~24 bytes |
| **SAFETY** | 0x06 | Safety systems and ground detection | 1.25Hz (÷16) | ~18 bytes |
| **PERFORMANCE** | 0x07 | Timing and performance metrics | 0.625Hz (÷32) | ~20 bytes |

## Configuration System

### TelemetryConfig Structure
```cpp
struct TelemetryConfig {
    bool enabled;                    // Global telemetry enable/disable
    uint8_t packet_types;            // Bitmask of enabled packet types (0x3F default)
    uint16_t base_rate_hz;           // Base telemetry rate (20Hz default)
    uint8_t rate_divisors[8];        // Rate divisors per packet type
    bool adaptive_rate;              // Adaptive rate based on link quality (future)
    bool compression;                // Data compression enable (future)
    uint8_t max_retries;             // Maximum retry attempts (3 default)
    uint32_t timeout_ms;             // Packet timeout (100ms default)
};
```

### Default Configuration
- **Base Rate**: 20Hz
- **Enabled Packets**: ATTITUDE, CONTROL, MOTORS, STATUS, SENSORS, SAFETY (0x3F bitmask)
- **Rate Divisors**: [1, 2, 4, 8, 16, 16, 32, 32]
- **Adaptive Rate**: Disabled
- **Compression**: Disabled
- **Max Retries**: 3
- **Timeout**: 100ms

### Runtime Configuration
```cpp
// Enable/disable specific packet types
void telemetry_set_packet_enable(TelemetryPacketType type, bool enabled);

// Adjust transmission rate for specific packet types
void telemetry_set_packet_rate(TelemetryPacketType type, uint8_t divisor);

// Full configuration update
void telemetry_enhanced_configure(const TelemetryConfig& config);
```

## Packet Structures

### Common Header
All enhanced telemetry packets share a common header:
```cpp
struct TelemetryHeader {
    uint8_t magic;                   // 0x5B (enhanced telemetry identifier)
    uint8_t version;                 // 2 (enhanced version)
    uint8_t type;                    // TelemetryPacketType
    uint8_t flags;                   // Packet flags (compression, ack_req, etc.)
    uint16_t seq;                    // Sequence number (per packet type)
    uint32_t timestamp_us;           // Microsecond timestamp
};
```

### Packet Definitions

#### 1. ATTITUDE (0x01) - Flight Attitude Data
```cpp
struct TelemetryAttitude {
    TelemetryHeader header;
    int16_t roll_deg_x100;           // Roll angle in 0.01° units
    int16_t pitch_deg_x100;          // Pitch angle in 0.01° units  
    int16_t yaw_deg_x100;            // Yaw angle in 0.01° units
    int16_t roll_rate_dps_x10;       // Roll rate in 0.1°/s units
    int16_t pitch_rate_dps_x10;      // Pitch rate in 0.1°/s units
    int16_t yaw_rate_dps_x10;        // Yaw rate in 0.1°/s units
    uint16_t crc;
};
```

#### 2. CONTROL (0x02) - PID Control Data
```cpp
struct TelemetryControl {
    TelemetryHeader header;
    int16_t set_roll_deg_x100;       // Roll setpoint in 0.01° units
    int16_t set_pitch_deg_x100;      // Pitch setpoint in 0.01° units
    int16_t set_yaw_rate_dps_x10;    // Yaw rate setpoint in 0.1°/s units
    int16_t out_roll_x10;            // Roll PID output x10
    int16_t out_pitch_x10;           // Pitch PID output x10
    int16_t out_yaw_x10;             // Yaw PID output x10
    uint8_t pid_gains_scale_x100;    // PID gains scaling factor x100
    uint16_t crc;
};
```

#### 3. MOTORS (0x03) - Motor and Mixer Data
```cpp
struct TelemetryMotors {
    TelemetryHeader header;
    uint16_t motor_cmd[4];           // Motor commands 0-1000
    uint16_t motor_actual[4];        // Actual motor outputs (if feedback available)
    uint16_t throttle;               // Base throttle
    uint8_t mixer_table_id;          // Active mixer table ID
    uint16_t crc;
};
```

#### 4. STATUS (0x04) - System Status
```cpp
struct TelemetryStatus {
    TelemetryHeader header;
    uint8_t armed;                   // Arming state
    uint8_t flight_mode;             // Flight mode
    uint8_t safety_flags;            // Safety system flags
    uint8_t ground_state;            // Ground detection state
    uint8_t link_quality;            // RC link quality 0-100
    uint8_t battery_pct;             // Battery percentage (future use)
    uint16_t uptime_s;               // System uptime in seconds
    uint32_t loop_rate_hz_x10;       // Main loop rate x10
    uint16_t crc;
};
```

#### 5. SENSORS (0x05) - Raw Sensor Data
```cpp
struct TelemetrySensors {
    TelemetryHeader header;
    int16_t accel_mg[3];             // Accelerometer in millig
    int16_t gyro_mdps[3];            // Gyroscope in milli-dps
    int16_t mag_mgauss[3];           // Magnetometer in milligauss (future)
    int16_t temperature_c_x10;       // Temperature in 0.1°C
    uint16_t crc;
};
```

#### 6. SAFETY (0x06) - Safety and Diagnostics
```cpp
struct TelemetrySafety {
    TelemetryHeader header;
    uint8_t ground_confidence_x100;  // Ground detection confidence x100
    uint8_t safety_gates;            // Active safety gates bitmask
    uint16_t error_flags;            // System error flags
    uint32_t total_flight_time_s;    // Total flight time
    uint16_t crash_count;            // Crash detection counter
    uint16_t crc;
};
```

#### 7. PERFORMANCE (0x07) - Performance Metrics
```cpp
struct TelemetryPerformance {
    TelemetryHeader header;
    uint16_t loop_time_us;           // Main loop execution time
    uint16_t imu_time_us;            // IMU read time
    uint16_t control_time_us;        // Control computation time
    uint8_t cpu_usage_pct;           // CPU usage percentage
    uint16_t free_heap_kb;           // Free heap in KB
    uint8_t stack_usage_pct;         // Stack usage percentage
    uint16_t crc;
};
```

## Statistics and Monitoring

### TelemetryStats Structure
```cpp
struct TelemetryStats {
    uint32_t packets_sent;           // Total packets sent
    uint32_t packets_acked;          // Packets acknowledged
    uint32_t packets_lost;           // Packets lost/timeout
    uint32_t bytes_sent;             // Total bytes transmitted
    float packet_loss_rate;          // Current packet loss percentage
    uint32_t avg_latency_us;         // Average round-trip time
    uint32_t link_quality;           // Link quality score 0-100
};
```

### Diagnostic Functions
```cpp
const TelemetryStats& telemetry_get_stats();     // Get current statistics
void telemetry_reset_stats();                    // Reset statistics counters
void telemetry_log_diagnostics();                // Log detailed diagnostics
```

## API Reference

### Initialization
```cpp
void telemetry_enhanced_init();                  // Initialize enhanced telemetry
void telemetry_enhanced_configure(const TelemetryConfig& config);
const TelemetryConfig& telemetry_enhanced_get_config();
```

### Packet Transmission
```cpp
void telemetry_send_attitude(float roll, float pitch, float yaw,
                           float roll_rate, float pitch_rate, float yaw_rate);

void telemetry_send_control(float set_roll, float set_pitch, float set_yaw_rate,
                          float out_roll, float out_pitch, float out_yaw, float gain_scale);

void telemetry_send_motors(const float motors[4], uint16_t throttle, uint8_t mixer_id);

void telemetry_send_status(bool armed, uint8_t flight_mode, uint8_t safety_flags, 
                         uint8_t ground_state, uint8_t link_quality);

void telemetry_send_sensors(const float accel[3], const float gyro[3], 
                          const float mag[3], float temperature);

void telemetry_send_safety(float ground_confidence, uint8_t safety_gates, 
                         uint16_t error_flags, uint32_t flight_time);

void telemetry_send_performance(uint16_t loop_time, uint16_t imu_time, 
                              uint16_t control_time, uint8_t cpu_usage);
```

### Runtime Management
```cpp
void telemetry_enhanced_update();               // Called each main loop cycle
void telemetry_set_packet_enable(TelemetryPacketType type, bool enabled);
void telemetry_set_packet_rate(TelemetryPacketType type, uint8_t divisor);
```

## Protocol Details

### Magic Bytes
- **Enhanced Telemetry**: 0x5B (version 2)
- **Legacy Telemetry**: 0x5A (version 1)

### CRC Protection
All packets use CRC-16/X.25 for error detection:
- Polynomial: 0x8408 (reflected)
- Initial value: 0xFFFF
- Final XOR: 0xFFFF

### Transmission Protocol
- **Transport**: ESP-NOW (WiFi 802.11)
- **Addressing**: MAC-based peer-to-peer
- **Reliability**: Best-effort with statistics tracking
- **Flow Control**: Rate-based transmission scheduling

## Integration Notes

### Feature Flag Control
Enhanced telemetry is controlled by the `CFG_ENHANCED_TELEMETRY` flag in `config_flags.h`:
```cpp
#define CFG_ENHANCED_TELEMETRY 1     // Enable enhanced telemetry
```

### Backward Compatibility
When enabled, the system provides a compatibility wrapper that maintains the legacy 44-byte packet interface while using the enhanced multi-packet system internally.

### Performance Impact
- **CPU Usage**: < 2% additional overhead
- **Memory Usage**: ~2KB additional RAM
- **Bandwidth**: More efficient than legacy (adaptive packet sizes)
- **Latency**: Improved for critical data (attitude packets)

## Receiver Implementation Guide

Ground station receivers should:

1. **Detect packet type** using the magic byte (0x5B) and type field
2. **Parse header** to extract sequence number and timestamp
3. **Switch on packet type** to handle different structures
4. **Verify CRC** before processing packet data
5. **Track statistics** for link quality monitoring
6. **Handle missing packets** gracefully (not all types sent every cycle)

Example detection code:
```cpp
if (data[0] == 0x5B && data[1] == 2) {  // Enhanced telemetry
    TelemetryPacketType type = (TelemetryPacketType)data[2];
    switch (type) {
        case TELEM_TYPE_ATTITUDE:
            handle_attitude_packet((TelemetryAttitude*)data);
            break;
        case TELEM_TYPE_CONTROL:
            handle_control_packet((TelemetryControl*)data);
            break;
        // ... handle other types
    }
}
```