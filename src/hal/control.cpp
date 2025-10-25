#include "control.h"
#include "config.h"
#include "logger.h"
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_SSD1306.h>

// Global display object (matching original code structure)
extern Adafruit_SSD1306 display;

bool ControlManager::init() {
    // Configure GPIO pins
    pinMode(PIN_ARM, INPUT_PULLUP);
    pinMode(PIN_CALIB, INPUT_PULLUP);

    // Configure ADC
    analogReadResolution(ADC_RESOLUTION);
    analogSetAttenuation(ADC_ATTENUATION);
    
    return true;
}

void ControlManager::calibrate() {
    showMessage("CAL: hold sticks", "neutral...");
    delay(600);
    
    m_centerYaw = readAdcAvg(PIN_YAW, ADC_SAMPLES_CAL);
    m_centerPitch = readAdcAvg(PIN_PITCH, ADC_SAMPLES_CAL);
    m_centerRoll = readAdcAvg(PIN_ROLL, ADC_SAMPLES_CAL);
    m_centerThr = readAdcAvg(PIN_THR, ADC_SAMPLES_CAL);
    
    char buf[32];
    snprintf(buf, sizeof(buf), "T:%u Y:%u P:%u", m_centerThr, m_centerYaw, m_centerPitch);
    showMessage("Centers set", buf);
    delay(600);
}

ControlInputs ControlManager::readInputs() {
    updateArmState();

    ControlInputs inputs;
    inputs.throttle = updateThrottle();
    inputs.yaw = readAxisCentered(PIN_YAW, m_filterYaw, m_centerYaw);
    inputs.pitch = readAxisCentered(PIN_PITCH, m_filterPitch, m_centerPitch, true); // Inverted
    inputs.roll = readAxisCentered(PIN_ROLL, m_filterRoll, m_centerRoll);
    inputs.armed = m_armed;
    inputs.calibButtonPressed = isCalibButtonPressed();
    inputs.debugView = m_debugView;  // TELEM: Add debug view state

    // Debug output for stick diagnostics (controlled via logger 'calib' category at TRACE level)
    static unsigned long lastDbgMs = 0;
    unsigned long now = millis();
    if (now - lastDbgMs > 200) {
        lastDbgMs = now;

        // Read raw values directly for diagnosis
        uint16_t rawR = readAdcAvg(PIN_ROLL, ADC_SAMPLES_AXIS);
        uint16_t rawP = readAdcAvg(PIN_PITCH, ADC_SAMPLES_AXIS);
        uint16_t rawY = readAdcAvg(PIN_YAW, ADC_SAMPLES_AXIS);
        uint16_t rawT = readAdcAvg(PIN_THR, ADC_SAMPLES_AXIS);

        LOG_TRACE(CALIB, "ADC raw R:%4u P:%4u Y:%4u T:%4u | norm R:%5d P:%5d Y:%5d T:%4u",
                  rawR, rawP, rawY, rawT,
                  inputs.roll, inputs.pitch, inputs.yaw, inputs.throttle);

        LOG_TRACE(CALIB, "Centers  R:%4u P:%4u Y:%4u T:%4u | Diff R:%+5d P:%+5d Y:%+5d T:%+5d",
                  m_centerRoll, m_centerPitch, m_centerYaw, m_centerThr,
                  (int)rawR - (int)m_centerRoll,
                  (int)rawP - (int)m_centerPitch,
                  (int)rawY - (int)m_centerYaw,
                  (int)rawT - (int)m_centerThr);
    }

    return inputs;
}

bool ControlManager::isArmButtonPressed() const {
    return digitalRead(PIN_ARM) == LOW;
}

bool ControlManager::isCalibButtonPressed() const {
    return digitalRead(PIN_CALIB) == LOW;
}

void ControlManager::showMessage(const char* line1, const char* line2) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println(line1);
    if (line2) {
        display.setCursor(0, 10);
        display.println(line2);
    }
    display.display();
}

uint16_t ControlManager::readAdcAvg(int pin, int samples) const {
    uint32_t acc = 0;
    for (int i = 0; i < samples; i++) {
        acc += analogRead(pin);
    }
    return (uint16_t)(acc / samples);
}

int16_t ControlManager::readAxisCentered(int pin, float& filter, uint16_t center, bool invert) {
    float raw = (float)readAdcAvg(pin, ADC_SAMPLES_AXIS);
    filter = smoothFilter(filter, raw);
    int v = (int)lroundf((filter - center) / 2.0f); // ~-1000..1000

    if (invert) v = -v;
    if (abs(v) < DEADZONE_THRESHOLD) v = 0;
    if (v < RC_AXIS_MIN) v = RC_AXIS_MIN;
    if (v > RC_AXIS_MAX) v = RC_AXIS_MAX;

    return (int16_t)v;
}

uint16_t ControlManager::updateThrottle() {
    unsigned long now = millis();
    float dt = (m_lastLoopMs > 0) ? (now - m_lastLoopMs) / 1000.0f : 0.02f;
    m_lastLoopMs = now;
    
    // Read throttle around calibrated center
    float raw = (float)readAdcAvg(PIN_THR, ADC_SAMPLES_AXIS);
    float diff = raw - m_centerThr;
    
    // Filter the difference
    static float f_raw = 0;
    f_raw = smoothFilter(f_raw, diff);
    int u = (int)lroundf(f_raw / 2.0f); // -1000..1000 approx
    
    if (abs(u) < THR_DEADZONE) u = 0;
    
    float rate = u * THR_RATE_SCALE; // units/s
    m_thrCmd += rate * dt;
    if (m_thrCmd < 0) m_thrCmd = 0;
    if (m_thrCmd > RC_THR_MAX) m_thrCmd = RC_THR_MAX;
    
    return (uint16_t)m_thrCmd;
}

float ControlManager::smoothFilter(float current, float input) const {
    return current + IIR_ALPHA * (input - current);
}

void ControlManager::updateArmState() {
    bool buttonPressed = isArmButtonPressed();
    unsigned long currentTime = millis();
    
    // TELEM: Enhanced button handling for short/long press
    if (!m_prevButton && buttonPressed) {
        // Button just pressed - start timing
        m_buttonPressed = true;
        m_buttonPressStart = currentTime;
    }
    else if (m_prevButton && !buttonPressed && m_buttonPressed) {
        // Button just released - check press duration
        unsigned long pressDuration = currentTime - m_buttonPressStart;
        
        // DEBUG: Print press duration
        LOG_INFO(INPUTS, "Press duration: %d ms", pressDuration);
        
        if (currentTime - m_lastToggleMs > ARM_DEBOUNCE_MS) {
            if (pressDuration < SHORT_PRESS_MS) {
                // Short press: toggle armed state (as before)
                m_armed = !m_armed;
                m_lastToggleMs = currentTime;
                LOG_INFO(INPUTS, "Short press - ARM toggle");
            }
            else if (pressDuration >= LONG_PRESS_MS) {
                // Long press: toggle debug view without changing armed
                m_debugView = !m_debugView;
                m_lastToggleMs = currentTime;
                LOG_INFO(INPUTS, "Long press - Debug view %d", m_debugView ? "ON" : "OFF");
            }
            // Medium press (500ms-1500ms): do nothing
        }
        m_buttonPressed = false;
    }
    
    m_prevButton = buttonPressed;
}