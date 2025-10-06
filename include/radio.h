#pragma once
#include <cstdint>
#include <cstddef>
#include <esp_now.h>
#include "protocol.h"

// Enhanced telemetry statistics per packet type
struct EnhancedTelemStats {
    uint32_t packets_received;
    uint32_t packets_dropped;
    uint16_t last_seq;
    uint32_t last_timestamp_us;
    uint32_t crc_errors;
};

// Enhanced telemetry data store
struct EnhancedTelemData {
    TelemetryAttitude attitude;
    TelemetryControl control;
    TelemetryMotors motors;
    TelemetryStatus status;
    TelemetrySensors sensors;
    TelemetrySafety safety;
    TelemetryPerformance performance;

    // Reception timestamps (millis)
    uint32_t attitude_rx_ms;
    uint32_t control_rx_ms;
    uint32_t motors_rx_ms;
    uint32_t status_rx_ms;
    uint32_t sensors_rx_ms;
    uint32_t safety_rx_ms;
    uint32_t performance_rx_ms;

    // Statistics per packet type
    EnhancedTelemStats stats[7]; // Index = (type - 1)
};

// Telemetry receiver configuration
struct TelemReceiverConfig {
    bool enable_enhanced;        // Enable enhanced telemetry reception
    uint8_t packet_type_mask;    // Bitmask of enabled packet types (bit 0 = ATTITUDE, etc.)
    uint16_t packet_timeout_ms;  // Packet timeout in ms
};

class RadioManager {
public:
    bool init(uint8_t channel = 1);
    bool setPeerMac(const uint8_t* mac);
    bool sendPacket(const void* data, size_t len);
    void setChannel(uint8_t channel);

    // Enhanced telemetry reception
    bool hasNewEnhancedTelemetry() const;
    const EnhancedTelemData& getEnhancedTelemetry() const;
    void clearNewEnhancedFlag();

    // Enhanced telemetry data accessors
    bool hasAttitude() const;
    bool hasControl() const;
    bool hasMotors() const;
    bool hasStatus() const;
    bool hasSensors() const;
    bool hasSafety() const;
    bool hasPerformance() const;

    // Statistics
    const EnhancedTelemStats& getEnhancedStats(TelemetryPacketType type) const;
    uint32_t getTotalEnhancedPackets() const;
    uint32_t getTotalEnhancedDrops() const;

    // Configuration
    void setReceiverConfig(const TelemReceiverConfig& config);
    const TelemReceiverConfig& getReceiverConfig() const;

    // Send status tracking
    uint32_t getSendSuccessCount() const;
    uint32_t getSendFailCount() const;

private:
    uint8_t m_peerMac[6] = {0};
    uint8_t m_channel = 1;
    bool m_initialized = false;

    // Enhanced telemetry state
    static EnhancedTelemData s_enhancedTelem;
    static volatile bool s_newEnhancedAvailable;
    static volatile uint8_t s_newPacketTypeFlags; // Bitmask of received packet types

    // Configuration
    static TelemReceiverConfig s_config;

    // Send status tracking
    static volatile uint32_t s_sendSuccessCount;
    static volatile uint32_t s_sendFailCount;

    // Packet handlers
    static void handleEnhancedAttitude(const uint8_t* data, int len);
    static void handleEnhancedControl(const uint8_t* data, int len);
    static void handleEnhancedMotors(const uint8_t* data, int len);
    static void handleEnhancedStatus(const uint8_t* data, int len);
    static void handleEnhancedSensors(const uint8_t* data, int len);
    static void handleEnhancedSafety(const uint8_t* data, int len);
    static void handleEnhancedPerformance(const uint8_t* data, int len);

    // Helper to update stats
    static void updatePacketStats(TelemetryPacketType type, uint16_t seq, bool crcValid);

    static void onSendCallback(const uint8_t *mac_addr, esp_now_send_status_t status);
    static void onReceiveCallback(const uint8_t *mac_addr, const uint8_t *data, int len);
};