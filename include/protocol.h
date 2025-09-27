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
    uint8_t  flags;     // bit0 = ARM state, bit1 = debugView
    uint8_t  rssi_hint; // optional RSSI info
    uint16_t crc;       // CRC-16/X.25 of all fields except crc
};

// TELEM: Telemetry packet structure (must match drone exactly)
struct TelemetryPacket {
    uint8_t  magic;             // 0x5A - 1 bajt
    uint8_t  version;           // 1 - 1 bajt
    uint16_t seq;               // sequence counter - 2 bajty
    uint32_t ms;                // timestamp - 4 bajty
    
    // Setpoints (scaled for precision)
    int16_t  setAngleRoll_x10;  // setpoint roll * 10 - 2 bajty
    int16_t  setAnglePitch_x10; // setpoint pitch * 10 - 2 bajty
    int16_t  setYawRate_dps;    // setpoint yaw rate deg/s - 2 bajty
    
    // Estimated angles (scaled for precision)
    int16_t  roll_deg_x10;      // actual roll * 10 - 2 bajty
    int16_t  pitch_deg_x10;     // actual pitch * 10 - 2 bajty
    
    // Rates
    int16_t  rollRate_dps;      // roll rate deg/s - 2 bajty
    int16_t  pitchRate_dps;     // pitch rate deg/s - 2 bajty
    int16_t  yawRate_dps;       // yaw rate deg/s - 2 bajty
    
    // RATE PID outputs
    int16_t  outRoll;           // roll PID output - 2 bajty
    int16_t  outPitch;          // pitch PID output - 2 bajty
    int16_t  outYaw;            // yaw PID output - 2 bajty
    
    // Mixer values
    uint16_t m1, m2, m3, m4;    // motor outputs - 4 × 2 = 8 bajtów
    
    // Status
    uint16_t thr;               // throttle 0..1000 - 2 bajty
    uint8_t  armed;             // armed state - 1 bajt
    uint8_t  linkAlive;         // link status - 1 bajt
    
    uint16_t crc;               // CRC-16/X.25 - 2 bajty
};
#pragma pack(pop)

// Packet constants
#define RC_PACKET_MAGIC   0xA5
#define RC_PACKET_VERSION 1
#define RC_FLAG_ARMED     0x01
#define RC_FLAG_DEBUG     0x02

// TELEM: Telemetry packet constants
#define TELEM_PACKET_MAGIC   0x5A
#define TELEM_PACKET_VERSION 1

// CRC-16/X.25 calculation
uint16_t crc16_x25(const uint8_t* data, size_t len);