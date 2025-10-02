#include <Arduino.h>
#include "config.h"
#include "protocol.h"
#include "radio.h"
#include "control.h"
#include "app/App.h"
#include "utils/Timing.h"
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>
#include <cstdarg>  // For va_list in logging functions

// Global instances
RadioManager radio;
ControlManager control;

// Global OLED display (matching original code structure)
Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);

// Packet state
volatile uint16_t g_sequenceNumber = 0;

// Drone MAC address
uint8_t g_droneMac[6] = DEFAULT_DRONE_MAC;

// TELEM: Telemetry state
unsigned long g_lastTelemUpdateMs = 0;
unsigned long g_lastOledUpdateMs = 0;
float g_telemFrequency = 0.0f;

// HORIZ: Horizon safety globals
bool g_telemArmed = false;
bool g_horizonOK = false;
unsigned long g_horizFlashStartMs = 0;
bool g_showHorizFlash = false;

// ARM: Arm pulse countdown (avoid multiple arm toggles)
#define ARM_PULSE_PACKETS 3  // Send ARM flag for this many packets (~60ms at 50Hz)
uint8_t g_armPulseCountdown = 0;
bool g_lastInputsArmed = false;

// LOG: Logging system configuration
struct LogConfig {
    bool enableSetup = true;           // Setup and initialization messages
    bool enableTelemetry = true;       // Telemetry data output 
    bool enableMacAddress = true;      // MAC address commands ('M')
    bool enableErrors = true;          // Error and warning messages
    bool enableDebug = true;           // Debug/diagnostic messages
};

LogConfig g_logConfig;

// LOG: Modular logging functions with category-based filtering
namespace Logger {
    /**
     * @brief Log setup and initialization messages
     * @param message Message to log (supports multiple parameters like Serial.print)
     */
    void setup(const char* message) {
        if (g_logConfig.enableSetup) {
            Serial.print("[SETUP] ");
            Serial.println(message);
        }
    }
    
    /**
     * @brief Log telemetry data in structured format
     * @param ms Timestamp
     * @param inputs Control inputs from transmitter
     * @param telem Telemetry packet from drone
     */
    void telemetry(unsigned long ms, const ControlInputs& inputs, const TelemetryPacket& telem) {
        if (!g_logConfig.enableTelemetry) return;
        
        // Structured telemetry format: TX[time,armed,throttle] | DRONE[...] | ATT[...] | MOTORS[...] | PID[...] | STATUS[...]
        Serial.print("TX[");
        Serial.print(ms); Serial.print(",");
        Serial.print(inputs.armed ? 1 : 0); Serial.print(",");
        Serial.print(inputs.throttle); Serial.print("] | ");
        
        Serial.print("DRONE[");
        Serial.print(telem.ms); Serial.print(",");
        Serial.print(telem.armed); Serial.print(",");
        Serial.print(telem.thr); Serial.print("] | ");
        
        Serial.print("ATT[R:");
        Serial.print(telem.roll_deg_x10 / 10.0f, 1); Serial.print(",P:");
        Serial.print(telem.pitch_deg_x10 / 10.0f, 1); Serial.print(",YR:");
        Serial.print(telem.yawRate_dps); Serial.print("] | ");
        
        Serial.print("MOTORS[");
        Serial.print(telem.m1); Serial.print(",");
        Serial.print(telem.m2); Serial.print(",");
        Serial.print(telem.m3); Serial.print(",");
        Serial.print(telem.m4); Serial.print("] | ");
        
        Serial.print("PID[R:");
        Serial.print(telem.outRoll); Serial.print(",P:");
        Serial.print(telem.outPitch); Serial.print(",Y:");
        Serial.print(telem.outYaw); Serial.print("] | ");
        
        // HORIZ: Add derived status columns
        Serial.print("STATUS[horizOK:");
        Serial.print(g_horizonOK ? 1 : 0); Serial.print(",armedDRN:");
        Serial.print(g_telemArmed ? 1 : 0); Serial.print("]");
        
        Serial.println();
    }
    
    /**
     * @brief Log MAC address information
     * @param label Descriptive label (e.g., "Our MAC", "Drone MAC")
     * @param mac 6-byte MAC address array
     */
    void macAddress(const char* label, const uint8_t* mac) {
        if (!g_logConfig.enableMacAddress) return;
        
        Serial.print("[MAC] ");
        Serial.print(label);
        Serial.print(": ");
        for (int i = 0; i < 6; i++) {
            Serial.printf("%02X", mac[i]);
            if (i < 5) Serial.print(":");
        }
        Serial.println();
    }
    
    /**
     * @brief Log error and warning messages
     * @param category Error category (e.g., "INIT", "RADIO", "CONTROL")
     * @param message Error description
     */
    void error(const char* category, const char* message) {
        if (!g_logConfig.enableErrors) return;
        
        Serial.print("[ERROR:");
        Serial.print(category);
        Serial.print("] ");
        Serial.println(message);
    }
    
    /**
     * @brief Log debug and diagnostic information
     * @param category Debug category
     * @param message Debug message
     */
    void debug(const char* category, const char* message) {
        if (!g_logConfig.enableDebug) return;
        
        Serial.print("[DEBUG:");
        Serial.print(category);
        Serial.print("] ");
        Serial.println(message);
    }
    
    /**
     * @brief Log debug information with formatted values
     * @param category Debug category
     * @param format printf-style format string
     * @param ... Variable arguments for formatting
     */
    void debugf(const char* category, const char* format, ...) {
        if (!g_logConfig.enableDebug) return;
        
        Serial.print("[DEBUG:");
        Serial.print(category);
        Serial.print("] ");
        
        va_list args;
        va_start(args, format);
        char buffer[128];
        vsnprintf(buffer, sizeof(buffer), format, args);
        va_end(args);
        
        Serial.println(buffer);
    }
    
    /**
     * @brief Log radio-specific error messages with structured format
     */
    void radioError(const char* operation, const char* details) {
        if (!g_logConfig.enableErrors) return;
        
        Serial.print("[ERROR:RADIO:");
        Serial.print(operation);
        Serial.print("] ");
        Serial.println(details);
    }
    
    void radioWrongPacketSize(int actualLen, int expectedLen) {
        if (!g_logConfig.enableErrors) return;
        
        Serial.print("[ERROR:RADIO:SIZE] Len: ");
        Serial.print(actualLen);
        Serial.print(" Expected: ");
        Serial.println(expectedLen);
    }
    
    void radioWrongMagicVersion(uint8_t magic, uint8_t version) {
        if (!g_logConfig.enableErrors) return;
        
        Serial.print("[ERROR:RADIO:PROTOCOL] Magic: 0x");
        Serial.print(magic, HEX);
        Serial.print(" Ver: ");
        Serial.println(version);
    }
    
    void radioCrcError(uint16_t calculated, uint16_t received) {
        if (!g_logConfig.enableErrors) return;
        
        Serial.print("[ERROR:RADIO:CRC] Calc: 0x");
        Serial.print(calculated, HEX);
        Serial.print(" Got: 0x");
        Serial.println(received, HEX);
    }
}


void setup() {
    g_app.init();
}

void loop() {
    g_app.loop();
}