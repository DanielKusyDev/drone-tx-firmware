#include "radio.h"
#include "config.h"
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <cstring>

// Forward declarations for compatibility logging functions (defined in main.cpp)
void radioWrongPacketSize(int actualLen, int expectedLen);
void radioWrongMagicVersion(uint8_t magic, uint8_t version);
void radioCrcError(uint16_t calculated, uint16_t received);


// TELEM: Static telemetry variables (legacy)
TelemetryPacket RadioManager::s_lastTelemetry = {};
volatile bool RadioManager::s_newTelemetryAvailable = false;
volatile uint32_t RadioManager::s_lastTelemSeq = 0;
volatile uint32_t RadioManager::s_dropCount = 0;

// Enhanced telemetry state
EnhancedTelemData RadioManager::s_enhancedTelem = {};
volatile bool RadioManager::s_newEnhancedAvailable = false;
volatile uint8_t RadioManager::s_newPacketTypeFlags = 0;

// Telemetry receiver configuration
// Enhanced telemetry only - legacy (0x5A) packets are ignored
TelemReceiverConfig RadioManager::s_config = {
    .enable_enhanced = true,     // Enhanced telemetry (magic 0x5B, version 2)
    .enable_legacy = false,      // Legacy telemetry disabled (magic 0x5A, version 1)
    .packet_type_mask = 0x7F,    // All 7 packet types enabled (ATTITUDE..PERFORMANCE)
    .packet_timeout_ms = 300     // Packet freshness timeout
};

// Send status tracking
volatile uint32_t RadioManager::s_sendSuccessCount = 0;
volatile uint32_t RadioManager::s_sendFailCount = 0;

// Static callback function
void RadioManager::onSendCallback(const uint8_t *mac_addr, esp_now_send_status_t status) {
    (void)mac_addr; // Unused
    
    if (status == ESP_NOW_SEND_SUCCESS) {
        s_sendSuccessCount++;
    } else {
        s_sendFailCount++;
    }
}

// TELEM: Receive callback for telemetry
void RadioManager::onReceiveCallback(const uint8_t *mac_addr, const uint8_t *data, int len) {
    (void)mac_addr; // Unused

    // Check for minimal header size
    if (len < 2) return;

    uint8_t magic = data[0];
    uint8_t version = data[1];

    // Route to enhanced or legacy handler
    if (magic == TELEM_ENHANCED_MAGIC && version == TELEM_ENHANCED_VERSION) {
        // Enhanced telemetry (v2)
        if (!s_config.enable_enhanced) return;

        if (len < sizeof(TelemetryHeader)) {
            radioWrongPacketSize(len, sizeof(TelemetryHeader));
            return;
        }

        const TelemetryHeader* header = reinterpret_cast<const TelemetryHeader*>(data);
        TelemetryPacketType type = static_cast<TelemetryPacketType>(header->type);

        // Check if this packet type is enabled
        uint8_t typeBit = 1 << (type - 1);
        if (!(s_config.packet_type_mask & typeBit)) {
            return; // Packet type filtered out
        }

        // Route to appropriate handler
        switch (type) {
            case TELEM_TYPE_ATTITUDE:
                handleEnhancedAttitude(data, len);
                break;
            case TELEM_TYPE_CONTROL:
                handleEnhancedControl(data, len);
                break;
            case TELEM_TYPE_MOTORS:
                handleEnhancedMotors(data, len);
                break;
            case TELEM_TYPE_STATUS:
                handleEnhancedStatus(data, len);
                break;
            case TELEM_TYPE_SENSORS:
                handleEnhancedSensors(data, len);
                break;
            case TELEM_TYPE_SAFETY:
                handleEnhancedSafety(data, len);
                break;
            case TELEM_TYPE_PERFORMANCE:
                handleEnhancedPerformance(data, len);
                break;
            default:
                // Unknown packet type
                return;
        }

    } else if (magic == TELEM_PACKET_MAGIC && version == TELEM_PACKET_VERSION) {
        // Legacy telemetry (v1)
        if (!s_config.enable_legacy) return;

        if (len != sizeof(TelemetryPacket)) {
            radioWrongPacketSize(len, sizeof(TelemetryPacket));
            return;
        }

        const TelemetryPacket* packet = reinterpret_cast<const TelemetryPacket*>(data);

        // Verify CRC (both sides use same CRC calc, no swap needed)
        uint16_t calculatedCrc = crc16_x25(data, len - sizeof(packet->crc));
        if (calculatedCrc != packet->crc) {
            radioCrcError(calculatedCrc, packet->crc);
            return;
        }

        // Check for dropped packets
        uint32_t currentSeq = packet->seq;
        if (s_lastTelemSeq != 0 && currentSeq != (s_lastTelemSeq + 1) % 65536) {
            // Packets were dropped
            uint32_t expectedSeq = (s_lastTelemSeq + 1) % 65536;
            uint32_t droppedCount;
            if (currentSeq > expectedSeq) {
                droppedCount = currentSeq - expectedSeq;
            } else {
                droppedCount = (65536 - expectedSeq) + currentSeq;
            }
            s_dropCount += droppedCount;
        }
        s_lastTelemSeq = currentSeq;

        // Copy packet and set flag
        memcpy((void*)&s_lastTelemetry, packet, sizeof(TelemetryPacket));
        s_newTelemetryAvailable = true;

    } else {
        // Unknown packet format
        radioWrongMagicVersion(magic, version);
    }
}

