
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
        
        // Debug: Log occasional packet status (every 50 packets = 1 second)
        static uint8_t debugCounter = 0;
        static uint32_t lastSuccessCount = 0;
        static uint32_t lastFailCount = 0;
        
        if (++debugCounter >= 50) {
            debugCounter = 0;
            
            uint32_t currentSuccess = m_radio->getSendSuccessCount();
            uint32_t currentFail = m_radio->getSendFailCount();
            uint32_t newSuccess = currentSuccess - lastSuccessCount;
            uint32_t newFails = currentFail - lastFailCount;
            
            if (sent) {
                if (newFails > 0) {
                    Logger::debugf("RADIO", "RC: queued seq=%d, %lu ACK, %lu FAIL (last 1s)", 
                                 packet.seq, newSuccess, newFails);
                } else if (newSuccess > 0) {
                    Logger::debugf("RADIO", "RC: queued seq=%d, %lu ACK (last 1s)", 
                                 packet.seq, newSuccess);
                } else {
                    Logger::debugf("RADIO", "RC: queued seq=%d, no callbacks yet", packet.seq);
                }
            } else {
                Logger::error("RADIO", "Failed to queue RC packet");
            }
            
            lastSuccessCount = currentSuccess;
            lastFailCount = currentFail;
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
        // OLED_DEMO: Override normal display when demo active
        if (m_oledDemo.isActive()) {
            m_oledDemo.update(inputs, lastTelem, dropCount);
        } else {
            // Normal display logic with debug view support
            if (Age::since(g_lastTelemUpdateMs) > TELEM_TIMEOUT_MS) {
                if (inputs.debugView) {
                    updateOledNoTelemDebugView(inputs);
                } else {
                    updateOledNoTelemNormalView(inputs);
                }
            } else {
                if (inputs.debugView) {
                    updateOledDebugView(inputs, lastTelem, dropCount);
                } else {
                    updateOledNormalView(inputs, lastTelem, dropCount);
                }
            }
        }
        display.display(); // Ensure display is updated
        g_lastOledUpdateMs = millis();
    }
}

