#pragma once
#include <cstdint>
#include "config.h"

struct ControlInputs {
    uint16_t throttle;  // 0..1000
    int16_t yaw;        // -1000..1000
    int16_t pitch;      // -1000..1000
    int16_t roll;       // -1000..1000
    bool armed;
};

class ControlManager {
public:
    bool init();
    void calibrate();
    ControlInputs readInputs();
    bool isArmButtonPressed() const;
    void showMessage(const char* line1, const char* line2 = nullptr);
    
private:
    // Calibration centers
    uint16_t m_centerYaw = 2048;
    uint16_t m_centerPitch = 2048;
    uint16_t m_centerRoll = 2048;
    uint16_t m_centerThr = 2048;
    
    // IIR filter states for axes
    float m_filterYaw = 0.0f;
    float m_filterPitch = 0.0f;
    float m_filterRoll = 0.0f;
    
    // Throttle state (latched/integrator)
    float m_thrCmd = 0.0f;
    unsigned long m_lastLoopMs = 0;
    
    // ARM button state
    bool m_armed = false;
    bool m_prevButton = true;
    unsigned long m_lastToggleMs = 0;
    
    uint16_t readAdcAvg(int pin, int samples = ADC_SAMPLES_DEFAULT) const;
    int16_t readAxisCentered(int pin, float& filter, uint16_t center, bool invert = false);
    uint16_t updateThrottle();
    float smoothFilter(float current, float input) const;
    void updateArmState();
};