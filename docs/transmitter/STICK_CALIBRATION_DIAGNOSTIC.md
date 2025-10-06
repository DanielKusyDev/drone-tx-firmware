# Transmitter Stick Calibration Diagnostic Report

## 📋 Symptom
- **ROLL setpoint: ~12.7** when stick centered
- **PITCH setpoint: ~-2.7** when stick centered
- Offsets persist consistently as throttle increases → systematic, not noise

## 🔍 Root Cause Analysis

### 1. Code Structure (Current State)
**File: [control.h](include/control.h:24-27)**
```cpp
// Hardcoded center values
uint16_t m_centerYaw = 2048;
uint16_t m_centerPitch = 2048;
uint16_t m_centerRoll = 2048;
uint16_t m_centerThr = 2048;
```

**File: [control.cpp:75-86](src/hal/control.cpp:75-86)** - `readAxisCentered()`
```cpp
float raw = (float)readAdcAvg(pin, ADC_SAMPLES_AXIS);
filter = smoothFilter(filter, raw);
int v = (int)lroundf((filter - center) / 2.0f); // ~-1000..1000
```

**Scaling math:**
- ADC range: 0-4095 (12-bit)
- Nominal center: 2048
- Scaling: `(raw - center) / 2.0` → maps ±2048 counts to ±1024 range

### 2. Root Cause Identification
**❌ PROBLEM: Calibration NOT called on startup**

- **File: [App.cpp:148](src/app/App.cpp:148)** - Only calls `control.init()`, NOT `control.calibrate()`
- Centers remain at hardcoded **2048** regardless of actual stick positions
- If true stick center ≠ 2048, you get constant offset

**Mathematical proof:**
```
Actual roll stick center = 2073 (example)
Hardcoded center = 2048
Offset at rest = (2073 - 2048) / 2.0 = 12.5

→ Matches observed setR ≈ 12.7 ✓
```

Similarly for pitch:
```
Actual pitch stick center = 2043 (example)
Offset = (2043 - 2048) / 2.0 = -2.5

→ Matches observed setP ≈ -2.7 ✓
```

### 3. Why Offset Persists with Throttle
- Throttle uses **independent ADC channel** (PIN_THR = 0)
- Roll uses PIN_ROLL = 2, Pitch uses PIN_PITCH = 4
- No cross-talk or mixing detected in code
- Offset is **calibration error**, not noise or interference

## 🛠️ Diagnostic Instrumentation Added

### Debug Output (controlled by existing Logger system)
**File: [control.cpp:48-70](src/hal/control.cpp:48-70)** - Added in `readInputs()`
```cpp
// Prints every 200ms at TRACE level, CALIB category:
[CALIB] ADC raw R:#### P:#### Y:#### T:#### | norm R:##### P:##### Y:##### T:####
[CALIB] Centers  R:#### P:#### Y:#### T:#### | Diff R:±#### P:±#### Y:±#### T:±####
```

### Usage Instructions
1. **Build and upload firmware**
2. **Open serial monitor** at 115200 baud
3. **Enable calibration logging:**
   ```
   level trace        (enable TRACE level logs)
   enable calib       (enable CALIB category)
   ```
4. **Leave sticks centered** for 5 seconds - record output
5. **Move each stick** through full range - verify scaling
6. **Disable verbose logging when done:**
   ```
   level info         (return to INFO level)
   disable calib      (disable CALIB category)
   ```
7. **Analyze the output:**
   - Check `Diff R:` and `Diff P:` when sticks centered
   - If Diff ≠ 0, centers are miscalibrated

## 🎯 Proposed Fix (3 Options)

### Option A: Auto-calibrate on every boot (RECOMMENDED)
**Pros:** Simple, always correct
**Cons:** User must hold sticks neutral during boot

**Implementation:**
```cpp
// In App.cpp after control.init():
LOG_INFO(INPUTS, "Auto-calibrating stick centers...");
control.calibrate();
```

### Option B: Calibrate on first boot, save to NVS
**Pros:** User-friendly, calibrate once
**Cons:** Requires NVS storage, more complex

**Implementation:**
- Add NVS library
- Save `m_centerRoll`, `m_centerPitch`, `m_centerYaw`, `m_centerThr` to flash
- Load on boot; if not present, run calibration

### Option C: Manual re-center via serial command
**Pros:** On-demand, no boot delay
**Cons:** User must trigger manually when drift occurs

**Implementation:**
- Add serial command handler: `CAL\n`
- Calls `control.calibrate()` on demand

## 📊 Validation Checklist

After applying fix, verify:

### ✅ Static Test (sticks centered)
```
Expected output:
[STICKDBG] Diff R: 0-5   P: 0-5   Y: 0-5   (within deadzone)
norm R: 0   P: 0   Y: 0
```

### ✅ Dynamic Test (throttle sweep, roll/pitch centered)
```
Throttle: 0 → 1000
norm R: ±5 max deviation
norm P: ±5 max deviation
```

### ✅ Full Range Test (each stick individually)
- Roll: -1000 ↔ +1000
- Pitch: -1000 ↔ +1000
- Yaw: -1000 ↔ +1000
- Throttle: 0 ↔ 1000

## 🚀 Next Steps

1. **Immediate:** Build firmware
2. **Upload and test:** Follow validation procedure
3. **Optional:** Enable CALIB logging to verify centers are correctly captured
4. **Validate:** Re-test with validation checklist

## 📌 Files Modified

- ✅ [control.cpp](src/hal/control.cpp) - Added TRACE-level debug output in `readInputs()` (CALIB category)
- ✅ [App.cpp:155-158](src/app/App.cpp#L155) - **Auto-calibration on boot IMPLEMENTED**
- ✅ [App.cpp:410-416](src/app/App.cpp#L410) - **Manual re-calibration via 'C' command ADDED**

## ✅ FIX IMPLEMENTED

### Primary Fix: Auto-Calibration on Boot
```cpp
// In App::init() after control.init():
LOG_INFO(INPUTS, "Calibrating stick centers - hold sticks at neutral position...");
m_control->calibrate();
LOG_INFO(INPUTS, "Stick calibration complete");
```

**Behavior:**
- On every boot/reset, transmitter samples all stick positions for 600ms
- Centers are set to actual ADC values at that moment
- **User must ensure sticks are at neutral position during boot**
- OLED displays: "CAL: hold sticks / neutral..." during calibration

### Secondary Fix: Manual Re-Calibration
```cpp
// Serial command: Send 'C' or 'c' + newline
if (c == 'C' || c == 'c') {
    m_control->calibrate();
}
```

**Usage:** Type `C` in serial monitor (115200 baud) to re-calibrate anytime

---
**Status:** ✅ FIX COMPLETE - Ready for build, upload, and validation testing.
