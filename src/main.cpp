#include <Arduino.h>
#include "config.h"
#include "protocol.h"
#include "radio.h"
#include "control.h"
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// Global instances
RadioManager radio;
ControlManager control;

// Global OLED display (matching original code structure)
Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);

// Packet state
volatile uint16_t g_sequenceNumber = 0;

// Drone MAC address
uint8_t g_droneMac[6] = DEFAULT_DRONE_MAC;

void setup() {
    Serial.begin(115200);
    
    // Initialize I2C for OLED
    Wire.begin(OLED_SDA, OLED_SCL);
    
    // Initialize OLED display
    if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
        Serial.println("OLED init failed!");
        while (1) delay(1000);
    }
    display.clearDisplay();
    display.display();
    
    // Initialize control system
    if (!control.init()) {
        Serial.println("Control init failed!");
        while (1) delay(1000);
    }
    
    // Initialize radio
    if (!radio.init(ESPNOW_CHANNEL)) {
        Serial.println("ESP-NOW init failed");
    }
    
    // Set peer MAC address
    if (!radio.setPeerMac(g_droneMac)) {
        Serial.println("Peer setup failed!");
    }
    
    delay(500);
    
    // Perform calibration
    control.calibrate();
    
    Serial.println("RC Transmitter Ready!");
}

void loop() {
    // Read control inputs
    ControlInputs inputs = control.readInputs();
    
    // Build and send packet
    RcPacket packet = {};
    packet.magic = RC_PACKET_MAGIC;
    packet.version = RC_PACKET_VERSION;
    packet.seq = ++g_sequenceNumber;
    packet.thr = inputs.throttle;
    packet.yaw = inputs.yaw;
    packet.pitch = inputs.pitch;
    packet.roll = inputs.roll;
    packet.flags = inputs.armed ? RC_FLAG_ARMED : 0;
    packet.rssi_hint = 0;
    
    // Calculate CRC (on all fields except CRC itself)
    packet.crc = crc16_x25(reinterpret_cast<const uint8_t*>(&packet), 
                          sizeof(packet) - sizeof(packet.crc));
    
    // Send packet
    radio.sendPacket(&packet, sizeof(packet));
    
    // Update OLED display
    display.clearDisplay();
    display.setCursor(0, 0);
    display.print("ARM: ");
    display.println(inputs.armed ? "ON" : "OFF");
    display.setCursor(0, 10);
    display.print("THR: ");
    display.print(inputs.throttle);
    display.setCursor(0, 20);
    display.print("Y:");
    display.print(inputs.yaw);
    display.print(" P:");
    display.print(inputs.pitch);
    display.print(" R:");
    display.print(inputs.roll);
    display.display();
    
    delay(DISPLAY_UPDATE_MS); // ~50 Hz
}