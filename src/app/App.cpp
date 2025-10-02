
#include "App.h"
#include "config.h"
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>
#include "../utils/Timing.h"
#include "../ui/Display.h"
#include "protocol.h"
#include "radio.h" 
#include "control.h"

// Extern global objects and variables from main.cpp and other modules
extern Adafruit_SSD1306 display;
extern unsigned long g_lastOledUpdateMs;
extern unsigned long g_lastTelemUpdateMs;
extern float g_telemFrequency;
extern bool g_telemArmed;
extern bool g_horizonOK;
extern unsigned long g_horizFlashStartMs;
extern bool g_showHorizFlash;
extern uint8_t g_armPulseCountdown;
extern bool g_lastInputsArmed;
extern uint8_t g_droneMac[6];

// Constants from config.h or protocol.h
#ifndef OLED_ADDR
#define OLED_ADDR 0x3C
#endif

#ifndef RC_FRAME_PERIOD_MS
#define RC_FRAME_PERIOD_MS 20
#endif
#ifndef OLED_UPDATE_PERIOD_MS
#define OLED_UPDATE_PERIOD_MS 50
#endif
#ifndef TELEM_UPDATE_PERIOD_MS
#define TELEM_UPDATE_PERIOD_MS 100
#endif
#ifndef HORIZ_FLASH_MS
#define HORIZ_FLASH_MS 1000
#endif
#ifndef TELEM_TIMEOUT_MS
#define TELEM_TIMEOUT_MS 300
#endif
#ifndef DROP_INDICATOR_COUNT
#define DROP_INDICATOR_COUNT 5
#endif
#ifndef ARM_PULSE_PACKETS
#define ARM_PULSE_PACKETS 3
#endif
#ifndef ESPNOW_CHANNEL
#define ESPNOW_CHANNEL 1
#endif
#ifndef TELEMETRY_RATE_HZ
#define TELEMETRY_RATE_HZ 10
#endif

// Forward declare helper functions
bool isTelemHorizonOK(const TelemetryPacket& telem);
bool isTelemArmed(const TelemetryPacket& telem);
bool isValidTelemPacket(const TelemetryPacket& telem);
namespace Logger {
    void error(const char* category, const char* message);
    void setup(const char* message);
    void telemetry(unsigned long ms, const ControlInputs& inputs, const TelemetryPacket& telem);
    void macAddress(const char* label, const uint8_t* mac);
    void debugf(const char* category, const char* format, ...);
}

// Helper function to build RC packet
void buildRcPacket(const ControlInputs& inputs, RcPacket& packet) {
    extern volatile uint16_t g_sequenceNumber;
    
    packet.magic = RC_PACKET_MAGIC;
    packet.version = RC_PACKET_VERSION;
    packet.seq = g_sequenceNumber++;
    packet.thr = inputs.throttle;
    packet.yaw = inputs.yaw;
    packet.pitch = inputs.pitch;
    packet.roll = inputs.roll;
    packet.flags = 0;
    if (inputs.armed) packet.flags |= RC_FLAG_ARMED;
    if (inputs.debugView) packet.flags |= RC_FLAG_DEBUG;
    packet.rssi_hint = 0;
    
    // Calculate CRC over all fields except crc
    packet.crc = crc16_x25((uint8_t*)&packet, sizeof(packet) - sizeof(packet.crc));
}

// Forward declare existing globals to maintain compatibility
extern RadioManager radio;
extern ControlManager control;
extern unsigned long g_lastOledUpdateMs;

// Global app instance
App g_app;


bool App::init() {
    // Initialize pointers to global managers
    m_control = &control;
    m_radio = &radio;
    m_lastOledUpdateMs = 0;

    // Serial and I2C
    Serial.begin(115200);
    delay(100);
    Wire.begin();

    // OLED
    if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
        Logger::error("INIT", "SSD1306 allocation failed");
        return false;
    }
    display.clearDisplay();
    display.display();

    // Radio
    if (!m_radio->init(ESPNOW_CHANNEL)) {
        Logger::error("INIT", "RadioManager init failed");
        return false;
    }
    
    // Set drone peer MAC address
    Logger::macAddress("Setting drone peer", g_droneMac);
    if (!m_radio->setPeerMac(g_droneMac)) {
        Logger::error("INIT", "Failed to set drone peer MAC");
        return false;
    }
    
    Logger::setup("Radio peer MAC set successfully");

    // Control
    if (!m_control->init()) {
        Logger::error("INIT", "ControlManager init failed");
        return false;
    }

    Logger::setup("App initialized");
    return true;
}


