#include <Arduino.h>
#include "config.h"
#include "protocol.h"
#include "radio.h"
#include "control.h"
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>

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
bool g_csvHeaderPrinted = false;
unsigned long g_lastTelemUpdateMs = 0;
float g_telemFrequency = 0.0f;

// TELEM: Helper functions
void updateOledNormalView(const ControlInputs& inputs, const TelemetryPacket& telem, uint32_t dropCount) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    
    // Line 1: ARM and THR
    display.setCursor(0, 0);
    display.print("ARM: ");
    display.print(inputs.armed ? "ON" : "OFF");
    display.print(" THR:");
    display.print(inputs.throttle);
    
    // Line 2: Roll and Pitch angles
    display.setCursor(0, 10);
    display.print("R: ");
    display.print(telem.angR_x10 / 10.0f, 1);
    display.print(" P: ");
    display.print(telem.angP_x10 / 10.0f, 1);
    
    // Line 3: Yaw rate and telemetry frequency
    display.setCursor(0, 20);
    display.print("YR: ");
    display.print((int)(telem.rateY_x10 / 10.0f));
    display.print(" FPS: ");
    display.print((int)g_telemFrequency);
    
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
    display.print(telem.setR_x10 / 10.0f, 1);
    display.print(" setP: ");
    display.print(telem.setP_x10 / 10.0f, 1);
    
    // Line 2: Rate values
    display.setCursor(0, 10);
    display.print("rateR:");
    display.print((int)(telem.rateR_x10 / 10.0f));
    display.print(" rateP:");
    display.print((int)(telem.rateP_x10 / 10.0f));
    
    // Line 3: Outputs
    display.setCursor(0, 20);
    display.print("outR:");
    display.print(telem.outR);
    display.print(" outP:");
    display.print(telem.outP);
    display.print(" Y:");
    display.print(telem.outY);
    
    // Drop indicator (small dot every 5 drops)
    if (dropCount >= DROP_INDICATOR_COUNT) {
        display.fillCircle(120, 2, 1, SSD1306_WHITE);
    }
    
    display.display();
}

void printCsvLine(unsigned long ms, const ControlInputs& inputs, const TelemetryPacket& telem) {
    Serial.print(ms); Serial.print(",");
    Serial.print(inputs.armed ? 1 : 0); Serial.print(",");
    Serial.print(inputs.throttle); Serial.print(",");
    Serial.print(telem.setR_x10 / 10.0f, 1); Serial.print(",");
    Serial.print(telem.setP_x10 / 10.0f, 1); Serial.print(",");
    Serial.print(telem.angR_x10 / 10.0f, 1); Serial.print(",");
    Serial.print(telem.angP_x10 / 10.0f, 1); Serial.print(",");
    Serial.print(telem.rateR_x10 / 10.0f, 1); Serial.print(",");
    Serial.print(telem.rateP_x10 / 10.0f, 1); Serial.print(",");
    Serial.print(telem.rateY_x10 / 10.0f, 1); Serial.print(",");
    Serial.print(telem.outR); Serial.print(",");
    Serial.print(telem.outP); Serial.print(",");
    Serial.print(telem.outY); Serial.print(",");
    Serial.print(telem.m1); Serial.print(",");
    Serial.print(telem.m2); Serial.print(",");
    Serial.print(telem.m3); Serial.print(",");
    Serial.print(telem.m4);
    Serial.println();
}

void setup() {
    Serial.begin(115200);
    delay(1000);  // Dodaj opóźnienie na stabilizację
    
    Serial.println();
    Serial.println("=== RC Transmitter Starting ===");
    Serial.println("Serial init OK");
    
    // Initialize I2C for OLED
    Wire.begin(OLED_SDA, OLED_SCL);
    Serial.println("I2C init OK");
    
    // Initialize OLED display
    if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
        Serial.println("OLED init failed!");
        while (1) delay(1000);
    }
    Serial.println("OLED init OK");
    display.clearDisplay();
    display.display();
    
    // Initialize control system
    if (!control.init()) {
        Serial.println("Control init failed!");
        while (1) delay(1000);
    }
    Serial.println("Control init OK");
    
    // Initialize radio
    if (!radio.init(ESPNOW_CHANNEL)) {
        Serial.println("ESP-NOW init failed");
    } else {
        Serial.println("ESP-NOW init OK");
    }
    
    // Set peer MAC address
    if (!radio.setPeerMac(g_droneMac)) {
        Serial.println("Peer setup failed!");
    } else {
        Serial.println("Peer MAC set OK");
    }
    
    delay(500);
    
    // Perform calibration
    Serial.println("Starting calibration...");
    control.calibrate();
    Serial.println("Calibration complete");
    
    Serial.println("RC Transmitter Ready!");
    Serial.println("Waiting for telemetry from drone...");
    
    // DEBUG: Print our MAC address
    uint8_t mac[6];
    WiFi.macAddress(mac);
    Serial.print("Our MAC: ");
    for (int i = 0; i < 6; i++) {
        Serial.printf("%02X", mac[i]);
        if (i < 5) Serial.print(":");
    }
    Serial.println();
    
    // DEBUG: Print drone MAC we expect
    Serial.print("Drone MAC: ");
    for (int i = 0; i < 6; i++) {
        Serial.printf("%02X", g_droneMac[i]);
        if (i < 5) Serial.print(":");
    }
    Serial.println();
    
    // TELEM: Print CSV header
    Serial.println("ms,armed,thr,setR,setP,angR,angP,rateR,rateP,rateY,outR,outP,outY,m1,m2,m3,m4");
    g_csvHeaderPrinted = true;
}

