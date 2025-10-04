#pragma once

/**
 * @file App.h
 * @brief Main application orchestration layer
 * 
 * Coordinates control input, radio communication, safety systems,
 * and display updates at correct cadences (50Hz RC, 20Hz OLED, 10Hz telemetry).
 * Maintains all existing behavior while providing cleaner separation.
 */

#include <Arduino.h>
#include "control.h"
#include "radio.h"
#include "protocol.h"

// OLED_DEMO: Demo state machine for cycling through all UI views
enum class OledDemoState {
    OFF,
    NO_TELEM_NORMAL,
    NO_TELEM_FLASH,
    NO_TELEM_DEBUG,
    NORMAL_VIEW,
    NORMAL_FLASH,
    NORMAL_STATUS,
    DEBUG_VIEW,
    DEBUG_DROPS
};

class OledDemo {
public:
    void toggle();
    void update(const ControlInputs& inputs, const TelemetryPacket& lastTelem, uint32_t dropCount);
    bool isActive() const { return m_state != OledDemoState::OFF; }
    
private:
    OledDemoState m_state = OledDemoState::OFF;
    unsigned long m_stateStartMs = 0;
    static const unsigned long STATE_DURATION_MS = 2000;
    
    void advance();
    void renderCurrentState(const ControlInputs& inputs, const TelemetryPacket& lastTelem, uint32_t dropCount);
    bool shouldStop(const ControlInputs& inputs, const TelemetryPacket& lastTelem);
    void createMockInputs(ControlInputs& mockInputs, bool debugView);
    void createMockTelemetry(TelemetryPacket& mockTelem);
};

class App {
public:
    /**
     * @brief Initialize application subsystems
     * @return true if initialization successful
     */
    bool init();

    /**
     * @brief Main application loop - maintains 50Hz RC transmission
     * Should be called from Arduino loop() function
     */
    void loop();

    /**
     * @brief Process serial commands
     *
     * Available commands:
     * - 'M': Display MAC addresses (transmitter and drone)
     * - 'O': Toggle OLED demo mode (cycles through all UI views)
     * - 'D': Display radio diagnostics (legacy telemetry)
     * - 'E': Display enhanced telemetry statistics and per-packet details
     * - 'T': Toggle enhanced telemetry mode on/off
     */
    void handleSerialCommands();

private:
    // Subsystem instances (maintain global access pattern for now)
    ControlManager* m_control;
    RadioManager* m_radio;
    
    // OLED_DEMO: Demo state machine instance
    OledDemo m_oledDemo;
    
    // Timing state (preserve existing timing behavior)
    unsigned long m_lastOledUpdateMs;
};

// Global app instance (maintains Arduino-style global access)
extern App g_app;