void App::handleSerialCommands() {
    // Handle serial commands (e.g., 'M' for MAC address, 'O' for OLED demo, 'D' for diagnostics)
    while (Serial.available()) {
        char c = Serial.read();
        if (c == 'M' || c == 'm') {
            // Get MAC as bytes
            uint8_t ourMac[6];
            WiFi.macAddress(ourMac);
            Logger::macAddress("Our MAC", ourMac);
            Logger::macAddress("Drone MAC", g_droneMac);
        }
        // OLED_DEMO: Toggle demo mode
        else if (c == 'O' || c == 'o') {
            m_oledDemo.toggle();
        }
        // Radio diagnostics
        else if (c == 'D' || c == 'd') {
            uint32_t successCount = m_radio->getSendSuccessCount();
            uint32_t failCount = m_radio->getSendFailCount();
            uint32_t dropCount = m_radio->getDropCount();

            Serial.println("[RADIO_STATS]");
            Serial.printf("Send Success: %lu\n", successCount);
            Serial.printf("Send Fail: %lu\n", failCount);
            Serial.printf("Telemetry Drops: %lu\n", dropCount);

            if (successCount + failCount > 0) {
                float successRate = (float)successCount / (successCount + failCount) * 100.0f;
                Serial.printf("Success Rate: %.1f%%\n", successRate);
            }

            unsigned long telemAge = Age::since(g_lastTelemUpdateMs);
            Serial.printf("Last Telemetry: %lu ms ago\n", telemAge);
        }
        // Enhanced telemetry diagnostics
        else if (c == 'E' || c == 'e') {
            const TelemReceiverConfig& config = m_radio->getReceiverConfig();

            Serial.println("[ENHANCED_TELEMETRY_STATS]");
            Serial.printf("Enhanced Mode: %s\n", config.enable_enhanced ? "ON" : "OFF");
            Serial.printf("Legacy Mode: %s\n", config.enable_legacy ? "ON" : "OFF");
            Serial.printf("Packet Type Mask: 0x%02X\n", config.packet_type_mask);
            Serial.printf("Timeout: %u ms\n", config.packet_timeout_ms);
            Serial.println();

            uint32_t totalPkts = m_radio->getTotalEnhancedPackets();
            uint32_t totalDrops = m_radio->getTotalEnhancedDrops();
            Serial.printf("Total Enhanced Packets: %lu\n", totalPkts);
            Serial.printf("Total Enhanced Drops: %lu\n", totalDrops);
            if (totalPkts > 0) {
                float lossRate = (float)totalDrops / (totalPkts + totalDrops) * 100.0f;
                Serial.printf("Loss Rate: %.2f%%\n", lossRate);
            }
            Serial.println();

            // Per-packet-type statistics
            const char* typeNames[] = {"ATTITUDE", "CONTROL", "MOTORS", "STATUS", "SENSORS", "SAFETY", "PERFORMANCE"};
            Serial.println("Per-Packet Statistics:");
            for (uint8_t i = 1; i <= 7; i++) {
                TelemetryPacketType type = static_cast<TelemetryPacketType>(i);
                const EnhancedTelemStats& stats = m_radio->getEnhancedStats(type);

                if (stats.packets_received > 0) {
                    Serial.printf("  %s: RX=%lu, DROP=%lu, CRC_ERR=%lu, SEQ=%u\n",
                                typeNames[i-1],
                                stats.packets_received,
                                stats.packets_dropped,
                                stats.crc_errors,
                                stats.last_seq);
                }
            }
            Serial.println();

            // Data freshness
            Serial.println("Data Freshness:");
            Serial.printf("  ATTITUDE: %s\n", m_radio->hasAttitude() ? "Fresh" : "Stale");
            Serial.printf("  CONTROL: %s\n", m_radio->hasControl() ? "Fresh" : "Stale");
            Serial.printf("  MOTORS: %s\n", m_radio->hasMotors() ? "Fresh" : "Stale");
            Serial.printf("  STATUS: %s\n", m_radio->hasStatus() ? "Fresh" : "Stale");
            Serial.printf("  SENSORS: %s\n", m_radio->hasSensors() ? "Fresh" : "Stale");
            Serial.printf("  SAFETY: %s\n", m_radio->hasSafety() ? "Fresh" : "Stale");
            Serial.printf("  PERFORMANCE: %s\n", m_radio->hasPerformance() ? "Fresh" : "Stale");
        }
        // Toggle enhanced telemetry mode
        else if (c == 'T' || c == 't') {
            TelemReceiverConfig config = m_radio->getReceiverConfig();
            config.enable_enhanced = !config.enable_enhanced;
            m_radio->setReceiverConfig(config);
            Serial.printf("[CONFIG] Enhanced telemetry: %s\n", config.enable_enhanced ? "ENABLED" : "DISABLED");
        }
    }
}

// OLED_DEMO: Implementation of demo state machine
void OledDemo::toggle() {
    if (m_state == OledDemoState::OFF) {
        m_state = OledDemoState::NO_TELEM_NORMAL;
        m_stateStartMs = millis();
        Serial.println("[OLED_DEMO] Started - cycling through 8 views (2s each)");
    } else {
        m_state = OledDemoState::OFF;
        Serial.println("[OLED_DEMO] Stopped");
    }
}

void OledDemo::update(const ControlInputs& inputs, const TelemetryPacket& lastTelem, uint32_t dropCount) {
    // Safety check - stop demo if unsafe conditions
    if (shouldStop(inputs, lastTelem)) {
        m_state = OledDemoState::OFF;
        Serial.println("[OLED_DEMO] Auto-stopped for safety");
        return;
    }
    
    // Check if it's time to advance to next state
    if (millis() - m_stateStartMs >= STATE_DURATION_MS) {
        advance();
    }
    
    // Render current state
    renderCurrentState(inputs, lastTelem, dropCount);
}

