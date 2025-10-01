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
    bool enableDebug = false;          // Debug/diagnostic messages
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
}

// TELEM: Helper functions for OLED display
void updateOledNoTelemNormalView(const ControlInputs& inputs) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    
    display.setCursor(0, 0);
    if (g_showHorizFlash) {
        // Show more informative warning based on what's preventing arming
        unsigned long telemAge = Age::since(g_lastTelemUpdateMs);
        if (telemAge > TELEM_TIMEOUT_MS) {
            display.print("LINK LOST!  THR:");
        } else {
            display.print("LEVEL!      THR:");
        }
        display.print(inputs.throttle);
    } else {
        display.print("TX: ");
        display.print(inputs.armed ? "ARM" : "---");
        display.print(" CH:");
        display.print(ESPNOW_CHANNEL);
        
        // HORIZ: Show LINK? only when telemetry is truly stale
        unsigned long telemAge = Age::since(g_lastTelemUpdateMs);
        if (telemAge > TELEM_TIMEOUT_MS) {
            display.setCursor(90, 0);
            display.print("LINK?");
        }
        
        display.setCursor(0, 10);
        display.print("THR: ");
        display.print(inputs.throttle);
    }
    
    // Show second and third line only when not flashing
    if (!g_showHorizFlash) {
        display.setCursor(0, 20);
        display.print("Y:");
        display.print((int)inputs.yaw);
        display.print(" P:");
        display.print((int)inputs.pitch);
        display.print(" R:");
        display.print((int)inputs.roll);
    }
}

void updateOledNoTelemDebugView(const ControlInputs& inputs) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    
    // Debug view without telemetry - show more technical info
    display.setCursor(0, 0);
    if (g_showHorizFlash) {
        // Show more informative warning in debug view too
        unsigned long telemAge = Age::since(g_lastTelemUpdateMs);
        if (telemAge > TELEM_TIMEOUT_MS) {
            display.print("LINK LOST!");
        } else {
            display.print("HORIZON UNSAFE!");
        }
    } else {
        display.print("DEBUG (no telem)");
    }
    display.setCursor(0, 10);
    display.print("ARM:");
    display.print(inputs.armed ? "ON" : "OFF");
    display.print(" T:");
    display.print(inputs.throttle);
    display.setCursor(0, 20);
    display.print("Y:");
    display.print((int)inputs.yaw);
    display.print(" P:");
    display.print((int)inputs.pitch);
    display.print(" R:");
    display.print((int)inputs.roll);
}

void updateOledNormalView(const ControlInputs& inputs, const TelemetryPacket& telem, uint32_t dropCount) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    
    // Line 1: ARM and THR with flash override
    display.setCursor(0, 0);
    if (g_showHorizFlash) {
        // Show more informative warning based on what's preventing arming
        unsigned long telemAge = Age::since(g_lastTelemUpdateMs);
        if (telemAge > TELEM_TIMEOUT_MS) {
            display.print("LINK LOST!  THR:");
        } else if (!g_horizonOK) {
            display.print("LEVEL!      THR:");
        } else if (inputs.throttle > 0) {
            display.print("THR=0 TO ARM THR:");
        } else {
            display.print("WAIT...     THR:");
        }
    } else {
        display.print("ARM: ");
        display.print(inputs.armed ? "ON" : "OFF");
        display.print(" THR:");
    }
    display.print(inputs.throttle);
    
    // HORIZ: Top-right status indicators (only when not flashing)
    if (!g_showHorizFlash) {
        unsigned long telemAge = Age::since(g_lastTelemUpdateMs);
        if (telemAge > TELEM_TIMEOUT_MS) {
            // Stale telemetry
            display.setCursor(90, 0);
            display.print("LINK?");
        } else if (!g_horizonOK && !g_telemArmed) {
            // Horizon not OK
            display.setCursor(84, 0);
            display.print("HORIZ?");
        }
    }
    
    // Line 2: Roll and Pitch angles
    display.setCursor(0, 10);
    display.print("R: ");
    display.print(telem.roll_deg_x10 / 10.0f, 1);
    display.print(" P: ");
    display.print(telem.pitch_deg_x10 / 10.0f, 1);
    
    // Line 3: Yaw rate and telemetry frequency
    display.setCursor(0, 20);
    display.print("YR: ");
    display.print((int)telem.yawRate_dps);
    display.print(" FPS: ");
    display.print((int)g_telemFrequency);
    
    // Show expected telemetry rate (small)
    display.setCursor(105, 20);
    display.print("/");
    display.print(TELEMETRY_RATE_HZ);
    
    // Drop indicator (small dot every 5 drops)
    if (dropCount >= DROP_INDICATOR_COUNT) {
        display.fillCircle(120, 2, 1, SSD1306_WHITE);
    }
    
    display.display();
}

