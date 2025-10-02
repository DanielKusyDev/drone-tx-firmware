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
     * @brief Process serial commands (e.g., 'M' for MAC address)
     */
    void handleSerialCommands();

private:
    // Subsystem instances (maintain global access pattern for now)
    ControlManager* m_control;
    RadioManager* m_radio;
    
    // Timing state (preserve existing timing behavior)
    unsigned long m_lastOledUpdateMs;
};

// Global app instance (maintains Arduino-style global access)
extern App g_app;