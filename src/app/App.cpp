
#include "App.h"
#include "config.h"
#include "logger.h"
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
extern bool g_calOK;
extern bool g_calibrating;
extern bool g_calFailed;
extern unsigned long g_horizFlashStartMs;
extern bool g_showHorizFlash;
extern uint8_t g_armPulseCountdown;
extern bool g_lastInputsArmed;
extern uint8_t g_droneMac[6];
extern bool g_forceDisarmActive;
extern unsigned long g_forceDisarmTimestamp;

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

// Helper function to build RC packet
void buildRcPacket(const ControlInputs &inputs, RcPacket &packet)
{
    extern volatile uint16_t g_sequenceNumber;

    packet.magic = RC_PACKET_MAGIC;
    packet.version = RC_PACKET_VERSION;
    packet.seq = g_sequenceNumber++;
    packet.thr = inputs.throttle;
    packet.yaw = inputs.yaw;
    packet.pitch = inputs.pitch;
    packet.roll = inputs.roll;
    packet.flags = 0;
    if (inputs.armed)
        packet.flags |= RC_FLAG_ARMED;
    if (inputs.debugView)
        packet.flags |= RC_FLAG_DEBUG;
    packet.rssi_hint = 0;

    // Calculate CRC over all fields except crc
    packet.crc = crc16_x25((uint8_t *)&packet, sizeof(packet) - sizeof(packet.crc));
}

// Forward declare existing globals to maintain compatibility
extern RadioManager radio;
extern ControlManager control;
extern unsigned long g_lastOledUpdateMs;

// Global app instance
App g_app;

bool App::init()
{
    // Initialize pointers to global managers
    m_control = &control;
    m_radio = &radio;
    m_lastOledUpdateMs = 0;

    // Initialize force disarm tracking
    m_lastArmedState = false;
    m_forceDisarmDetected = false;
    m_forceDisarmTimestamp = 0;

    // Serial and I2C
    Serial.begin(115200);
    delay(100);

    // Initialize logger first
    Logger::init();
    LOG_INFO(SYSTEM, "Transmitter starting up...");

    Wire.begin();

    // OLED
    LOG_INFO(OLED, "Initializing OLED display...");
    if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR))
    {
        LOG_ERROR(OLED, "SSD1306 allocation failed");
        return false;
    }
    display.clearDisplay();
    display.display();
    LOG_INFO(OLED, "OLED initialized successfully");

    // Radio
    LOG_INFO(RADIO, "Initializing ESP-NOW radio (channel %d)...", ESPNOW_CHANNEL);
    if (!m_radio->init(ESPNOW_CHANNEL))
    {
        LOG_ERROR(RADIO, "RadioManager init failed");
        return false;
    }

    // Set drone peer MAC address
    LOG_INFO(RADIO, "Setting drone peer MAC: %02X:%02X:%02X:%02X:%02X:%02X",
             g_droneMac[0], g_droneMac[1], g_droneMac[2],
             g_droneMac[3], g_droneMac[4], g_droneMac[5]);
    if (!m_radio->setPeerMac(g_droneMac))
    {
        LOG_ERROR(RADIO, "Failed to set drone peer MAC");
        return false;
    }
    LOG_INFO(RADIO, "Radio initialized successfully");

    // Control
    LOG_INFO(INPUTS, "Initializing control inputs...");
    if (!m_control->init())
    {
        LOG_ERROR(INPUTS, "ControlManager init failed");
        return false;
    }
    LOG_INFO(INPUTS, "Control inputs initialized");

    // Calibrate stick centers (ensure sticks are neutral!)
    LOG_INFO(INPUTS, "Calibrating stick centers - hold sticks at neutral position...");
    m_control->calibrate();
    LOG_INFO(INPUTS, "Stick calibration complete");

    LOG_INFO(SYSTEM, "Transmitter initialization complete");
    return true;
}

