# OLED View Inventory - Transmitter UI

*Generated: October 2, 2025*

## Overview
This document catalogues all existing OLED display modes and states used by the transmitter firmware, based on code analysis of the UI module.

## Core Display Views

### 1. No Telemetry Normal View
- **Function**: `updateOledNoTelemNormalView(inputs)`
- **Trigger**: Telemetry timeout (`Age::since(g_lastTelemUpdateMs) > TELEM_TIMEOUT_MS`) AND normal view mode
- **Data Displayed**:
  - ARM status (ARM/---)
  - ESP-NOW channel number
  - Throttle value
  - Control axes (Y/P/R values)
- **Warning States**:
  - "LINK LOST! THR:XXX" - when no telemetry available
  - "LEVEL! THR:XXX" - when horizon safety triggered
  - "LINK?" indicator - when telemetry is stale

### 2. No Telemetry Debug View  
- **Function**: `updateOledNoTelemDebugView(inputs)`
- **Trigger**: Telemetry timeout AND debug view mode (`inputs.debugView`)
- **Data Displayed**:
  - Technical debug header
  - ARM state (ON/OFF format)
  - Throttle and all control axes
- **Warning States**:
  - "LINK LOST!" - telemetry timeout
  - "HORIZON UNSAFE!" - horizon safety issues

### 3. Normal View With Telemetry
- **Function**: `updateOledNormalView(inputs, telem, dropCount)`
- **Trigger**: Active telemetry AND normal view mode
- **Data Displayed**:
  - ARM status and throttle
  - Roll/pitch angles from drone (degrees)
  - Yaw rate (degrees/second)
  - Telemetry frequency (actual/expected FPS)
  - Packet drop indicator (dot)
- **Warning States**:
  - Flash warnings: "LINK LOST!", "LEVEL!", "THR=0 TO ARM", "WAIT..."
  - Status indicators: "LINK?", "HORIZ?"

### 4. Debug View With Telemetry
- **Function**: `updateOledDebugView(inputs, telem, dropCount)`
- **Trigger**: Active telemetry AND debug view mode (`inputs.debugView`)
- **Data Displayed**:
  - Setpoint angles (setR, setP)
  - Rate values (rateR, rateP)
  - PID outputs (outR, outP, outY)
  - Packet drop indicator (dot)

## View Selection Logic

```cpp
// Main view selection (App.cpp line ~223)
if (Age::since(g_lastTelemUpdateMs) > TELEM_TIMEOUT_MS) {
    // No telemetry available
    if (inputs.debugView) {
        updateOledNoTelemDebugView(inputs);
    } else {
        updateOledNoTelemNormalView(inputs);
    }
} else {
    // Telemetry available  
    if (inputs.debugView) {
        updateOledDebugView(inputs, lastTelem, dropCount);
    } else {
        updateOledNormalView(inputs, lastTelem, dropCount);
    }
}
```

## Flash Warning System

### Trigger Conditions
- **g_showHorizFlash** flag set by safety system when:
  - Telemetry timeout (`Age::since(g_lastTelemUpdateMs) > TELEM_TIMEOUT_MS`)
  - Horizon unsafe (`!g_horizonOK`) 
  - Drone not armed (`!g_telemArmed`)

### Flash Messages Priority
1. **"LINK LOST!"** - No telemetry from drone
2. **"LEVEL!"** - Drone not level/horizon unsafe
3. **"THR=0 TO ARM"** - Throttle must be zero to arm
4. **"WAIT..."** - Generic safety hold

## Control Triggers

### Debug View Toggle
- **Button**: ARM button long press (>1500ms when disarmed)
- **State**: `ControlManager::m_debugView` boolean flag
- **Effect**: Switches between normal and debug display modes

### Update Frequency
- **OLED Refresh**: 20Hz (every 50ms via `oledEvery.check()`)
- **Display Command**: `display.display()` called after each update

## Notes
- All views use 128x32 OLED with SSD1306 driver
- Text size 1, white color on black background
- Views are mutually exclusive - only one active at a time
- Flash warnings override normal content when active
- Drop indicator appears as small dot when `dropCount >= DROP_INDICATOR_COUNT`