void loop() {
    unsigned long currentTime = millis();
    static unsigned long lastDebugMs = 0;
    
    // Check for serial commands
    if (Serial.available()) {
        char cmd = Serial.read();
        if (cmd == 'M' || cmd == 'm') {
            // Print MAC address
            uint8_t mac[6];
            WiFi.macAddress(mac);
            Serial.print("Transmitter MAC: ");
            for (int i = 0; i < 6; i++) {
                Serial.printf("%02X", mac[i]);
                if (i < 5) Serial.print(":");
            }
            Serial.println();
        }
        // Clear remaining characters
        while (Serial.available()) {
            Serial.read();
        }
    }
    
    // Read control inputs with button handling
    ControlInputs inputs = control.readInputs();
    
    // Debug info co 5 sekund
    if (currentTime - lastDebugMs >= 5000) {
        Serial.print("[DEBUG] Time: ");
        Serial.print(currentTime);
        Serial.print(" ARM: ");
        Serial.print(inputs.armed ? "ON" : "OFF");
        Serial.print(" THR: ");
        Serial.print(inputs.throttle);
        Serial.print(" Seq: ");
        Serial.println(g_sequenceNumber);
        lastDebugMs = currentTime;
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
    packet.flags = inputs.armed ? RC_FLAG_ARMED : 0;
    if (inputs.debugView) packet.flags |= RC_FLAG_DEBUG;
    packet.rssi_hint = 0;
    
    // Calculate CRC (on all fields except CRC itself)
    packet.crc = crc16_x25(reinterpret_cast<const uint8_t*>(&packet), 
                          sizeof(packet) - sizeof(packet.crc));
    
    // Send packet
    radio.sendPacket(&packet, sizeof(packet));
    
    // Check if we have fresh telemetry data
    TelemetryPacket telemetry;
    bool hasFreshTelemetry = false;
    uint32_t dropCount = 0;
    
    if (radio.hasNewTelemetry()) {
        telemetry = radio.getLastTelemetry();
        dropCount = radio.getDropCount();
        radio.clearNewTelemetryFlag();
        hasFreshTelemetry = true;
        
        unsigned long telemUpdateMs = millis();
        
        // Calculate telemetry frequency
        if (g_lastTelemUpdateMs != 0) {
            float deltaS = (telemUpdateMs - g_lastTelemUpdateMs) / 1000.0f;
            if (deltaS > 0.001f) {
                g_telemFrequency = 0.9f * g_telemFrequency + 0.1f * (1.0f / deltaS);
            }
        }
        g_lastTelemUpdateMs = telemUpdateMs;
        
        // Print CSV header if needed
        if (!g_csvHeaderPrinted) {
            Serial.println("ms,armed,throttle,setR,setP,angR,angP,rateR,rateP,rateY,outR,outP,outY,m1,m2,m3,m4");
            g_csvHeaderPrinted = true;
        }
        
        // Print CSV line with fresh telemetry
        printCsvLine(currentTime, inputs, telemetry);
    }
    
    // OLED display - choose view based on debug flag
    if (hasFreshTelemetry) {
        if (inputs.debugView) {
            updateOledDebugView(inputs, telemetry, dropCount);
        } else {
            updateOledNormalView(inputs, telemetry, dropCount);
        }
    } else {
        // No telemetry - show basic TX status but respect debugView
        display.clearDisplay();
        display.setTextSize(1);
        display.setTextColor(SSD1306_WHITE);
        
        if (inputs.debugView) {
            // Debug view without telemetry - show more technical info
            display.setCursor(0, 0);
            display.print("DEBUG MODE (no telem)");
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
        } else {
            // Normal view without telemetry - clean display
            display.setCursor(0, 0);
            display.print("TX: ");
            display.print(inputs.armed ? "ARM" : "---");
            display.print(" CH:");
            display.print(ESPNOW_CHANNEL);
            display.setCursor(0, 10);
            display.print("THR: ");
            display.print(inputs.throttle);
            display.setCursor(0, 20);
            display.print("Y:");
            display.print((int)inputs.yaw);
            display.print(" P:");
            display.print((int)inputs.pitch);
            display.print(" R:");
            display.print((int)inputs.roll);
        }
        
        display.display();
    }
    
    delay(DISPLAY_UPDATE_MS); // ~50 Hz
}