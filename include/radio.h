#pragma once
#include <cstdint>
#include <cstddef>
#include <esp_now.h>
#include "protocol.h"

class RadioManager {
public:
    bool init(uint8_t channel = 1);
    bool setPeerMac(const uint8_t* mac);
    bool sendPacket(const void* data, size_t len);
    void setChannel(uint8_t channel);
    
    // TELEM: Telemetry reception
    bool hasNewTelemetry() const;
    TelemetryPacket getLastTelemetry();
    void clearNewTelemetryFlag();
    uint32_t getDropCount() const;
    
    // Send status tracking
    uint32_t getSendSuccessCount() const;
    uint32_t getSendFailCount() const;
    
private:
    uint8_t m_peerMac[6] = {0};
    uint8_t m_channel = 1;
    bool m_initialized = false;
    
    // TELEM: Telemetry state
    static TelemetryPacket s_lastTelemetry;
    static volatile bool s_newTelemetryAvailable;
    static volatile uint32_t s_lastTelemSeq;
    static volatile uint32_t s_dropCount;
    
    // Send status tracking
    static volatile uint32_t s_sendSuccessCount;
    static volatile uint32_t s_sendFailCount;
    
    static void onSendCallback(const uint8_t *mac_addr, esp_now_send_status_t status);
    static void onReceiveCallback(const uint8_t *mac_addr, const uint8_t *data, int len);
};