void updateOledDebugView(const ControlInputs& inputs, const TelemetryPacket& telem, uint32_t dropCount) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    
    // Line 1: Setpoints
    display.setCursor(0, 0);
    display.print("setR: ");
    display.print(telem.setAngleRoll_x10 / 10.0f, 1);
    display.print(" setP: ");
    display.print(telem.setAnglePitch_x10 / 10.0f, 1);
    
    // Line 2: Rate values
    display.setCursor(0, 10);
    display.print("rateR:");
    display.print((int)telem.rollRate_dps);
    display.print(" rateP:");
    display.print((int)telem.pitchRate_dps);
    
    // Line 3: Outputs
    display.setCursor(0, 20);
    display.print("outR:");
    display.print(telem.outRoll);
    display.print(" outP:");
    display.print(telem.outPitch);
    display.print(" Y:");
    display.print(telem.outYaw);
    
    // Drop indicator (small dot every 5 drops)
    if (dropCount >= DROP_INDICATOR_COUNT) {
        display.fillCircle(120, 2, 1, SSD1306_WHITE);
    }
    
    display.display();
}

// DEPRECATED: Old CSV logging function - replaced by Logger::telemetry()
// Kept for compatibility during transition
void printCsvLine(unsigned long ms, const ControlInputs& inputs, const TelemetryPacket& telem) {
    Logger::telemetry(ms, inputs, telem);
}

void setup() {
    Serial.begin(115200);
    delay(1000);  // Stabilization delay
    
    Logger::setup("=== RC Transmitter Starting ===");
    Logger::setup("Serial init OK");
    
    // Initialize I2C for OLED
    Wire.begin(OLED_SDA, OLED_SCL);
    Logger::setup("I2C init OK");
    
    // Initialize OLED display
    if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
        Logger::error("INIT", "OLED init failed!");
        while (1) delay(1000);
    }
    Logger::setup("OLED init OK");
    display.clearDisplay();
    display.display();
    
    // Initialize control system
    if (!control.init()) {
        Logger::error("INIT", "Control init failed!");
        while (1) delay(1000);
    }
    Logger::setup("Control init OK");
    
    // Initialize radio
    if (!radio.init(ESPNOW_CHANNEL)) {
        Logger::error("RADIO", "ESP-NOW init failed");
    } else {
        Logger::setup("ESP-NOW init OK");
    }
    
    // Set peer MAC address
    if (!radio.setPeerMac(g_droneMac)) {
        Logger::error("RADIO", "Peer setup failed!");
    } else {
        Logger::setup("Peer MAC set OK");
    }
    
    delay(500);
    
    // Perform calibration
    Logger::setup("Starting calibration...");
    control.calibrate();
    Logger::setup("Calibration complete");
    
    Logger::setup("RC Transmitter Ready!");
    Logger::setup("Waiting for telemetry from drone...");
    
    // Print MAC addresses for debugging
    uint8_t mac[6];
    WiFi.macAddress(mac);
    Logger::macAddress("Our MAC", mac);
    Logger::macAddress("Drone MAC", g_droneMac);
    
    Logger::setup("Transmitter ready!");
    
    // Log telemetry configuration
    Serial.print("[CONFIG] Packet rate: ");
    Serial.print(PACKET_RATE_HZ);
    Serial.print(" Hz, Telemetry rate: ");
    Serial.print(TELEMETRY_RATE_HZ);
    Serial.print(" Hz, Timeout: ");
    Serial.print(TELEM_TIMEOUT_MS);
    Serial.println(" ms");
}

