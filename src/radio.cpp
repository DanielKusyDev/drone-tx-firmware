#include "radio.h"
#include "config.h"
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <cstring>

// TELEM: Static telemetry variables
TelemetryPacket RadioManager::s_lastTelemetry = {};
volatile bool RadioManager::s_newTelemetryAvailable = false;
volatile uint32_t RadioManager::s_lastTelemSeq = 0;
volatile uint32_t RadioManager::s_dropCount = 0;

// Static callback function
void RadioManager::onSendCallback(const uint8_t *mac_addr, esp_now_send_status_t status) {
    // Callback for send status - could be used for link quality indication
    (void)mac_addr;
    (void)status;
}

// TELEM: Receive callback for telemetry
void RadioManager::onReceiveCallback(const uint8_t *mac_addr, const uint8_t *data, int len) {
    (void)mac_addr; // Unused
    
    // DEBUG: Print received packet info
    Serial.print("[RECV] Len: ");
    Serial.print(len);
    Serial.print(" Expected: ");
    Serial.println(sizeof(TelemetryPacket));
    
    // Quick validation
    if (len != sizeof(TelemetryPacket)) {
        Serial.println("[RECV] Wrong packet size!");
        return;
    }
    
    const TelemetryPacket* packet = reinterpret_cast<const TelemetryPacket*>(data);
    
    // DEBUG: Print magic and version
    Serial.print("[RECV] Magic: 0x");
    Serial.print(packet->magic, HEX);
    Serial.print(" Ver: ");
    Serial.println(packet->version);
    
    // Check magic and version
    if (packet->magic != TELEM_PACKET_MAGIC || packet->version != TELEM_PACKET_VERSION) {
        Serial.println("[RECV] Wrong magic/version!");
        return;
    }
    
    // Verify CRC
    uint16_t calculatedCrc = crc16_x25(data, len - sizeof(packet->crc));
    if (calculatedCrc != packet->crc) {
        Serial.print("[RECV] CRC Error! Calc: 0x");
        Serial.print(calculatedCrc, HEX);
        Serial.print(" Got: 0x");
        Serial.println(packet->crc, HEX);
        return;
    }
    
    Serial.print("[RECV] Good packet! Seq: ");
    Serial.println(packet->seq);
    
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