void App::loop()
{
    static Every rcEvery(RC_FRAME_PERIOD_MS);
    static Every oledEvery(OLED_UPDATE_PERIOD_MS);
    static Every telemEvery(TELEM_UPDATE_PERIOD_MS);
    static FlashTimer horizFlashTimer(HORIZ_FLASH_MS);
    static uint32_t dropCount = 0;

    // 1. Handle serial commands (e.g., MAC address)
    handleSerialCommands();

    // 2. Process control inputs (joysticks, switches)
    const ControlInputs &inputs = m_control->readInputs();

    // 3. Apply safety logic (arming, horizon, telemetry)
    // Get enhanced telemetry for safety checks
    const EnhancedTelemData &etelem = m_radio->getEnhancedTelemetry();

    // --- Horizon safety from STATUS packet ---
    // In enhanced telemetry, safety_flags contains horizon bit (bit 0) and calibration bits (bits 3-5)
    g_horizonOK = (etelem.status.safety_flags & TELEM_HORIZON_BIT) != 0;
    g_telemArmed = (etelem.status.armed & TELEM_ARMED_BIT) != 0;
    g_calOK = (etelem.status.safety_flags & TELEM_FLAG_CAL_OK) != 0;
    g_calibrating = (etelem.status.safety_flags & TELEM_FLAG_CALIBRATING) != 0;
    g_calFailed = (etelem.status.safety_flags & TELEM_FLAG_CAL_FAILED) != 0;
    // --- Force disarm detection ---
    bool isArmed = g_telemArmed;
    bool forceDisarm = (etelem.status.safety_flags & TELEM_FORCE_DISARM) != 0;

    // Detect disarm transition with force disarm flag
    if (m_lastArmedState && !isArmed && forceDisarm)
    {
        g_forceDisarmActive = true;
        g_forceDisarmTimestamp = millis();
        LOG_WARN(SYSTEM, "Force disarm event detected!");
    }

    m_lastArmedState = isArmed;

    // --- Horizon flash logic ---
    if (!g_horizonOK || !g_telemArmed || Age::since(g_lastTelemUpdateMs) > TELEM_TIMEOUT_MS)
    {
        if (!g_showHorizFlash)
        {
            g_showHorizFlash = true;
            g_horizFlashStartMs = millis();
            horizFlashTimer.start();
        }
    }
    else
    {
        g_showHorizFlash = false;
        horizFlashTimer.stop();
    }
    if (g_showHorizFlash && horizFlashTimer.isActive())
    {
        g_showHorizFlash = false;
    }

    // --- Arm pulse logic ---
    if (inputs.armed && !g_lastInputsArmed)
    {
        g_armPulseCountdown = ARM_PULSE_PACKETS;
    }
    g_lastInputsArmed = inputs.armed;

    // 4. Build and send RC packet (50Hz)
    if (rcEvery.check())
    {
        RcPacket packet = {};
        buildRcPacket(inputs, packet);
        if (g_armPulseCountdown > 0)
        {
            packet.flags |= RC_FLAG_ARMED;
            g_armPulseCountdown--;
        }
        bool sent = m_radio->sendPacket(&packet, sizeof(packet));

        // Debug: Log occasional packet status (every 50 packets = 1 second)
        static uint8_t debugCounter = 0;
        static uint32_t lastSuccessCount = 0;
        static uint32_t lastFailCount = 0;

        if (++debugCounter >= 50)
        {
            debugCounter = 0;

            uint32_t currentSuccess = m_radio->getSendSuccessCount();
            uint32_t currentFail = m_radio->getSendFailCount();
            uint32_t newSuccess = currentSuccess - lastSuccessCount;
            uint32_t newFails = currentFail - lastFailCount;

            if (sent)
            {
                if (newFails > 0)
                {
                    LOG_DEBUG(RADIO, "RC: queued seq=%d, %lu ACK, %lu FAIL (last 1s)",
                              packet.seq, newSuccess, newFails);
                }
                else if (newSuccess > 0)
                {
                    LOG_DEBUG(RADIO, "RC: queued seq=%d, %lu ACK (last 1s)",
                              packet.seq, newSuccess);
                }
                else
                {
                    LOG_DEBUG(RADIO, "RC: queued seq=%d, no callbacks yet", packet.seq);
                }
            }
            else
            {
                LOG_ERROR(RADIO, "Failed to queue RC packet");
            }

            lastSuccessCount = currentSuccess;
            lastFailCount = currentFail;
        }
    }

    // 5. Process telemetry (10Hz)
    if (telemEvery.check())
    {
        // Check for enhanced telemetry
        if (m_radio->hasNewEnhancedTelemetry())
        {
            m_radio->clearNewEnhancedFlag();
            g_lastTelemUpdateMs = millis();
            g_telemFrequency = 20.0f; // Enhanced ATTITUDE packets at 20Hz
            dropCount = 0;

            // Log enhanced telemetry data
            const EnhancedTelemData &etelem = m_radio->getEnhancedTelemetry();

            // ATTITUDE packet (20Hz from drone)
            if (etelem.attitude_rx_ms > 0)
            {
                float roll = etelem.attitude.roll_deg_x100 / 100.0f;
                float pitch = etelem.attitude.pitch_deg_x100 / 100.0f;
                float yaw = etelem.attitude.yaw_deg_x100 / 100.0f;
                LOG_DEBUG(TELEM, "ATT: R=%.2f P=%.2f Y=%.2f seq=%u",
                          roll, pitch, yaw, etelem.attitude.header.seq);
            }

            // CONTROL packet
            if (etelem.control_rx_ms > 0)
            {
                float setRoll = etelem.control.set_roll_deg_x100 / 100.0f;
                float setPitch = etelem.control.set_pitch_deg_x100 / 100.0f;
                float setYawRate = etelem.control.set_yaw_rate_dps_x10 / 10.0f;
                LOG_DEBUG(TELEM, "CTL: setR=%.2f setP=%.2f setYR=%.1f seq=%u",
                          setRoll, setPitch, setYawRate, etelem.control.header.seq);
            }

            // MOTORS packet
            if (etelem.motors_rx_ms > 0)
            {
                LOG_DEBUG(TELEM, "MOT: cmd=[%u %u %u %u] act=[%u %u %u %u] seq=%u THR=%u",
                          etelem.motors.motor_cmd[0], etelem.motors.motor_cmd[1],
                          etelem.motors.motor_cmd[2], etelem.motors.motor_cmd[3],
                          etelem.motors.motor_actual[0], etelem.motors.motor_actual[1],
                          etelem.motors.motor_actual[2], etelem.motors.motor_actual[3],
                          etelem.motors.header.seq, etelem.motors.throttle);
            }

            // STATUS packet
            if (etelem.status_rx_ms > 0)
            {
                bool armed = (etelem.status.armed & TELEM_ARMED_BIT) != 0;
                bool horizOK = (etelem.status.safety_flags & TELEM_HORIZON_BIT) != 0;
                bool calOK = (etelem.status.safety_flags & TELEM_FLAG_CAL_OK) != 0;
                bool calibrating = (etelem.status.safety_flags & TELEM_FLAG_CALIBRATING) != 0;
                bool calFailed = (etelem.status.safety_flags & TELEM_FLAG_CAL_FAILED) != 0;
                bool forceDisarm = (etelem.status.safety_flags & TELEM_FORCE_DISARM) != 0;

                LOG_DEBUG(TELEM, "STA: armed=%d mode=%d link=%d%% uptime=%us seq=%u [ARM:%d HRZ:%d CAL:%d CALIB:%d FAIL:%d FD:%d]",
                          etelem.status.armed, etelem.status.flight_mode,
                          etelem.status.link_quality, etelem.status.uptime_s,
                          etelem.status.header.seq, armed, horizOK, calOK, calibrating, calFailed, forceDisarm);
            }
        }
        else
        {
            dropCount++;
        }
    }

    // 6. Update OLED display (20Hz)
    if (oledEvery.check())
    {
        // OLED_DEMO: Override normal display when demo active
        if (m_oledDemo.isActive())
        {
            m_oledDemo.update(inputs, etelem, dropCount);
        }
        else
        {
            // Normal display logic with debug view support
            if (Age::since(g_lastTelemUpdateMs) > TELEM_TIMEOUT_MS)
            {
                if (inputs.debugView)
                {
                    updateOledNoTelemDebugView(inputs);
                }
                else
                {
                    updateOledNoTelemNormalView(inputs);
                }
            }
            else
            {
                if (inputs.debugView)
                {
                    updateOledDebugView(inputs, etelem, dropCount);
                }
                else
                {
                    updateOledNormalView(inputs, etelem, dropCount);
                }
            }
        }

        display.display(); // Ensure display is updated
        g_lastOledUpdateMs = millis();
    }
}

