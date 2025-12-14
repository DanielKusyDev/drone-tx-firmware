/**
 * @file TelemetryForwarder.cpp
 * @brief Implementation of TelemetryForwarder
 */

#include "TelemetryForwarder.h"
#include <Arduino.h>

void TelemetryForwarder::init(RadioManager* radio) {
    m_radio = radio;
}

void TelemetryForwarder::setUartMode(UartMode mode) {
    m_uartMode = mode;
}

UartMode TelemetryForwarder::getUartMode() const {
    return m_uartMode;
}

void TelemetryForwarder::setConfig(const ForwarderConfig& config) {
    m_config = config;
}

const ForwarderConfig& TelemetryForwarder::getConfig() const {
    return m_config;
}

void TelemetryForwarder::update() {
    // Only forward in TELEMETRY_BINARY mode
    if (m_uartMode != UartMode::TELEMETRY_BINARY) {
        return;
    }

    // Check if radio is initialized
    if (!m_radio) {
        return;
    }

    // Check if there's new telemetry available
    if (!m_radio->hasNewEnhancedTelemetry()) {
        return;
    }

    // Forward enabled packet types
    if (m_config.forward_attitude) {
        checkAndForwardAttitude();
    }

    if (m_config.forward_motors) {
        checkAndForwardMotors();
    }

    if (m_config.forward_status) {
        checkAndForwardStatus();
    }

    if (m_config.forward_control) {
        checkAndForwardControl();
    }

    if (m_config.forward_sensors) {
        checkAndForwardSensors();
    }

    if (m_config.forward_safety) {
        checkAndForwardSafety();
    }

    if (m_config.forward_performance) {
        checkAndForwardPerformance();
    }

    // Clear the "new telemetry" flag
    m_radio->clearNewEnhancedFlag();
}

bool TelemetryForwarder::forwardPacket(const uint8_t* data, size_t len, TelemetryPacketType type) {
    // Write packet to UART
    size_t written = Serial.write(data, len);

    // Update statistics
    if (written == len) {
        m_forwardedCount++;
        uint8_t idx = type - 1;
        if (idx < 7) {
            m_forwardedByType[idx]++;
        }
        return true;
    } else {
        m_droppedCount++;
        return false;
    }
}

void TelemetryForwarder::checkAndForwardAttitude() {
    if (m_radio->hasAttitude()) {
        const auto& telem = m_radio->getEnhancedTelemetry();
        forwardPacket(
            reinterpret_cast<const uint8_t*>(&telem.attitude),
            sizeof(TelemetryAttitude),
            TELEM_TYPE_ATTITUDE
        );
    }
}

void TelemetryForwarder::checkAndForwardMotors() {
    if (m_radio->hasMotors()) {
        const auto& telem = m_radio->getEnhancedTelemetry();
        forwardPacket(
            reinterpret_cast<const uint8_t*>(&telem.motors),
            sizeof(TelemetryMotors),
            TELEM_TYPE_MOTORS
        );
    }
}

void TelemetryForwarder::checkAndForwardStatus() {
    if (m_radio->hasStatus()) {
        const auto& telem = m_radio->getEnhancedTelemetry();
        forwardPacket(
            reinterpret_cast<const uint8_t*>(&telem.status),
            sizeof(TelemetryStatus),
            TELEM_TYPE_STATUS
        );
    }
}

void TelemetryForwarder::checkAndForwardControl() {
    if (m_radio->hasControl()) {
        const auto& telem = m_radio->getEnhancedTelemetry();
        forwardPacket(
            reinterpret_cast<const uint8_t*>(&telem.control),
            sizeof(TelemetryControl),
            TELEM_TYPE_CONTROL
        );
    }
}

void TelemetryForwarder::checkAndForwardSensors() {
    if (m_radio->hasSensors()) {
        const auto& telem = m_radio->getEnhancedTelemetry();
        forwardPacket(
            reinterpret_cast<const uint8_t*>(&telem.sensors),
            sizeof(TelemetrySensors),
            TELEM_TYPE_SENSORS
        );
    }
}

void TelemetryForwarder::checkAndForwardSafety() {
    if (m_radio->hasSafety()) {
        const auto& telem = m_radio->getEnhancedTelemetry();
        forwardPacket(
            reinterpret_cast<const uint8_t*>(&telem.safety),
            sizeof(TelemetrySafety),
            TELEM_TYPE_SAFETY
        );
    }
}

void TelemetryForwarder::checkAndForwardPerformance() {
    if (m_radio->hasPerformance()) {
        const auto& telem = m_radio->getEnhancedTelemetry();
        forwardPacket(
            reinterpret_cast<const uint8_t*>(&telem.performance),
            sizeof(TelemetryPerformance),
            TELEM_TYPE_PERFORMANCE
        );
    }
}

uint32_t TelemetryForwarder::getForwardedCount() const {
    return m_forwardedCount;
}

uint32_t TelemetryForwarder::getDroppedCount() const {
    return m_droppedCount;
}

uint32_t TelemetryForwarder::getForwardedCount(TelemetryPacketType type) const {
    uint8_t idx = type - 1;
    if (idx >= 7) return 0;
    return m_forwardedByType[idx];
}
