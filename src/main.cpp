#include <Arduino.h>
#include "config.h"
#include "protocol.h"
#include "radio.h"
#include "control.h"
#include "app/App.h"
#include "utils/Timing.h"
#include "logger.h"
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

// FORCE_DISARM: Force disarm warning state
bool g_forceDisarmActive = false;
unsigned long g_forceDisarmTimestamp = 0;
#define FORCE_DISARM_WARNING_MS 5000  // Show warning for 5 seconds

// LOG: Compatibility shim for radio.cpp error logging
// These global functions forward to the new logger system
void radioWrongPacketSize(int actualLen, int expectedLen) {
    LOG_ERROR(RADIO, "Wrong packet size: %d (expected %d)", actualLen, expectedLen);
}

void radioWrongMagicVersion(uint8_t magic, uint8_t version) {
    LOG_ERROR(RADIO, "Wrong magic/version: 0x%02X / %d", magic, version);
}

void radioCrcError(uint16_t calculated, uint16_t received) {
    LOG_ERROR(RADIO, "CRC mismatch: calc=0x%04X rcv=0x%04X", calculated, received);
}


void setup() {
    g_app.init();
}

void loop() {
    g_app.loop();
}