void OledDemo::advance() {
    switch (m_state) {
        case OledDemoState::NO_TELEM_NORMAL:
            m_state = OledDemoState::NO_TELEM_FLASH;
            Serial.println("[OLED_DEMO] -> No Telem Flash Warning");
            break;
        case OledDemoState::NO_TELEM_FLASH:
            m_state = OledDemoState::NO_TELEM_DEBUG;
            Serial.println("[OLED_DEMO] -> No Telem Debug View");
            break;
        case OledDemoState::NO_TELEM_DEBUG:
            m_state = OledDemoState::NORMAL_VIEW;
            Serial.println("[OLED_DEMO] -> Normal View (with telem)");
            break;
        case OledDemoState::NORMAL_VIEW:
            m_state = OledDemoState::NORMAL_FLASH;
            Serial.println("[OLED_DEMO] -> Normal Flash Warning");
            break;
        case OledDemoState::NORMAL_FLASH:
            m_state = OledDemoState::NORMAL_STATUS;
            Serial.println("[OLED_DEMO] -> Normal Status Indicator");
            break;
        case OledDemoState::NORMAL_STATUS:
            m_state = OledDemoState::DEBUG_VIEW;
            Serial.println("[OLED_DEMO] -> Debug View (PID tuning)");
            break;
        case OledDemoState::DEBUG_VIEW:
            m_state = OledDemoState::DEBUG_DROPS;
            Serial.println("[OLED_DEMO] -> Debug View with Drops");
            break;
        case OledDemoState::DEBUG_DROPS:
            m_state = OledDemoState::NO_TELEM_NORMAL;
            Serial.println("[OLED_DEMO] -> Cycle restart: No Telem Normal");
            break;
        default:
            m_state = OledDemoState::OFF;
            break;
    }
    m_stateStartMs = millis();
}

void OledDemo::renderCurrentState(const ControlInputs& inputs, const TelemetryPacket& lastTelem, uint32_t dropCount) {
    ControlInputs mockInputs;
    TelemetryPacket mockTelem;
    uint32_t mockDropCount = 0;
    
    // Set global state variables to simulate different conditions
    extern bool g_showHorizFlash;
    extern bool g_horizonOK;
    extern bool g_telemArmed;
    extern unsigned long g_lastTelemUpdateMs;
    extern float g_telemFrequency;
    
    // Save original states
    bool origHorizFlash = g_showHorizFlash;
    bool origHorizonOK = g_horizonOK;
    bool origTelemArmed = g_telemArmed;
    unsigned long origLastTelem = g_lastTelemUpdateMs;
    float origTelemFreq = g_telemFrequency;
    
    switch (m_state) {
        case OledDemoState::NO_TELEM_NORMAL:
            Serial.println("[OLED_DEMO] Showing: No Telem Normal View");
            createMockInputs(mockInputs, false);
            g_showHorizFlash = false;
            g_lastTelemUpdateMs = millis() - (TELEM_TIMEOUT_MS + 1000); // Force stale
            updateOledNoTelemNormalView(mockInputs);
            break;
            
        case OledDemoState::NO_TELEM_FLASH:
            Serial.println("[OLED_DEMO] Showing: No Telem Flash Warning");
            createMockInputs(mockInputs, false);
            g_showHorizFlash = true;
            g_horizonOK = false;
            g_lastTelemUpdateMs = millis() - (TELEM_TIMEOUT_MS + 1000); // Force stale
            updateOledNoTelemNormalView(mockInputs);
            break;
            
        case OledDemoState::NO_TELEM_DEBUG:
            Serial.println("[OLED_DEMO] Showing: No Telem Debug View");
            createMockInputs(mockInputs, true);
            g_showHorizFlash = false;
            g_lastTelemUpdateMs = millis() - (TELEM_TIMEOUT_MS + 1000); // Force stale
            updateOledNoTelemDebugView(mockInputs);
            break;
            
        case OledDemoState::NORMAL_VIEW:
            Serial.println("[OLED_DEMO] Showing: Normal View with Telemetry");
            createMockInputs(mockInputs, false);
            createMockTelemetry(mockTelem);
            g_showHorizFlash = false;
            g_horizonOK = true;
            g_telemArmed = false;
            g_lastTelemUpdateMs = millis(); // Fresh telemetry
            g_telemFrequency = 9.8f;
            updateOledNormalView(mockInputs, mockTelem, mockDropCount);
            break;
            
        case OledDemoState::NORMAL_FLASH:
            Serial.println("[OLED_DEMO] Showing: Normal Flash Warning (LEVEL!)");
            createMockInputs(mockInputs, false);
            createMockTelemetry(mockTelem);
            g_showHorizFlash = true;
            g_horizonOK = false;
            g_lastTelemUpdateMs = millis(); // Fresh telemetry
            updateOledNormalView(mockInputs, mockTelem, mockDropCount);
            break;
            
        case OledDemoState::NORMAL_STATUS:
            Serial.println("[OLED_DEMO] Showing: Normal Status Indicator (HORIZ?)");
            createMockInputs(mockInputs, false);
            createMockTelemetry(mockTelem);
            g_showHorizFlash = false;
            g_horizonOK = false;
            g_telemArmed = false;
            g_lastTelemUpdateMs = millis(); // Fresh telemetry
            g_telemFrequency = 10.1f;
            updateOledNormalView(mockInputs, mockTelem, mockDropCount);
            break;
            
        case OledDemoState::DEBUG_VIEW:
            Serial.println("[OLED_DEMO] Showing: Debug View (PID tuning)");
            createMockInputs(mockInputs, true);
            createMockTelemetry(mockTelem);
            g_showHorizFlash = false;
            g_lastTelemUpdateMs = millis(); // Fresh telemetry
            updateOledDebugView(mockInputs, mockTelem, mockDropCount);
            break;
            
        case OledDemoState::DEBUG_DROPS:
            Serial.println("[OLED_DEMO] Showing: Debug View with Packet Drops");
            createMockInputs(mockInputs, true);
            createMockTelemetry(mockTelem);
            g_showHorizFlash = false;
            g_lastTelemUpdateMs = millis(); // Fresh telemetry
            mockDropCount = DROP_INDICATOR_COUNT; // Force drop indicator
            updateOledDebugView(mockInputs, mockTelem, mockDropCount);
            break;
            
        default:
            break;
    }
    
    // Restore original states
    g_showHorizFlash = origHorizFlash;
    g_horizonOK = origHorizonOK;
    g_telemArmed = origTelemArmed;
    g_lastTelemUpdateMs = origLastTelem;
    g_telemFrequency = origTelemFreq;
}

