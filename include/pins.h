#pragma once

/**
 * @file pins.h  
 * @brief Hardware pin definitions for ESP32-C3 RC Transmitter
 * 
 * Extracted from config.h for better organization.
 * Maintains exact same pin assignments as original.
 */

// Control Input Pins (ADC)
#define PIN_THR   0   // Throttle stick (integrator mode)
#define PIN_YAW   1   // Yaw stick (proportional)  
#define PIN_PITCH 4   // Pitch stick (proportional, inverted)
#define PIN_ROLL  2   // Roll stick (proportional)
#define PIN_ARM   7   // ARM/DISARM button
#define PIN_CALIB 10   // Calibration button

// OLED Display (I2C)
#define OLED_SDA  8   // I2C Data
#define OLED_SCL  9   // I2C Clock
#define OLED_ADDR 0x3C // I2C Address

// Display Properties
#define OLED_WIDTH  128
#define OLED_HEIGHT 32