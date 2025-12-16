#pragma once

// Include hardware pin definitions
#include "pins.h"

// ESP-NOW Configuration
#define ESPNOW_CHANNEL 1

// Drone MAC address (matching your code)
#define DEFAULT_DRONE_MAC {0xD8, 0x3B, 0xDA, 0x74, 0x83, 0x68}

// Control Configuration
#define PACKET_RATE_HZ    50  // RC control packets (TX -> RX)
#define PACKET_INTERVAL_MS (1000 / PACKET_RATE_HZ)

// Telemetry Configuration
#define TELEMETRY_RATE_HZ 10  // Telemetry packets (RX -> TX)
#define TELEMETRY_INTERVAL_MS (1000 / TELEMETRY_RATE_HZ)

// ADC Configuration
#define ADC_RESOLUTION    12
#define ADC_ATTENUATION   ADC_11db
#define ADC_MAX_VALUE     4095

// RC Control Limits
#define RC_THR_MIN        0
#define RC_THR_MAX        1000
#define RC_AXIS_MIN       -1000
#define RC_AXIS_MAX       1000

// Control Parameters
#define DEADZONE_THRESHOLD 20
#define ARM_DEBOUNCE_MS    100
#define IIR_ALPHA          0.15f  // Smooth joystick: reduced from 0.3f for smoother response
#define THR_DEADZONE       50
#define THR_RATE_SCALE     0.6f   // Smooth joystick: reduced from 1.2f to prevent too fast climb

// TELEM: Button press timing
#define SHORT_PRESS_MS     500
#define LONG_PRESS_MS      1500

// TELEM: Telemetry parameters
#define TELEM_TIMEOUT_MS   (TELEMETRY_INTERVAL_MS * 3)  // Consider telemetry stale after 3 missed packets
#define DROP_INDICATOR_COUNT 5

// ADC averaging
#define ADC_SAMPLES_DEFAULT 16
#define ADC_SAMPLES_AXIS    8  // Smooth joystick: increased from 4 for better noise reduction
#define ADC_SAMPLES_CAL     64

// Display update rate
#define DISPLAY_UPDATE_MS  20

// UART Mode Configuration
// Uncomment to enable binary telemetry forwarding to UART
// Comment out for debug text mode (default)
#define UART_MODE_TELEMETRY_BINARY

// UART Configuration
#define UART_BAUD_RATE 115200