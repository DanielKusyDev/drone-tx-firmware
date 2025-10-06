# Stick Calibration Fix - Validation Procedure

## 🔧 Build & Upload

### Step 1: Build firmware
```bash
pio run
```

### Step 2: Upload to transmitter
```bash
pio run --target upload
```

### Step 3: Open serial monitor
```bash
pio device monitor
```
Or use Arduino IDE / PlatformIO IDE serial monitor at **115200 baud**.

---

## 📊 Validation Tests

### Test 1: Boot Calibration (CRITICAL)
**Objective:** Verify auto-calibration runs on boot

**Procedure:**
1. **IMPORTANT:** Hold all sticks at center position
2. Press reset button on ESP32-C3
3. Watch OLED display and serial output

**Expected Output:**
```
[INPUTS] Calibrating stick centers - hold sticks at neutral position...
[OLED displays: "CAL: hold sticks / neutral..."]
[INPUTS] Stick calibration complete
```

**Pass Criteria:**
- ✅ OLED shows calibration message
- ✅ Serial confirms calibration complete
- ✅ Boot sequence continues normally

---

### Test 2: Static Centered Sticks
**Objective:** Confirm zero drift when sticks are idle

**Procedure:**
1. After boot completes, leave all sticks at center
2. **Enable detailed logging:**
   ```
   level trace
   enable calib
   ```
3. Observe serial output for 5 seconds
4. Record `[CALIB]` messages

**Expected Output (with CALIB logging enabled):**
```
[CALIB] ADC raw R:2073 P:2043 Y:2055 T:2048 | norm R:0 P:0 Y:0 T:0
[CALIB] Centers  R:2073 P:2043 Y:2055 T:2048 | Diff R:+0 P:+0 Y:+0 T:+0
```

**Pass Criteria:**
- ✅ `norm R`, `norm P`, `norm Y` = **0** (±5 acceptable due to ADC noise/deadband)
- ✅ `Diff` values near **0** (within ±10 counts)
- ✅ Values stable over 5 seconds

**Cleanup:**
```
level info
disable calib
```

---

### Test 3: Throttle Independence
**Objective:** Verify roll/pitch remain zero while throttle changes

**Procedure:**
1. Ensure CALIB logging is enabled: `level trace` + `enable calib`
2. Keep roll/pitch/yaw sticks centered
3. Slowly move throttle stick from 0% → 100% → 0%
4. Watch serial output for roll/pitch values

**Expected Output:**
```
[CALIB] ... | norm R:0 P:0 Y:0 T:0
[CALIB] ... | norm R:0 P:0 Y:0 T:250
[CALIB] ... | norm R:0 P:0 Y:0 T:500
[CALIB] ... | norm R:0 P:0 Y:0 T:750
[CALIB] ... | norm R:0 P:0 Y:0 T:1000
[CALIB] ... | norm R:0 P:0 Y:0 T:500
[CALIB] ... | norm R:0 P:0 Y:0 T:0
```

**Pass Criteria:**
- ✅ `norm R` and `norm P` remain **0** (±5) throughout throttle sweep
- ✅ `norm T` changes smoothly 0→1000→0
- ✅ No cross-talk or drift

---

### Test 4: Full Range Verification
**Objective:** Confirm proper scaling and inversion

**Procedure:**
For **each axis** (Roll, Pitch, Yaw):
1. Move stick to full **down/left** position
2. Hold 1 second, observe output
3. Move stick to full **up/right** position
4. Hold 1 second, observe output
5. Return to center

**Expected Output:**

| Axis  | Direction | Expected norm value | Notes                    |
|-------|-----------|---------------------|--------------------------|
| Roll  | Left      | ≈ -1000             | Full left deflection     |
| Roll  | Right     | ≈ +1000             | Full right deflection    |
| Pitch | Down      | ≈ -1000             | **Inverted** (down = -) |
| Pitch | Up        | ≈ +1000             | **Inverted** (up = +)   |
| Yaw   | Left      | ≈ -1000             | Full left deflection     |
| Yaw   | Right     | ≈ +1000             | Full right deflection    |

**Pass Criteria:**
- ✅ All axes reach ±1000 at endpoints (±50 tolerance)
- ✅ Pitch inverted correctly (hardware down → negative setpoint)
- ✅ Values return to 0 when centered

---

### Test 5: Manual Re-Calibration
**Objective:** Verify serial command 'C' triggers re-calibration

**Procedure:**
1. Intentionally move sticks **OFF center**
2. Type `C` in serial monitor and press Enter
3. **Immediately** return sticks to center before 600ms timeout
4. Watch for confirmation messages

**Expected Output:**
```
[INPUTS] Manual calibration triggered - hold sticks neutral!
[OLED displays: "CAL: hold sticks / neutral..."]
[INPUTS] Calibration complete
```

**Pass Criteria:**
- ✅ Calibration runs on command
- ✅ New centers captured
- ✅ Normalized values return to ~0 after calibration

---

## 🚨 Failure Scenarios & Troubleshooting

### Issue: "norm R/P still ≠ 0 after calibration"
**Possible Causes:**
- Sticks were not centered during boot calibration
- Physical stick deadzone too small (check `DEADZONE_THRESHOLD` in config.h)
- ADC noise exceeds filter capacity

**Solutions:**
1. Re-run calibration with sticks precisely centered
2. Use manual calibration command `C` for better control
3. Increase `DEADZONE_THRESHOLD` from 20 to 30-50 in [config.h:32](include/config.h#L32)

### Issue: "Sticks reversed or wrong scaling"
**Check:**
- Pin assignments in [pins.h:14-15](include/pins.h#L14)
- Invert flag in [control.cpp:42](src/hal/control.cpp#L42) - only pitch should be inverted
- ADC wiring (ensure correct GPIO pins connected)

### Issue: "Values jitter excessively"
**Solutions:**
- Increase `IIR_ALPHA` for more smoothing (current: 0.3 in [config.h:34](include/config.h#L34))
- Increase `ADC_SAMPLES_AXIS` from 4 to 8-16 in [config.h:48](include/config.h#L48)
- Check power supply stability (ADC sensitive to VCC noise)

---

## 📝 Test Results Template

```
Date: ___________
Firmware Version: (git commit hash)
Hardware: ESP32-C3 + [joystick model]

[ ] Test 1: Boot Calibration - PASS / FAIL
    Notes: _______________________________________

[ ] Test 2: Static Centered Sticks - PASS / FAIL
    Measured R:___ P:___ Y:___ (should be ~0)

[ ] Test 3: Throttle Independence - PASS / FAIL
    Max drift during sweep: R:±___ P:±___

[ ] Test 4: Full Range Verification - PASS / FAIL
    Roll: [___  to  ___]  (expect -1000 to +1000)
    Pitch: [___  to  ___]
    Yaw: [___  to  ___]

[ ] Test 5: Manual Re-Calibration - PASS / FAIL

Overall Result: PASS / FAIL
Tester Signature: _________________
```

---

## 🎯 Success Criteria Summary

Fix is **validated** when:
- ✅ All 5 tests pass
- ✅ Static stick readings: |norm R|, |norm P|, |norm Y| < 5
- ✅ Throttle sweep: no cross-talk (drift < 10)
- ✅ Full range: all axes reach ±1000
- ✅ Manual calibration works reliably

**Next Step:** If all tests pass, disable verbose logging for normal operation:
```
level info
disable calib
```
