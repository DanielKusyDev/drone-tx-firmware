#pragma once

// Hardware Configuration
#define PIN_THR   0
#define PIN_YAW   1
#define PIN_PITCH 4
#define PIN_ROLL  2
#define PIN_ARM   7

// OLED Configuration
#define OLED_WIDTH  128
#define OLED_HEIGHT 32
#define OLED_SDA    8
#define OLED_SCL    9
#define OLED_ADDR   0x3C

// ESP-NOW Configuration
#define ESPNOW_CHANNEL 1

// Drone MAC address (matching your code)
#define DEFAULT_DRONE_MAC {0xD8, 0x3B, 0xDA, 0x74, 0x83, 0x68}

// Control Configuration
#define PACKET_RATE_HZ    50
#define PACKET_INTERVAL_MS (1000 / PACKET_RATE_HZ)

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
#define IIR_ALPHA          0.3f
#define THR_DEADZONE       50
#define THR_RATE_SCALE     1.2f

// TELEM: Button press timing
#define SHORT_PRESS_MS     500
#define LONG_PRESS_MS      1500

// TELEM: Telemetry parameters
#define TELEM_TIMEOUT_MS   1000
#define DROP_INDICATOR_COUNT 5

// ADC averaging
#define ADC_SAMPLES_DEFAULT 16
#define ADC_SAMPLES_AXIS    4
#define ADC_SAMPLES_CAL     64

// Display update rate
#define DISPLAY_UPDATE_MS  20