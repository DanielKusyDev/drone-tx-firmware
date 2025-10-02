#include "Display.h"
#include "config.h"
#include "../utils/Timing.h"
#include <Adafruit_SSD1306.h>

// External global variables
extern Adafruit_SSD1306 display;
extern unsigned long g_lastTelemUpdateMs;
extern bool g_showHorizFlash;
extern bool g_horizonOK;

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
    extern float g_telemFrequency;
    
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
        extern bool g_telemArmed;
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