bool OledDemo::shouldStop(const ControlInputs& inputs, const TelemetryPacket& lastTelem) {
    // Stop demo if unsafe conditions detected
    return inputs.armed ||                    // User trying to arm
           inputs.throttle > 50 ||           // Throttle not at zero
           (lastTelem.armed & 0x01);         // Drone reports armed
}

void OledDemo::createMockInputs(ControlInputs& mockInputs, bool debugView) {
    // OLED_DEMO: Safe, representative mock control inputs
    mockInputs.throttle = 0;           // Always safe for demo
    mockInputs.yaw = -150;            // Realistic stick input
    mockInputs.pitch = 200;           // Realistic stick input
    mockInputs.roll = -75;            // Realistic stick input
    mockInputs.armed = false;         // Always false for safety
    mockInputs.debugView = debugView; // Controlled by demo state
}

void OledDemo::createMockTelemetry(TelemetryPacket& mockTelem) {
    // OLED_DEMO: Realistic telemetry data for demo
    mockTelem.roll_deg_x10 = -52;     // -5.2 degrees (slight tilt)
    mockTelem.pitch_deg_x10 = 31;     // 3.1 degrees
    mockTelem.yawRate_dps = -45;      // Turning left
    mockTelem.setAngleRoll_x10 = -50; // Close to actual angle
    mockTelem.setAnglePitch_x10 = 30;
    mockTelem.rollRate_dps = -48;     // Rate values
    mockTelem.pitchRate_dps = 35;
    mockTelem.outRoll = 1850;         // PID outputs (realistic range)
    mockTelem.outPitch = 1920;
    mockTelem.outYaw = 1480;
    mockTelem.armed = 0x00;           // Not armed (bit 0 = armedDRN, bit 1 = horizonOK)
}