bool RadioManager::init(uint8_t channel) {
    m_channel = channel;
    
    // Initialize WiFi in station mode
    WiFi.mode(WIFI_STA);
    
    // Set the channel
    esp_wifi_set_promiscuous(true);
    esp_wifi_set_channel(m_channel, WIFI_SECOND_CHAN_NONE);
    esp_wifi_set_promiscuous(false);
    
    // Initialize ESP-NOW
    if (esp_now_init() != ESP_OK) {
        return false;
    }
    
    // Register send callback
    esp_now_register_send_cb(onSendCallback);
    
    // TELEM: Register receive callback
    esp_now_register_recv_cb(onReceiveCallback);
    
    m_initialized = true;
    return true;
}

bool RadioManager::setPeerMac(const uint8_t* mac) {
    if (!m_initialized || !mac) {
        return false;
    }
    
    // Remove existing peer if any
    esp_now_del_peer(m_peerMac);
    
    // Copy new MAC address
    memcpy(m_peerMac, mac, 6);
    
    // Add new peer
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, m_peerMac, 6);
    peerInfo.channel = m_channel;
    peerInfo.encrypt = false;
    
    return esp_now_add_peer(&peerInfo) == ESP_OK;
}

bool RadioManager::sendPacket(const void* data, size_t len) {
    if (!m_initialized) {
        return false;
    }
    
    return esp_now_send(m_peerMac, (const uint8_t*)data, len) == ESP_OK;
}

void RadioManager::setChannel(uint8_t channel) {
    if (m_channel != channel) {
        m_channel = channel;
        esp_wifi_set_promiscuous(true);
        esp_wifi_set_channel(m_channel, WIFI_SECOND_CHAN_NONE);
        esp_wifi_set_promiscuous(false);
    }
}

// TELEM: Telemetry accessor methods
bool RadioManager::hasNewTelemetry() const {
    return s_newTelemetryAvailable;
}

TelemetryPacket RadioManager::getLastTelemetry() {
    return s_lastTelemetry;
}

void RadioManager::clearNewTelemetryFlag() {
    s_newTelemetryAvailable = false;
}

uint32_t RadioManager::getDropCount() const {
    return s_dropCount;
}

uint32_t RadioManager::getSendSuccessCount() const {
    return s_sendSuccessCount;
}

uint32_t RadioManager::getSendFailCount() const {
    return s_sendFailCount;
}

// ============================================================================
// Enhanced Telemetry Packet Handlers
// ============================================================================

