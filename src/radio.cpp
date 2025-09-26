#include "radio.h"
#include "config.h"
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <cstring>

// Static callback function
void RadioManager::onSendCallback(const uint8_t *mac_addr, esp_now_send_status_t status) {
    // Callback for send status - could be used for link quality indication
    (void)mac_addr;
    (void)status;
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