void App::handleSerialCommands()
{
    // Check for full line commands (logger commands)
    if (Serial.available())
    {
        String line = Serial.readStringUntil('\n');
        if (line.length() > 1)
        { // Multi-character command = logger command
            Logger::processCommand(line);
            return;
        }

        // Single character commands (legacy interface)
        char c = line.charAt(0);
        if (c == 'M' || c == 'm')
        {
            // Get MAC as bytes
            uint8_t ourMac[6];
            WiFi.macAddress(ourMac);
            LOG_INFO(SYSTEM, "Our MAC: %02X:%02X:%02X:%02X:%02X:%02X",
                     ourMac[0], ourMac[1], ourMac[2], ourMac[3], ourMac[4], ourMac[5]);
            LOG_INFO(SYSTEM, "Drone MAC: %02X:%02X:%02X:%02X:%02X:%02X",
                     g_droneMac[0], g_droneMac[1], g_droneMac[2],
                     g_droneMac[3], g_droneMac[4], g_droneMac[5]);
        }
        // OLED_DEMO: Toggle demo mode
        else if (c == 'O' || c == 'o')
        {
            m_oledDemo.toggle();
        }
        // Calibrate stick centers
        else if (c == 'C' || c == 'c')
        {
            LOG_INFO(INPUTS, "Manual calibration triggered - hold sticks neutral!");
            m_control->calibrate();
            LOG_INFO(INPUTS, "Calibration complete");
        }
        // Radio diagnostics
        else if (c == 'D' || c == 'd')
        {
            uint32_t successCount = m_radio->getSendSuccessCount();
            uint32_t failCount = m_radio->getSendFailCount();
            uint32_t totalPackets = m_radio->getTotalEnhancedPackets();
            uint32_t totalDrops = m_radio->getTotalEnhancedDrops();

            Serial.println("[RADIO_STATS]");
            Serial.printf("Send Success: %lu\n", successCount);
            Serial.printf("Send Fail: %lu\n", failCount);

            if (successCount + failCount > 0)
            {
                float successRate = (float)successCount / (successCount + failCount) * 100.0f;
                Serial.printf("Success Rate: %.1f%%\n", successRate);
            }

            Serial.printf("Telemetry Received: %lu packets\n", totalPackets);
            Serial.printf("Telemetry Drops: %lu packets\n", totalDrops);

            if (totalPackets + totalDrops > 0)
            {
                float dropRate = (float)totalDrops / (totalPackets + totalDrops) * 100.0f;
                Serial.printf("Drop Rate: %.2f%%\n", dropRate);
            }

            unsigned long telemAge = Age::since(g_lastTelemUpdateMs);
            Serial.printf("Last Telemetry: %lu ms ago\n", telemAge);
        }
        // Enhanced telemetry diagnostics
        else if (c == 'E' || c == 'e')
        {
            const TelemReceiverConfig &config = m_radio->getReceiverConfig();

            Serial.println("[TELEMETRY_STATS]");
            Serial.printf("Enhanced Mode: %s\n", config.enable_enhanced ? "ON" : "OFF");
            Serial.printf("Packet Type Mask: 0x%02X\n", config.packet_type_mask);
            Serial.printf("Timeout: %u ms\n", config.packet_timeout_ms);
            Serial.println();

            uint32_t totalPkts = m_radio->getTotalEnhancedPackets();
            uint32_t totalDrops = m_radio->getTotalEnhancedDrops();
            Serial.printf("Total Enhanced Packets: %lu\n", totalPkts);
            Serial.printf("Total Enhanced Drops: %lu\n", totalDrops);
            if (totalPkts > 0)
            {
                float lossRate = (float)totalDrops / (totalPkts + totalDrops) * 100.0f;
                Serial.printf("Loss Rate: %.2f%%\n", lossRate);
            }
            Serial.println();

            // Per-packet-type statistics
            const char *typeNames[] = {"ATTITUDE", "CONTROL", "MOTORS", "STATUS", "SENSORS", "SAFETY", "PERFORMANCE"};
            Serial.println("Per-Packet Statistics:");
            for (uint8_t i = 1; i <= 7; i++)
            {
                TelemetryPacketType type = static_cast<TelemetryPacketType>(i);
                const EnhancedTelemStats &stats = m_radio->getEnhancedStats(type);

                if (stats.packets_received > 0)
                {
                    Serial.printf("  %s: RX=%lu, DROP=%lu, CRC_ERR=%lu, SEQ=%u\n",
                                  typeNames[i - 1],
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
            Serial.println();

            // Status flags (decoded from armed and safety_flags bitfields)
            if (m_radio->hasStatus())
            {
                const EnhancedTelemData &etelem = m_radio->getEnhancedTelemetry();
                Serial.println("Status Flags:");
                Serial.printf("  Armed: %s\n", (etelem.status.armed & TELEM_ARMED_BIT) ? "YES" : "NO");
                Serial.printf("  Horizon OK: %s\n", (etelem.status.safety_flags & TELEM_HORIZON_BIT) ? "YES" : "NO");
                Serial.printf("  Calibration OK: %s\n", (etelem.status.safety_flags & TELEM_FLAG_CAL_OK) ? "YES" : "NO");
                Serial.printf("  Calibrating: %s\n", (etelem.status.safety_flags & TELEM_FLAG_CALIBRATING) ? "YES" : "NO");
                Serial.printf("  Cal Failed: %s\n", (etelem.status.safety_flags & TELEM_FLAG_CAL_FAILED) ? "YES" : "NO");
                Serial.printf("  Force Disarm: %s\n", (etelem.status.safety_flags & TELEM_FORCE_DISARM) ? "YES" : "NO");
            }
        }
        // Toggle enhanced telemetry mode
        else if (c == 'T' || c == 't')
        {
            TelemReceiverConfig config = m_radio->getReceiverConfig();
            config.enable_enhanced = !config.enable_enhanced;
            m_radio->setReceiverConfig(config);
            Serial.printf("[CONFIG] Enhanced telemetry: %s\n", config.enable_enhanced ? "ENABLED" : "DISABLED");
        }
    }
}

// OLED_DEMO: Implementation of demo state machine
void OledDemo::toggle()
{
    if (m_state == OledDemoState::OFF)
    {
        m_state = OledDemoState::NO_TELEM_NORMAL;
        m_stateStartMs = millis();
        Serial.println("[OLED_DEMO] Started - cycling through 10 views (2s each)");
    }
    else
    {
        m_state = OledDemoState::OFF;
        Serial.println("[OLED_DEMO] Stopped");
    }
}

void OledDemo::update(const ControlInputs &inputs, const EnhancedTelemData &telem, uint32_t dropCount)
{
    // Safety check - stop demo if unsafe conditions
    if (shouldStop(inputs, telem))
    {
        m_state = OledDemoState::OFF;
        Serial.println("[OLED_DEMO] Auto-stopped for safety");
        return;
    }

    // Check if it's time to advance to next state
    if (millis() - m_stateStartMs >= STATE_DURATION_MS)
    {
        advance();
    }

    // Render current state
    renderCurrentState(inputs, telem, dropCount);
}

void OledDemo::advance()
{
    switch (m_state)
    {
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
        m_state = OledDemoState::CALIBRATING;
        Serial.println("[OLED_DEMO] -> Calibrating");
        break;
    case OledDemoState::CALIBRATING:
        m_state = OledDemoState::CAL_FAILED;
        Serial.println("[OLED_DEMO] -> Calibration Failed");
        break;
    case OledDemoState::CAL_FAILED:
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

void OledDemo::renderCurrentState(const ControlInputs &inputs, const EnhancedTelemData &telem, uint32_t dropCount)
{
    ControlInputs mockInputs;
    EnhancedTelemData mockTelem;
    uint32_t mockDropCount = 0;

    // Set global state variables to simulate different conditions
    extern bool g_showHorizFlash;
    extern bool g_horizonOK;
    extern bool g_telemArmed;
    extern bool g_calibrating;
    extern bool g_calFailed;
    extern unsigned long g_lastTelemUpdateMs;
    extern float g_telemFrequency;

    // Save original states
    bool origHorizFlash = g_showHorizFlash;
    bool origHorizonOK = g_horizonOK;
    bool origTelemArmed = g_telemArmed;
    bool origCalibrating = g_calibrating;
    bool origCalFailed = g_calFailed;
    unsigned long origLastTelem = g_lastTelemUpdateMs;
    float origTelemFreq = g_telemFrequency;

    switch (m_state)
    {
    case OledDemoState::NO_TELEM_NORMAL:
        createMockInputs(mockInputs, false);
        g_showHorizFlash = false;
        g_lastTelemUpdateMs = millis() - (TELEM_TIMEOUT_MS + 1000);
        updateOledNoTelemNormalView(mockInputs);
        break;

    case OledDemoState::NO_TELEM_FLASH:
        createMockInputs(mockInputs, false);
        g_showHorizFlash = true;
        g_horizonOK = false;
        g_lastTelemUpdateMs = millis() - (TELEM_TIMEOUT_MS + 1000);
        updateOledNoTelemNormalView(mockInputs);
        break;

    case OledDemoState::NO_TELEM_DEBUG:
        createMockInputs(mockInputs, true);
        g_showHorizFlash = false;
        g_lastTelemUpdateMs = millis() - (TELEM_TIMEOUT_MS + 1000);
        updateOledNoTelemDebugView(mockInputs);
        break;

    case OledDemoState::NORMAL_VIEW:
        createMockInputs(mockInputs, false);
        createMockTelemetry(mockTelem);
        g_showHorizFlash = false;
        g_horizonOK = true;
        g_telemArmed = false;
        g_lastTelemUpdateMs = millis();
        g_telemFrequency = 9.8f;
        updateOledNormalView(mockInputs, mockTelem, mockDropCount);
        break;

    case OledDemoState::NORMAL_FLASH:
        createMockInputs(mockInputs, false);
        createMockTelemetry(mockTelem);
        g_showHorizFlash = true;
        g_horizonOK = false;
        g_lastTelemUpdateMs = millis();
        updateOledNormalView(mockInputs, mockTelem, mockDropCount);
        break;

    case OledDemoState::NORMAL_STATUS:
        createMockInputs(mockInputs, false);
        createMockTelemetry(mockTelem);
        g_showHorizFlash = false;
        g_horizonOK = false;
        g_telemArmed = false;
        g_lastTelemUpdateMs = millis();
        g_telemFrequency = 10.1f;
        updateOledNormalView(mockInputs, mockTelem, mockDropCount);
        break;

    case OledDemoState::CALIBRATING:
        createMockInputs(mockInputs, false);
        createMockTelemetry(mockTelem);
        g_showHorizFlash = false;
        g_horizonOK = true;
        g_telemArmed = false;
        g_calibrating = true;
        g_calFailed = false;
        g_lastTelemUpdateMs = millis();
        updateOledNormalView(mockInputs, mockTelem, mockDropCount);
        break;

    case OledDemoState::CAL_FAILED:
        createMockInputs(mockInputs, false);
        createMockTelemetry(mockTelem);
        g_showHorizFlash = false;
        g_horizonOK = true;
        g_telemArmed = false;
        g_calibrating = false;
        g_calFailed = true;
        g_lastTelemUpdateMs = millis();
        updateOledNormalView(mockInputs, mockTelem, mockDropCount);
        break;

    case OledDemoState::DEBUG_VIEW:
        createMockInputs(mockInputs, true);
        createMockTelemetry(mockTelem);
        g_showHorizFlash = false;
        g_lastTelemUpdateMs = millis();
        updateOledDebugView(mockInputs, mockTelem, mockDropCount);
        break;

    case OledDemoState::DEBUG_DROPS:
        createMockInputs(mockInputs, true);
        createMockTelemetry(mockTelem);
        g_showHorizFlash = false;
        g_lastTelemUpdateMs = millis();
        mockDropCount = DROP_INDICATOR_COUNT;
        updateOledDebugView(mockInputs, mockTelem, mockDropCount);
        break;

    default:
        break;
    }

    // Restore original states
    g_showHorizFlash = origHorizFlash;
    g_horizonOK = origHorizonOK;
    g_telemArmed = origTelemArmed;
    g_calibrating = origCalibrating;
    g_calFailed = origCalFailed;
    g_lastTelemUpdateMs = origLastTelem;
    g_telemFrequency = origTelemFreq;
}

bool OledDemo::shouldStop(const ControlInputs &inputs, const EnhancedTelemData &telem)
{
    // Stop demo if unsafe conditions detected
    return inputs.armed ||          // User trying to arm
           inputs.throttle > 50 ||  // Throttle not at zero
           telem.status.armed != 0; // Drone reports armed
}

void OledDemo::createMockInputs(ControlInputs &mockInputs, bool debugView)
{
    // OLED_DEMO: Safe, representative mock control inputs
    mockInputs.throttle = 0;          // Always safe for demo
    mockInputs.yaw = -150;            // Realistic stick input
    mockInputs.pitch = 200;           // Realistic stick input
    mockInputs.roll = -75;            // Realistic stick input
    mockInputs.armed = false;         // Always false for safety
    mockInputs.debugView = debugView; // Controlled by demo state
}

void OledDemo::createMockTelemetry(EnhancedTelemData &mockTelem)
{
    // OLED_DEMO: Realistic enhanced telemetry data for demo
    memset(&mockTelem, 0, sizeof(mockTelem));

    // ATTITUDE packet
    mockTelem.attitude.roll_deg_x100 = -520;     // -5.2 degrees
    mockTelem.attitude.pitch_deg_x100 = 310;     // 3.1 degrees
    mockTelem.attitude.yaw_deg_x100 = 4500;      // 45 degrees
    mockTelem.attitude.roll_rate_dps_x10 = -480; // -48 deg/s
    mockTelem.attitude.pitch_rate_dps_x10 = 350; // 35 deg/s
    mockTelem.attitude.yaw_rate_dps_x10 = -450;  // -45 deg/s
    mockTelem.attitude_rx_ms = millis();

    // CONTROL packet
    mockTelem.control.set_roll_deg_x100 = -500;    // -5.0 degrees setpoint
    mockTelem.control.set_pitch_deg_x100 = 300;    // 3.0 degrees setpoint
    mockTelem.control.set_yaw_rate_dps_x10 = -400; // -40 deg/s setpoint
    mockTelem.control.out_roll_x10 = 1850;         // PID output
    mockTelem.control.out_pitch_x10 = 1920;        // PID output
    mockTelem.control.out_yaw_x10 = 1480;          // PID output
    mockTelem.control_rx_ms = millis();

    // MOTORS packet
    mockTelem.motors.throttle = 250; // Base throttle
    mockTelem.motors.motor_cmd[0] = 300;
    mockTelem.motors.motor_cmd[1] = 280;
    mockTelem.motors.motor_cmd[2] = 270;
    mockTelem.motors.motor_cmd[3] = 290;
    mockTelem.motors_rx_ms = millis();

    // STATUS packet
    mockTelem.status.armed = 0;                             // Not armed
    mockTelem.status.flight_mode = 1;                       // Stabilize mode
    mockTelem.status.safety_flags = TELEM_HORIZON_BIT;      // Horizon OK
    mockTelem.status.link_quality = 95;                     // 95% link quality
    mockTelem.status_rx_ms = millis();
}