void RadioManager::updatePacketStats(TelemetryPacketType type, uint16_t seq, bool crcValid) {
    uint8_t idx = type - 1;
    if (idx >= 7) return;

    EnhancedTelemStats& stats = s_enhancedTelem.stats[idx];

    if (!crcValid) {
        stats.crc_errors++;
        return;
    }

    // Check for dropped packets
    if (stats.packets_received > 0) {
        uint16_t expectedSeq = (stats.last_seq + 1) % 65536;
        if (seq != expectedSeq) {
            // Calculate dropped count
            uint32_t dropped;
            if (seq > expectedSeq) {
                dropped = seq - expectedSeq;
            } else {
                dropped = (65536 - expectedSeq) + seq;
            }
            stats.packets_dropped += dropped;
        }
    }

    stats.last_seq = seq;
    stats.packets_received++;
}

void RadioManager::handleEnhancedAttitude(const uint8_t* data, int len) {
    if (len != sizeof(TelemetryAttitude)) {
        radioWrongPacketSize(len, sizeof(TelemetryAttitude));
        return;
    }

    const TelemetryAttitude* packet = reinterpret_cast<const TelemetryAttitude*>(data);

    // Verify CRC
    uint16_t calculatedCrc = crc16_x25(data, len - sizeof(packet->crc));
    bool crcValid = (calculatedCrc == packet->crc);

    if (!crcValid) {
        radioCrcError(calculatedCrc, packet->crc);
        updatePacketStats(TELEM_TYPE_ATTITUDE, packet->header.seq, false);
        return;
    }

    // Update stats
    updatePacketStats(TELEM_TYPE_ATTITUDE, packet->header.seq, true);

    // Store packet data
    memcpy(&s_enhancedTelem.attitude, packet, sizeof(TelemetryAttitude));
    s_enhancedTelem.attitude_rx_ms = millis();
    s_enhancedTelem.stats[0].last_timestamp_us = packet->header.timestamp_us;

    // Set flags
    s_newEnhancedAvailable = true;
    s_newPacketTypeFlags |= (1 << 0);
}

void RadioManager::handleEnhancedControl(const uint8_t* data, int len) {
    if (len != sizeof(TelemetryControl)) {
        radioWrongPacketSize(len, sizeof(TelemetryControl));
        return;
    }

    const TelemetryControl* packet = reinterpret_cast<const TelemetryControl*>(data);

    // Verify CRC
    uint16_t calculatedCrc = crc16_x25(data, len - sizeof(packet->crc));
    bool crcValid = (calculatedCrc == packet->crc);

    if (!crcValid) {
        radioCrcError(calculatedCrc, packet->crc);
        updatePacketStats(TELEM_TYPE_CONTROL, packet->header.seq, false);
        return;
    }

    updatePacketStats(TELEM_TYPE_CONTROL, packet->header.seq, true);

    memcpy(&s_enhancedTelem.control, packet, sizeof(TelemetryControl));
    s_enhancedTelem.control_rx_ms = millis();
    s_enhancedTelem.stats[1].last_timestamp_us = packet->header.timestamp_us;

    s_newEnhancedAvailable = true;
    s_newPacketTypeFlags |= (1 << 1);
}

void RadioManager::handleEnhancedMotors(const uint8_t* data, int len) {
    if (len != sizeof(TelemetryMotors)) {
        radioWrongPacketSize(len, sizeof(TelemetryMotors));
        return;
    }

    const TelemetryMotors* packet = reinterpret_cast<const TelemetryMotors*>(data);

    uint16_t calculatedCrc = crc16_x25(data, len - sizeof(packet->crc));
    bool crcValid = (calculatedCrc == packet->crc);

    if (!crcValid) {
        radioCrcError(calculatedCrc, packet->crc);
        updatePacketStats(TELEM_TYPE_MOTORS, packet->header.seq, false);
        return;
    }

    updatePacketStats(TELEM_TYPE_MOTORS, packet->header.seq, true);

    memcpy(&s_enhancedTelem.motors, packet, sizeof(TelemetryMotors));
    s_enhancedTelem.motors_rx_ms = millis();
    s_enhancedTelem.stats[2].last_timestamp_us = packet->header.timestamp_us;

    s_newEnhancedAvailable = true;
    s_newPacketTypeFlags |= (1 << 2);
}

