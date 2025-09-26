#pragma once
#include <cstdint>
#include <cstddef>
#include <esp_now.h>

class RadioManager {
public:
    bool init(uint8_t channel = 1);
    bool setPeerMac(const uint8_t* mac);
    bool sendPacket(const void* data, size_t len);
    void setChannel(uint8_t channel);
    
private:
    uint8_t m_peerMac[6] = {0};
    uint8_t m_channel = 1;
    bool m_initialized = false;
    
    static void onSendCallback(const uint8_t *mac_addr, esp_now_send_status_t status);
};