void loop() {
    unsigned long currentTime = millis();
    
    // Check for serial commands
    if (Serial.available()) {
        char cmd = Serial.read();
        if (cmd == 'M' || cmd == 'm') {
            // Print MAC address
            uint8_t mac[6];
            WiFi.macAddress(mac);
            Logger::debugf("MAC", "Transmitter MAC: %02X:%02X:%02X:%02X:%02X:%02X", 
                          mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
        }
        // Clear remaining characters
        while (Serial.available()) {
            Serial.read();
        }
    }
    
    // Read control inputs with button handling
    ControlInputs inputs = control.readInputs();
    
    // Debug: Track ARM state changes
    static bool prevArmedState = false;
    if (inputs.armed != prevArmedState) {
        Serial.print("[ARM_STATE] Changed to: ");
        Serial.println(inputs.armed ? "ARMED" : "DISARMED");
        prevArmedState = inputs.armed;
    }
    
    // HORIZ: Apply horizon safety - prevent arming if horizon not OK or telemetry stale
    bool effectiveArmed = inputs.armed;
    unsigned long telemAge = Age::since(g_lastTelemUpdateMs);
    bool horizonSafe = g_horizonOK && (telemAge <= TELEM_TIMEOUT_MS);
    
    // HORIZ: If user tried to arm but horizon not safe, show appropriate flash message
    if (inputs.armed && !g_showHorizFlash) {
        if (!horizonSafe) {
            g_showHorizFlash = true;
            g_horizFlashStartMs = currentTime;
            effectiveArmed = false; // Don't actually arm
            
            // Add more detailed logging about WHY arming was prevented
            if (!g_horizonOK) {
                Serial.println("[SAFETY] Arming prevented: horizon not level");
            } else if (telemAge > TELEM_TIMEOUT_MS) {
                Serial.println("[SAFETY] Arming prevented: telemetry stale");
            }
        }
    }
    
    // Keep disarmed if horizon not safe
    if (!horizonSafe) {
        effectiveArmed = false;
    }
    
    // HORIZ: Safety check - never arm with throttle > 0
    if (inputs.throttle > 0) {
        effectiveArmed = false;
    }
    
    // Debug: Track effective ARM state changes
    static bool prevEffectiveArmed = false;
    if (effectiveArmed != prevEffectiveArmed) {
        Serial.print("[EFFECTIVE_ARM] Changed to: ");
        Serial.print(effectiveArmed ? "ARMED" : "DISARMED");
        Serial.print(" (inputs.armed=");
        Serial.print(inputs.armed ? "true" : "false");
        Serial.print(", horizonSafe=");
        Serial.print(horizonSafe ? "true" : "false");
        Serial.print(", throttle=");
        Serial.print(inputs.throttle);
        Serial.println(")");
        prevEffectiveArmed = effectiveArmed;
    }
    
    // ARM PULSE: Check for rising edge of inputs.armed (user pressed ARM button)
    if (inputs.armed && !g_lastInputsArmed) {
        g_armPulseCountdown = ARM_PULSE_PACKETS; // Start ARM pulse
        Serial.println("[ARM_PULSE] Starting ARM pulse");
    }
    g_lastInputsArmed = inputs.armed;
    
    // ARM PULSE: Manage countdown
    bool sendArmFlag = false;
    if (g_armPulseCountdown > 0) {
        g_armPulseCountdown--;
        sendArmFlag = effectiveArmed; // Only send if also effectively armed
        
        if (g_armPulseCountdown == 0) {
            Serial.println("[ARM_PULSE] ARM pulse complete");
        }
    }
    
    // Build and send packet (maintain 50Hz)
    RcPacket packet = {};
    packet.magic = RC_PACKET_MAGIC;
    packet.version = RC_PACKET_VERSION;
    packet.seq = ++g_sequenceNumber;
    packet.thr = inputs.throttle;
    packet.yaw = inputs.yaw;
    packet.pitch = inputs.pitch;
    packet.roll = inputs.roll;
    
    // ARM PULSE: Set ARM flag only during pulse or first packet when arming
    packet.flags = 0;
    if (sendArmFlag) {
        packet.flags |= RC_FLAG_ARMED;  // Set ARM flag only during pulse
    }
    
    if (inputs.debugView) packet.flags |= RC_FLAG_DEBUG;
    packet.rssi_hint = 0;
    
    // Calculate CRC (on all fields except CRC itself)
    packet.crc = crc16_x25(reinterpret_cast<const uint8_t*>(&packet), 
                          sizeof(packet) - sizeof(packet.crc));
    
    // Send packet
    radio.sendPacket(&packet, sizeof(packet));
    
    // --- OLED Flicker Fix: Buffer last telemetry and only show 'no telemetry' after timeout ---
    static TelemetryPacket lastTelemetry = {};
    static uint32_t lastDropCount = 0;
    static bool lastTelemetryValid = false;
    static unsigned long lastTelemetryMs = 0;

    if (radio.hasNewTelemetry()) {
        lastTelemetry = radio.getLastTelemetry();
        lastDropCount = radio.getDropCount();
        radio.clearNewTelemetryFlag();
        lastTelemetryValid = true;
        lastTelemetryMs = millis();

        // HORIZ: Parse armed bitfield from telemetry
        g_telemArmed = (lastTelemetry.armed & 0x01) != 0;
        g_horizonOK = (lastTelemetry.armed & 0x02) != 0;

        unsigned long telemUpdateMs = lastTelemetryMs;

        // Calculate telemetry frequency
        if (g_lastTelemUpdateMs != 0) {
            float deltaS = (telemUpdateMs - g_lastTelemUpdateMs) / 1000.0f;
            if (deltaS > 0.001f) {
                g_telemFrequency = 0.9f * g_telemFrequency + 0.1f * (1.0f / deltaS);
            }
        }
        g_lastTelemUpdateMs = telemUpdateMs;

        // Print formatted telemetry line
        printCsvLine(currentTime, inputs, lastTelemetry);
    }

    // OLED display update - limit to ~20Hz to prevent flickering
    static Every oledUpdate(50); // 20Hz update rate
    if (oledUpdate.check()) {
        // HORIZ: Check for flash message timeout ONCE per OLED update cycle
        static FlashTimer horizFlash(700); // 700ms flash duration
        if (g_showHorizFlash) {
            horizFlash.start();
            g_showHorizFlash = false; // Consume the trigger
        }
        // FlashTimer automatically manages the flash state

        // Show telemetry view as long as last telemetry is not stale
        bool telemetryFresh = lastTelemetryValid && (Age::since(lastTelemetryMs) <= TELEM_TIMEOUT_MS);
        if (telemetryFresh) {
            if (inputs.debugView) {
                updateOledDebugView(inputs, lastTelemetry, lastDropCount);
            } else {
                updateOledNormalView(inputs, lastTelemetry, lastDropCount);
            }
        } else {
            // No telemetry - show basic TX status but respect debugView
            if (inputs.debugView) {
                updateOledNoTelemDebugView(inputs);
            } else {
                updateOledNoTelemNormalView(inputs);
            }
        }

        display.display();
        g_lastOledUpdateMs = currentTime;
    }
    
    delay(DISPLAY_UPDATE_MS); // ~50 Hz
}