void RadioManager::handleEnhancedStatus(const uint8_t* data, int len) {
    if (len != sizeof(TelemetryStatus)) {
        radioWrongPacketSize(len, sizeof(TelemetryStatus));
        return;
    }

    const TelemetryStatus* packet = reinterpret_cast<const TelemetryStatus*>(data);

    uint16_t calculatedCrc = crc16_x25(data, len - sizeof(packet->crc));
    bool crcValid = (calculatedCrc == packet->crc);

    if (!crcValid) {
        radioCrcError(calculatedCrc, packet->crc);
        updatePacketStats(TELEM_TYPE_STATUS, packet->header.seq, false);
        return;
    }

    updatePacketStats(TELEM_TYPE_STATUS, packet->header.seq, true);

    memcpy(&s_enhancedTelem.status, packet, sizeof(TelemetryStatus));
    s_enhancedTelem.status_rx_ms = millis();
    s_enhancedTelem.stats[3].last_timestamp_us = packet->header.timestamp_us;

    s_newEnhancedAvailable = true;
    s_newPacketTypeFlags |= (1 << 3);
}

void RadioManager::handleEnhancedSensors(const uint8_t* data, int len) {
    if (len != sizeof(TelemetrySensors)) {
        radioWrongPacketSize(len, sizeof(TelemetrySensors));
        return;
    }

    const TelemetrySensors* packet = reinterpret_cast<const TelemetrySensors*>(data);

    uint16_t calculatedCrc = crc16_x25(data, len - sizeof(packet->crc));
    bool crcValid = (calculatedCrc == packet->crc);

    if (!crcValid) {
        radioCrcError(calculatedCrc, packet->crc);
        updatePacketStats(TELEM_TYPE_SENSORS, packet->header.seq, false);
        return;
    }

    updatePacketStats(TELEM_TYPE_SENSORS, packet->header.seq, true);

    memcpy(&s_enhancedTelem.sensors, packet, sizeof(TelemetrySensors));
    s_enhancedTelem.sensors_rx_ms = millis();
    s_enhancedTelem.stats[4].last_timestamp_us = packet->header.timestamp_us;

    s_newEnhancedAvailable = true;
    s_newPacketTypeFlags |= (1 << 4);
}

void RadioManager::handleEnhancedSafety(const uint8_t* data, int len) {
    if (len != sizeof(TelemetrySafety)) {
        radioWrongPacketSize(len, sizeof(TelemetrySafety));
        return;
    }

    const TelemetrySafety* packet = reinterpret_cast<const TelemetrySafety*>(data);

    uint16_t calculatedCrc = crc16_x25(data, len - sizeof(packet->crc));
    bool crcValid = (calculatedCrc == packet->crc);

    if (!crcValid) {
        radioCrcError(calculatedCrc, packet->crc);
        updatePacketStats(TELEM_TYPE_SAFETY, packet->header.seq, false);
        return;
    }

    updatePacketStats(TELEM_TYPE_SAFETY, packet->header.seq, true);

    memcpy(&s_enhancedTelem.safety, packet, sizeof(TelemetrySafety));
    s_enhancedTelem.safety_rx_ms = millis();
    s_enhancedTelem.stats[5].last_timestamp_us = packet->header.timestamp_us;

    s_newEnhancedAvailable = true;
    s_newPacketTypeFlags |= (1 << 5);
}

