#include "radio.h"
#include "config.h"
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <cstring>


// Enhanced telemetry state
EnhancedTelemData RadioManager::s_enhancedTelem = {};
bool RadioManager::s_newEnhancedAvailable = false;
uint8_t RadioManager::s_newPacketTypeFlags = 0;

// PARAM response state
bool RadioManager::s_newParamResponse = false;

// Telemetry receiver configuration
TelemReceiverConfig RadioManager::s_config = {
    .enable_enhanced = true,     // Enhanced telemetry enabled
    .packet_type_mask = 0x7F,    // All 7 packet types enabled (ATTITUDE..PERFORMANCE)
    .packet_timeout_ms = 300     // Packet freshness timeout
};

// Send status tracking
volatile uint32_t RadioManager::s_sendSuccessCount = 0;
volatile uint32_t RadioManager::s_sendFailCount = 0;

// Thread safety
SemaphoreHandle_t RadioManager::s_telemMutex = NULL;

// Error logging (optional)
IRadioErrorLogger* RadioManager::s_errorLogger = nullptr;

void RadioManager::setErrorLogger(IRadioErrorLogger* logger) {
    s_errorLogger = logger;
}

// Helper macro for packet handlers to reduce code duplication
// NOTE: LOWERCASE_TYPE must match struct member names (attitude, control, etc.)
#define HANDLE_TELEMETRY_PACKET(TYPE, ENUM_TYPE, STRUCT_NAME, LOWERCASE_TYPE, INDEX) \
void RadioManager::handleEnhanced##TYPE(const uint8_t* data, int len) { \
    if (len != sizeof(Telemetry##STRUCT_NAME)) { \
        if (s_errorLogger) s_errorLogger->logWrongPacketSize(len, sizeof(Telemetry##STRUCT_NAME)); \
        return; \
    } \
    const Telemetry##STRUCT_NAME* packet = reinterpret_cast<const Telemetry##STRUCT_NAME*>(data); \
    uint16_t calculatedCrc = crc16_x25(data, len - sizeof(packet->crc)); \
    bool crcValid = (calculatedCrc == packet->crc); \
    if (!crcValid) { \
        if (s_errorLogger) s_errorLogger->logCrcError(calculatedCrc, packet->crc); \
        if (xSemaphoreTakeFromISR(s_telemMutex, NULL) == pdTRUE) { \
            updatePacketStats(TELEM_TYPE_##ENUM_TYPE, packet->header.seq, false); \
            xSemaphoreGiveFromISR(s_telemMutex, NULL); \
        } \
        return; \
    } \
    if (xSemaphoreTakeFromISR(s_telemMutex, NULL) == pdTRUE) { \
        updatePacketStats(TELEM_TYPE_##ENUM_TYPE, packet->header.seq, true); \
        memcpy(&s_enhancedTelem.LOWERCASE_TYPE, packet, sizeof(Telemetry##STRUCT_NAME)); \
        s_enhancedTelem.LOWERCASE_TYPE##_rx_ms = millis(); \
        s_enhancedTelem.stats[INDEX].last_timestamp_us = packet->header.timestamp_us; \
        s_newEnhancedAvailable = true; \
        s_newPacketTypeFlags |= (1 << INDEX); \
        xSemaphoreGiveFromISR(s_telemMutex, NULL); \
    } \
}

// Static callback function
void RadioManager::onSendCallback(const uint8_t *mac_addr, esp_now_send_status_t status) {
    (void)mac_addr; // Unused
    
    if (status == ESP_NOW_SEND_SUCCESS) {
        s_sendSuccessCount++;
    } else {
        s_sendFailCount++;
    }
}

// Enhanced telemetry receive callback
void RadioManager::onReceiveCallback(const uint8_t *mac_addr, const uint8_t *data, int len) {
    (void)mac_addr; // Unused

    // Check for minimal header size
    if (len < 2) return;

    uint8_t magic = data[0];
    uint8_t version = data[1];

    // Only handle enhanced telemetry
    if (magic == TELEM_ENHANCED_MAGIC && version == TELEM_ENHANCED_VERSION) {
        if (!s_config.enable_enhanced) return;

        if (len < sizeof(TelemetryHeader)) {
            if (s_errorLogger) {
                s_errorLogger->logWrongPacketSize(len, sizeof(TelemetryHeader));
            }
            return;
        }

        const TelemetryHeader* header = reinterpret_cast<const TelemetryHeader*>(data);
        TelemetryPacketType type = static_cast<TelemetryPacketType>(header->type);

        // Check if this packet type is enabled (skip check for PARAM packets 0x10, 0x11)
        if (type < TELEM_TYPE_PARAM_REQUEST) {
            uint8_t typeBit = 1 << (type - 1);
            if (!(s_config.packet_type_mask & typeBit)) {
                return; // Packet type filtered out
            }
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
            case TELEM_TYPE_PARAM_RESPONSE:
                handleParamResponse(data, len);
                break;
            default:
                // Unknown packet type
                return;
        }
    } else {
        // Unknown packet format
        if (s_errorLogger) {
            s_errorLogger->logWrongMagicVersion(magic, version);
        }
    }
}

bool RadioManager::init(uint8_t channel) {
    m_channel = channel;

    // Create mutex for telemetry data protection
    if (s_telemMutex == NULL) {
        s_telemMutex = xSemaphoreCreateMutex();
        if (s_telemMutex == NULL) {
            return false;  // Mutex creation failed
        }
    }

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

// Generate all packet handlers using macro (thread-safe with mutexes)
HANDLE_TELEMETRY_PACKET(Attitude, ATTITUDE, Attitude, attitude, 0)
HANDLE_TELEMETRY_PACKET(Control, CONTROL, Control, control, 1)
HANDLE_TELEMETRY_PACKET(Motors, MOTORS, Motors, motors, 2)
HANDLE_TELEMETRY_PACKET(Status, STATUS, Status, status, 3)
HANDLE_TELEMETRY_PACKET(Sensors, SENSORS, Sensors, sensors, 4)
HANDLE_TELEMETRY_PACKET(Safety, SAFETY, Safety, safety, 5)
HANDLE_TELEMETRY_PACKET(Performance, PERFORMANCE, Performance, performance, 6)

// ============================================================================
// Enhanced Telemetry Public API
// ============================================================================

bool RadioManager::hasNewEnhancedTelemetry() const {
    bool result = false;
    if (xSemaphoreTake(s_telemMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        result = s_newEnhancedAvailable;
        xSemaphoreGive(s_telemMutex);
    }
    return result;
}

const EnhancedTelemData& RadioManager::getEnhancedTelemetry() const {
    // Note: Caller should hold mutex or accept potential race
    // This is acceptable as telemetry is read-only after reception
    return s_enhancedTelem;
}

void RadioManager::clearNewEnhancedFlag() {
    if (xSemaphoreTake(s_telemMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        s_newEnhancedAvailable = false;
        s_newPacketTypeFlags = 0;
        xSemaphoreGive(s_telemMutex);
    }
}

bool RadioManager::hasAttitude() const {
    bool result = false;
    if (xSemaphoreTake(s_telemMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        uint32_t age = millis() - s_enhancedTelem.attitude_rx_ms;
        result = (s_enhancedTelem.stats[0].packets_received > 0) && (age < s_config.packet_timeout_ms);
        xSemaphoreGive(s_telemMutex);
    }
    return result;
}

bool RadioManager::hasControl() const {
    bool result = false;
    if (xSemaphoreTake(s_telemMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        uint32_t age = millis() - s_enhancedTelem.control_rx_ms;
        result = (s_enhancedTelem.stats[1].packets_received > 0) && (age < s_config.packet_timeout_ms);
        xSemaphoreGive(s_telemMutex);
    }
    return result;
}

bool RadioManager::hasMotors() const {
    bool result = false;
    if (xSemaphoreTake(s_telemMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        uint32_t age = millis() - s_enhancedTelem.motors_rx_ms;
        result = (s_enhancedTelem.stats[2].packets_received > 0) && (age < s_config.packet_timeout_ms);
        xSemaphoreGive(s_telemMutex);
    }
    return result;
}

bool RadioManager::hasStatus() const {
    bool result = false;
    if (xSemaphoreTake(s_telemMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        uint32_t age = millis() - s_enhancedTelem.status_rx_ms;
        result = (s_enhancedTelem.stats[3].packets_received > 0) && (age < s_config.packet_timeout_ms);
        xSemaphoreGive(s_telemMutex);
    }
    return result;
}

bool RadioManager::hasSensors() const {
    bool result = false;
    if (xSemaphoreTake(s_telemMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        uint32_t age = millis() - s_enhancedTelem.sensors_rx_ms;
        result = (s_enhancedTelem.stats[4].packets_received > 0) && (age < s_config.packet_timeout_ms);
        xSemaphoreGive(s_telemMutex);
    }
    return result;
}

bool RadioManager::hasSafety() const {
    bool result = false;
    if (xSemaphoreTake(s_telemMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        uint32_t age = millis() - s_enhancedTelem.safety_rx_ms;
        result = (s_enhancedTelem.stats[5].packets_received > 0) && (age < s_config.packet_timeout_ms);
        xSemaphoreGive(s_telemMutex);
    }
    return result;
}

bool RadioManager::hasPerformance() const {
    bool result = false;
    if (xSemaphoreTake(s_telemMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        uint32_t age = millis() - s_enhancedTelem.performance_rx_ms;
        result = (s_enhancedTelem.stats[6].packets_received > 0) && (age < s_config.packet_timeout_ms);
        xSemaphoreGive(s_telemMutex);
    }
    return result;
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

// ============================================================================
// PARAM System Handlers
// ============================================================================

void RadioManager::handleParamResponse(const uint8_t* data, int len) {
    if (len != sizeof(TelemetryParamResponse)) {
        if (s_errorLogger) {
            s_errorLogger->logWrongPacketSize(len, sizeof(TelemetryParamResponse));
        }
        return;
    }

    const TelemetryParamResponse* packet = reinterpret_cast<const TelemetryParamResponse*>(data);

    // Validate CRC
    uint16_t calculatedCrc = crc16_x25(data, len - sizeof(packet->crc));
    if (calculatedCrc != packet->crc) {
        if (s_errorLogger) {
            s_errorLogger->logCrcError(calculatedCrc, packet->crc);
        }
        return;
    }

    // Store PARAM response (thread-safe)
    if (xSemaphoreTakeFromISR(s_telemMutex, NULL) == pdTRUE) {
        memcpy(&s_enhancedTelem.paramResponse, packet, sizeof(TelemetryParamResponse));
        s_enhancedTelem.param_response_rx_ms = millis();
        s_newParamResponse = true;
        xSemaphoreGiveFromISR(s_telemMutex, NULL);
    }
}

bool RadioManager::hasParamResponse() const {
    bool result = false;
    if (xSemaphoreTake(s_telemMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        result = s_newParamResponse;
        xSemaphoreGive(s_telemMutex);
    }
    return result;
}

void RadioManager::clearParamResponseFlag() {
    if (xSemaphoreTake(s_telemMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        s_newParamResponse = false;
        xSemaphoreGive(s_telemMutex);
    }
}