void App::loop() {
    static Every rcEvery(RC_FRAME_PERIOD_MS);
    static Every oledEvery(OLED_UPDATE_PERIOD_MS);
    static Every telemEvery(TELEM_UPDATE_PERIOD_MS);
    static FlashTimer horizFlashTimer(HORIZ_FLASH_MS);
    static uint32_t dropCount = 0;
    static TelemetryPacket lastTelem = {};

    // 1. Handle serial commands (e.g., MAC address)
    handleSerialCommands();

    // 2. Process control inputs (joysticks, switches)
    const ControlInputs& inputs = m_control->readInputs();

    // 3. Apply safety logic (arming, horizon, telemetry)
    // --- Horizon safety ---
    g_horizonOK = isTelemHorizonOK(lastTelem);
    g_telemArmed = isTelemArmed(lastTelem);

    // --- Horizon flash logic ---
    if (!g_horizonOK || !g_telemArmed || Age::since(g_lastTelemUpdateMs) > TELEM_TIMEOUT_MS) {
        if (!g_showHorizFlash) {
            g_showHorizFlash = true;
            g_horizFlashStartMs = millis();
            horizFlashTimer.start();
        }
    } else {
        g_showHorizFlash = false;
        horizFlashTimer.stop();
    }
    if (g_showHorizFlash && horizFlashTimer.isActive()) {
        g_showHorizFlash = false;
    }

    // --- Arm pulse logic ---
    if (inputs.armed && !g_lastInputsArmed) {
        g_armPulseCountdown = ARM_PULSE_PACKETS;
    }
    g_lastInputsArmed = inputs.armed;

    // 4. Build and send RC packet (50Hz)
    if (rcEvery.check()) {
        RcPacket packet = {};
        buildRcPacket(inputs, packet);
        if (g_armPulseCountdown > 0) {
            packet.flags |= RC_FLAG_ARMED;
            g_armPulseCountdown--;
        }
        bool sent = m_radio->sendPacket(&packet, sizeof(packet));
        
        // Debug: Log occasional packet sends (every 50 packets = 1 second)
        static uint8_t debugCounter = 0;
        if (++debugCounter >= 50) {
            debugCounter = 0;
            if (sent) {
                Logger::debugf("RADIO", "RC packet sent OK, seq=%d", packet.seq);
            } else {
                Logger::error("RADIO", "Failed to send RC packet");
            }
        }
    }

    // 5. Process telemetry (10Hz)
    if (telemEvery.check()) {
        if (m_radio->hasNewTelemetry()) {
            lastTelem = m_radio->getLastTelemetry();
            m_radio->clearNewTelemetryFlag();
            g_lastTelemUpdateMs = millis();
            g_telemFrequency = 10.0f; // Calculated elsewhere or fixed rate
            dropCount = 0;
            Logger::telemetry(millis(), inputs, lastTelem);
        } else {
            dropCount++;
        }
    }

    // 6. Update OLED display (20Hz)
    if (oledEvery.check()) {
        if (Age::since(g_lastTelemUpdateMs) > TELEM_TIMEOUT_MS) {
            updateOledNoTelemNormalView(inputs);
        } else {
            updateOledNormalView(inputs, lastTelem, dropCount);
        }
        display.display(); // Ensure display is updated
        g_lastOledUpdateMs = millis();
    }
}

void App::handleSerialCommands() {
    // Handle serial commands (e.g., 'M' for MAC address)
    while (Serial.available()) {
        char c = Serial.read();
        if (c == 'M' || c == 'm') {
            // Get MAC as bytes
            uint8_t ourMac[6];
            WiFi.macAddress(ourMac);
            Logger::macAddress("Our MAC", ourMac);
            Logger::macAddress("Drone MAC", g_droneMac);
        }
    }
}