void RadioManager::handleEnhancedPerformance(const uint8_t* data, int len) {
    if (len != sizeof(TelemetryPerformance)) {
        radioWrongPacketSize(len, sizeof(TelemetryPerformance));
        return;
    }

    const TelemetryPerformance* packet = reinterpret_cast<const TelemetryPerformance*>(data);

    uint16_t calculatedCrc = crc16_x25(data, len - sizeof(packet->crc));
    bool crcValid = (calculatedCrc == packet->crc);

    if (!crcValid) {
        radioCrcError(calculatedCrc, packet->crc);
        updatePacketStats(TELEM_TYPE_PERFORMANCE, packet->header.seq, false);
        return;
    }

    updatePacketStats(TELEM_TYPE_PERFORMANCE, packet->header.seq, true);

    memcpy(&s_enhancedTelem.performance, packet, sizeof(TelemetryPerformance));
    s_enhancedTelem.performance_rx_ms = millis();
    s_enhancedTelem.stats[6].last_timestamp_us = packet->header.timestamp_us;

    s_newEnhancedAvailable = true;
    s_newPacketTypeFlags |= (1 << 6);
}

// ============================================================================
// Enhanced Telemetry Public API
// ============================================================================

bool RadioManager::hasNewEnhancedTelemetry() const {
    return s_newEnhancedAvailable;
}

const EnhancedTelemData& RadioManager::getEnhancedTelemetry() const {
    return s_enhancedTelem;
}

void RadioManager::clearNewEnhancedFlag() {
    s_newEnhancedAvailable = false;
    s_newPacketTypeFlags = 0;
}

bool RadioManager::hasAttitude() const {
    uint32_t age = millis() - s_enhancedTelem.attitude_rx_ms;
    return (s_enhancedTelem.stats[0].packets_received > 0) && (age < s_config.packet_timeout_ms);
}

bool RadioManager::hasControl() const {
    uint32_t age = millis() - s_enhancedTelem.control_rx_ms;
    return (s_enhancedTelem.stats[1].packets_received > 0) && (age < s_config.packet_timeout_ms);
}

bool RadioManager::hasMotors() const {
    uint32_t age = millis() - s_enhancedTelem.motors_rx_ms;
    return (s_enhancedTelem.stats[2].packets_received > 0) && (age < s_config.packet_timeout_ms);
}

bool RadioManager::hasStatus() const {
    uint32_t age = millis() - s_enhancedTelem.status_rx_ms;
    return (s_enhancedTelem.stats[3].packets_received > 0) && (age < s_config.packet_timeout_ms);
}

bool RadioManager::hasSensors() const {
    uint32_t age = millis() - s_enhancedTelem.sensors_rx_ms;
    return (s_enhancedTelem.stats[4].packets_received > 0) && (age < s_config.packet_timeout_ms);
}

bool RadioManager::hasSafety() const {
    uint32_t age = millis() - s_enhancedTelem.safety_rx_ms;
    return (s_enhancedTelem.stats[5].packets_received > 0) && (age < s_config.packet_timeout_ms);
}

bool RadioManager::hasPerformance() const {
    uint32_t age = millis() - s_enhancedTelem.performance_rx_ms;
    return (s_enhancedTelem.stats[6].packets_received > 0) && (age < s_config.packet_timeout_ms);
}

const EnhancedTelemStats& RadioManager::getEnhancedStats(TelemetryPacketType type) const {
    static const EnhancedTelemStats emptyStats = {0, 0, 0, 0, 0};
    uint8_t idx = type - 1;
    if (idx >= 7) return emptyStats;
    return s_enhancedTelem.stats[idx];
}

uint32_t RadioManager::getTotalEnhancedPackets() const {
    uint32_t total = 0;
    for (int i = 0; i < 7; i++) {
        total += s_enhancedTelem.stats[i].packets_received;
    }
    return total;
}

uint32_t RadioManager::getTotalEnhancedDrops() const {
    uint32_t total = 0;
    for (int i = 0; i < 7; i++) {
        total += s_enhancedTelem.stats[i].packets_dropped;
    }
    return total;
}

void RadioManager::setReceiverConfig(const TelemReceiverConfig& config) {
    s_config = config;
}

const TelemReceiverConfig& RadioManager::getReceiverConfig() const {
    return s_config;
}