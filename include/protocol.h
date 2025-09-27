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
    uint8_t  magic;     // 0xB5
    uint8_t  version;   // 1
    uint16_t seq;       // sequence counter
    uint16_t armed;     // 0 or 1
    uint16_t thr;       // 0..1000
    int16_t  setR_x10;  // setpoint roll * 10 (degrees)
    int16_t  setP_x10;  // setpoint pitch * 10 (degrees)
    int16_t  angR_x10;  // actual roll * 10 (degrees)
    int16_t  angP_x10;  // actual pitch * 10 (degrees)
    int16_t  rateR_x10; // roll rate * 10 (deg/s)
    int16_t  rateP_x10; // pitch rate * 10 (deg/s)
    int16_t  rateY_x10; // yaw rate * 10 (deg/s)
    uint16_t outR;      // roll output 0..100
    uint16_t outP;      // pitch output 0..100
    uint16_t outY;      // yaw output 0..100
    uint16_t m1;        // motor 1 output 0..100
    uint16_t m2;        // motor 2 output 0..100
    uint16_t m3;        // motor 3 output 0..100
    uint16_t m4;        // motor 4 output 0..100
    uint16_t crc;       // CRC-16/X.25
};
#pragma pack(pop)

// Packet constants
#define RC_PACKET_MAGIC   0xA5
#define RC_PACKET_VERSION 1
#define RC_FLAG_ARMED     0x01
#define RC_FLAG_DEBUG     0x02

// TELEM: Telemetry packet constants
#define TELEM_PACKET_MAGIC   0xB5
#define TELEM_PACKET_VERSION 1

// CRC-16/X.25 calculation
uint16_t crc16_x25(const uint8_t* data, size_t len);