/**
 * @file TelemetryForwarder.h
 * @brief Forward Enhanced Telemetry packets from ESP-NOW to UART
 *
 * This module handles forwarding of received telemetry packets to UART
 * in TELEMETRY_BINARY mode. In DEBUG_TEXT mode, forwarding is disabled.
 */

#pragma once
#include <cstdint>
#include "radio.h"

/**
 * @brief UART operation modes
 */
enum class UartMode : uint8_t {
    DEBUG_TEXT,         ///< Text-based debug logs (default)
    TELEMETRY_BINARY    ///< Binary telemetry packets (for UI)
};

/**
 * @brief Telemetry forwarder configuration
 */
struct ForwarderConfig {
    bool forward_attitude = true;       ///< Forward ATTITUDE packets (20 Hz)
    bool forward_motors = true;         ///< Forward MOTORS packets (5 Hz)
    bool forward_status = true;         ///< Forward STATUS packets (2.5 Hz)
    bool forward_control = false;       ///< Forward CONTROL packets (10 Hz, optional)
    bool forward_sensors = false;       ///< Forward SENSORS packets (1.25 Hz, optional)
    bool forward_safety = false;        ///< Forward SAFETY packets (1.25 Hz, optional)
    bool forward_performance = false;   ///< Forward PERFORMANCE packets (0.625 Hz, optional)
};

/**
 * @brief TelemetryForwarder class
 *
 * Handles forwarding of telemetry packets from RadioManager to UART.
 * Only forwards packets when in TELEMETRY_BINARY mode.
 */
class TelemetryForwarder {
public:
    /**
     * @brief Initialize the forwarder
     * @param radio Pointer to RadioManager instance
     */
    void init(RadioManager* radio);

    /**
     * @brief Set UART operating mode
     * @param mode UartMode (DEBUG_TEXT or TELEMETRY_BINARY)
     */
    void setUartMode(UartMode mode);

    /**
     * @brief Get current UART mode
     * @return Current UartMode
     */
    UartMode getUartMode() const;

    /**
     * @brief Set forwarder configuration
     * @param config ForwarderConfig with enabled packet types
     */
    void setConfig(const ForwarderConfig& config);

    /**
     * @brief Get current configuration
     * @return Current ForwarderConfig
     */
    const ForwarderConfig& getConfig() const;

    /**
     * @brief Update forwarder (call from main loop)
     *
     * Checks for new telemetry packets and forwards them to UART
     * if in TELEMETRY_BINARY mode.
     */
    void update();

    /**
     * @brief Get total number of forwarded packets
     * @return Count of successfully forwarded packets
     */
    uint32_t getForwardedCount() const;

    /**
     * @brief Get total number of dropped packets
     * @return Count of packets that failed to forward
     */
    uint32_t getDroppedCount() const;

    /**
     * @brief Get forwarded count per packet type
     * @param type TelemetryPacketType enum
     * @return Count of forwarded packets of this type
     */
    uint32_t getForwardedCount(TelemetryPacketType type) const;

private:
    RadioManager* m_radio = nullptr;
    UartMode m_uartMode = UartMode::DEBUG_TEXT;
    ForwarderConfig m_config;

    // Statistics
    uint32_t m_forwardedCount = 0;
    uint32_t m_droppedCount = 0;
    uint32_t m_forwardedByType[7] = {0}; // Index = (type - 1)

    /**
     * @brief Forward single packet to UART
     * @param data Pointer to packet data
     * @param len Length of packet in bytes
     * @param type Packet type (for statistics)
     * @return true if forwarded successfully
     */
    bool forwardPacket(const uint8_t* data, size_t len, TelemetryPacketType type);

    /**
     * @brief Check and forward ATTITUDE packet
     */
    void checkAndForwardAttitude();

    /**
     * @brief Check and forward MOTORS packet
     */
    void checkAndForwardMotors();

    /**
     * @brief Check and forward STATUS packet
     */
    void checkAndForwardStatus();

    /**
     * @brief Check and forward CONTROL packet
     */
    void checkAndForwardControl();

    /**
     * @brief Check and forward SENSORS packet
     */
    void checkAndForwardSensors();

    /**
     * @brief Check and forward SAFETY packet
     */
    void checkAndForwardSafety();

    /**
     * @brief Check and forward PERFORMANCE packet
     */
    void checkAndForwardPerformance();
};
