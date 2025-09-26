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
    uint8_t  flags;     // bit0 = ARM state
    uint8_t  rssi_hint; // optional RSSI info
    uint16_t crc;       // CRC-16/X.25 of all fields except crc
};
#pragma pack(pop)

// Packet constants
#define RC_PACKET_MAGIC   0xA5
#define RC_PACKET_VERSION 1
#define RC_FLAG_ARMED     0x01

// CRC-16/X.25 calculation
uint16_t crc16_x25(const uint8_t* data, size_t len);