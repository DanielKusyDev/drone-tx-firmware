# RC Transmitter Firmware - Project Context for Claude

## Project Overview

This is an **RC transmitter firmware** for ESP32-based micro-drones. Built with PlatformIO/Arduino, it provides bidirectional communication between a handheld transmitter (ESP32-C3) and a micro-drone (ESP32-S3) using ESP-NOW protocol with professional-grade telemetry.

**What this project does:**
- Transmits 50 Hz RC commands (throttle, yaw, pitch, roll) from joysticks to drone
- Receives 7 types of telemetry packets at varying rates (attitude 20Hz, motors 5Hz, status 2.5Hz, etc.)
- Displays flight data on OLED (128×32) with normal/debug views
- Handles ARM/DISARM logic with safety gates
- Forwards telemetry to UART for external dashboards (Python bridge → React UI)

---

## How to Work with This Codebase

### Build & Upload
```bash
# Build firmware
pio run

# Upload to ESP32-C3
pio run -t upload

# Serial monitor (115200 baud)
pio device monitor -b 115200
```

### Project Structure
```
src/
├── main.cpp              # Entry point, calls App::init() and App::loop()
├── app/App.cpp           # Main application logic (50Hz RC, 20Hz OLED, telemetry)
├── hal/control.cpp       # ControlManager: joystick ADC, button handling, calibration
├── radio/radio.cpp       # RadioManager: ESP-NOW TX/RX, telemetry parsing
├── telemetry/            # NEW: TelemetryForwarder for UART binary output
├── ui/Display.cpp        # OLED rendering (Normal/Debug views)
├── utils/protocol.cpp    # CRC-16 validation, packet structures
└── logger.cpp            # Categorized logging (ERROR/INFO/DEBUG)

include/
├── config.h              # ALL CONFIGURATION HERE (pins, rates, thresholds, MAC)
├── pins.h                # GPIO mapping
├── protocol.h            # Packet definitions (RcPacket, TelemetryAttitude, etc.)
└── [module].h            # Header for each module

docs/transmitter/         # REFERENCE DOCUMENTATION (read before modifying)
├── transmitter_hardware.md    # TX hardware specs (ESP32-C3, OLED, joysticks)
├── drone_hardware.md          # Drone specs (ESP32-S3, MPU6050, motors)
├── telemetry.md               # Enhanced telemetry system (7 packet types)
├── telemetry_forwarding.md    # UART binary forwarding for UI
└── log_format.md              # How to interpret serial logs
```

### Key Files to Read Before Changes
- **`include/config.h`** - All tunable parameters (rates, thresholds, MAC address)
- **`docs/transmitter/telemetry.md`** - Telemetry packet structures and rates
- **`docs/transmitter/telemetry_forwarding.md`** - UART forwarding system
- **`src/app/App.cpp`** - Main loop timing and integration point

### Testing Commands (Serial at 115200 baud)
```bash
M    # Show MAC addresses (TX and drone)
O    # Toggle OLED demo mode (10 states, 2s each)
C    # Manual stick calibration (hold neutral)
D    # Radio diagnostics (TX/RX success rate)
E    # Enhanced telemetry stats (per-packet-type)
T    # Toggle enhanced telemetry ON/OFF
U    # Toggle UART mode (DEBUG_TEXT ↔ TELEMETRY_BINARY)
F    # Forwarder statistics

log status              # Show active log categories
log enable TELEM        # Enable DEBUG logs for TELEM category
log disable INPUTS      # Disable INPUTS category logs
```

---

## Tech Stack

**Hardware:**
- **TX**: ESP32-C3 Super Mini (USB-C, built-in antenna)
- **Drone**: ESP32-S3 XIAO
- **Display**: SSD1306 128×32 OLED (I²C, 0x3C)
- **IMU**: MPU-6050 (I²C, on drone)
- **Power**: 3× AA NiMH → LDO 3.3V (TX), 1S Li-Po (drone)

**Software:**
- **Platform**: PlatformIO
- **Framework**: Arduino ESP32
- **Communication**: ESP-NOW (peer-to-peer, channel 1)
- **CRC**: CRC-16/X.25 (polynomial 0x8408)

**Key Libraries:**
- Wire (I²C for OLED)
- WiFi.h (for ESP-NOW)
- Adafruit_SSD1306 (OLED)
- Every (timing without delay())

---

## Architecture Patterns

### Timing System (Non-Blocking)
Uses `Every` pattern instead of `delay()`:
```cpp
static Every rcEvery(20ms);      // 50 Hz RC packet TX
static Every oledEvery(50ms);    // 20 Hz OLED update
static Every telemEvery(100ms);  // 10 Hz telemetry processing

if (rcEvery.check()) {
    // Send RC packet
}
```

### Module Integration
App.cpp integrates modules via composition:
```cpp
class App {
    ControlManager control;
    RadioManager radio;
    Display display;
    TelemetryForwarder telemForwarder;
};
```

### Dependency Injection
RadioManager receives error logger callback to avoid circular dependencies:
```cpp
radio.setErrorLogger([](const char* msg) {
    LOG_ERROR(RADIO, "%s", msg);
});
```

### Global State (Pragmatic Choice)
Display, control, radio are global for simpler integration across modules. Trade-off: easier to use, harder to test in isolation.

---

## Communication Protocols

### RC Packet (TX → Drone, 50 Hz)
**Structure (16 bytes):**
```cpp
struct RcPacket {
    uint8_t  magic;      // 0xA5
    uint8_t  version;    // 1
    uint16_t seq;        // Sequence counter
    uint16_t thr;        // 0..1000
    int16_t  yaw;        // -1000..1000
    int16_t  pitch;      // -1000..1000
    int16_t  roll;       // -1000..1000
    uint8_t  flags;      // bit0=ARM, bit1=CALIBRATE, bit2=DEBUG
    uint8_t  rssi_hint;  // 0 (future use)
    uint16_t crc;        // CRC-16/X.25
};
```

### Enhanced Telemetry (Drone → TX)
**Multi-packet system** with different rates per data type.

**Magic byte:** `0x5B`, **Version:** `2`

**Packet Types:**

| Type | ID | Rate | Size | Contains |
|------|----|----|------|----------|
| ATTITUDE | 0x01 | 20 Hz | 24B | Roll/pitch/yaw angles & rates |
| CONTROL | 0x02 | 10 Hz | 30B | Setpoints, PID outputs, gain scaling |
| MOTORS | 0x03 | 5 Hz | 31B | Motor commands & actual outputs |
| STATUS | 0x04 | 2.5 Hz | 24B | Armed, mode, safety flags, link quality |
| SENSORS | 0x05 | 1.25 Hz | 30B | Raw IMU (accel, gyro, mag) |
| SAFETY | 0x06 | 1.25 Hz | 20B | Ground confidence, error flags |
| PERFORMANCE | 0x07 | 0.625 Hz | 22B | Loop timing, CPU, heap |

**See:** `docs/transmitter/telemetry.md` for detailed packet structures.

### Telemetry Forwarding (NEW Feature)
TX can forward raw binary telemetry to UART for external UI:
- **DEBUG_TEXT mode** (default): Human-readable logs
- **TELEMETRY_BINARY mode**: Raw binary packets → Python bridge → React UI
- **Runtime toggle**: `U` command switches modes without recompile
- **Selective forwarding**: Configure which packet types to forward (ATTITUDE, MOTORS, STATUS by default)

**See:** `docs/transmitter/telemetry_forwarding.md`

---

## Critical Configuration (include/config.h)

### ESP-NOW
```cpp
#define ESPNOW_CHANNEL 1
#define DEFAULT_DRONE_MAC {0xD8, 0x3B, 0xDA, 0x74, 0x83, 0x68}
```
**IMPORTANT:** Verify drone MAC with `M` command. Must match on both sides.

### Rates & Timing
```cpp
#define PACKET_RATE_HZ 50           // RC TX rate
#define TELEMETRY_RATE_HZ 10        // Processing rate
#define TELEM_TIMEOUT_MS 300        // Link lost threshold
#define DISPLAY_UPDATE_MS 20        // 50 Hz OLED refresh
```

### Control Tuning
```cpp
#define IIR_ALPHA 0.15f             // Joystick smoothing (lower = smoother)
#define THR_RATE_SCALE 0.6f         // Throttle climb rate
#define DEADZONE_THRESHOLD 20       // ADC deadzone
#define SHORT_PRESS_MS 500          // ARM toggle threshold
#define LONG_PRESS_MS 1500          // Display view toggle
```

### UART Mode (Telemetry Forwarding)
```cpp
#define UART_BAUD_RATE 115200
// Uncomment to enable binary telemetry forwarding by default:
// #define UART_MODE_TELEMETRY_BINARY
```

---

## GPIO Pin Mapping (ESP32-C3)

**DO NOT change pins without updating `include/pins.h`**

| Function | GPIO | Type | Notes |
|----------|------|------|-------|
| OLED SDA | 8 | I²C | SSD1306, addr 0x3C |
| OLED SCL | 9 | I²C | 400 kHz |
| THROTTLE | 0 | ADC1_CH0 | 1kΩ series + 100nF to GND |
| YAW | 1 | ADC1_CH1 | RC filter |
| PITCH | 4 | ADC1_CH4 | RC filter |
| ROLL | 2 | ADC1_CH2 | RC filter |
| ARM/MODE BTN | 7 | INPUT_PULLUP | Button to GND |

**ADC Notes:**
- 12-bit resolution (0-4095)
- RC filter per axis: 1kΩ series + 100nF to GND at pin
- Average 8 samples per read for noise reduction
- Calibration: 64 samples per axis

---

## Coding Conventions

### Logging
**Always use categorized logging:**
```cpp
LOG_ERROR(SYSTEM, "Critical: %s", msg);      // Always visible
LOG_INFO(RADIO, "Connected to %02X:...", mac[0]);  // Default ON
LOG_DEBUG(TELEM, "ATT seq=%u", seq);          // Default OFF for TELEM
```

**Categories:** SYSTEM, RADIO, TELEM, INPUTS, OLED

### Naming
- **Types**: PascalCase (`RcPacket`, `TelemetryAttitude`)
- **Functions**: camelCase (`sendPacket()`, `hasNewEnhancedTelemetry()`)
- **Constants**: UPPER_SNAKE_CASE (`PACKET_RATE_HZ`)
- **Globals**: `g_` prefix (`g_app`, `g_forceDisarmActive`)

### Packet Structures
**ALWAYS use `__attribute__((packed))`:**
```cpp
struct __attribute__((packed)) RcPacket {
    // ...
};
```
This ensures no padding, making size deterministic for CRC and transmission.

### Timing
**NEVER use `delay()`**. Use `Every` pattern:
```cpp
static Every myTimer(100ms);
if (myTimer.check()) {
    // Do periodic task
}
```

---

## Safety Constraints

### DO NOT
- ❌ **Modify pin assignments** without updating `pins.h` AND hardware documentation
- ❌ **Change CRC algorithm** (breaks compatibility with drone)
- ❌ **Remove safety checks** (horizon, force disarm detection)
- ❌ **Disable telemetry timeout** (critical for link loss detection)
- ❌ **Hardcode MAC address** outside `config.h`
- ❌ **Use `delay()` in main loop** (breaks timing)
- ❌ **Skip CRC validation** on received packets

### ARM Logic Safety
ARM state changes only when:
1. Horizon check passes (`HRZ` flag = 1)
2. Accelerometer calibration valid (`CAL` flag = 1)
3. Not in calibration (`CALIB` flag = 0)
4. No calibration failure (`FAIL` flag = 0)

**ARM pulse:** 3 packets × 20ms = 60ms pulse to prevent accidental arming.

### Force Disarm Detection
When drone force-disarms (crash, extreme angle):
- `g_forceDisarmActive` flag set
- Warning displayed on OLED for 5 seconds
- User must acknowledge before next ARM

---

## Common Workflows

### Adding a New Telemetry Packet Type
1. **Define struct** in `protocol.h`:
   ```cpp
   struct __attribute__((packed)) TelemetryMyData {
       TelemetryHeader header;
       // Your fields here (use int16/uint16 for space efficiency)
       uint16_t crc;
   };
   ```
2. **Add enum** in `protocol.h`:
   ```cpp
   enum TelemetryPacketType {
       TELEM_TYPE_ATTITUDE = 0x01,
       // ...
       TELEM_TYPE_MY_DATA = 0x08,  // Next available
   };
   ```
3. **Extend RadioManager:**
  - Add field to `EnhancedTelemData` struct
  - Add case in `onReceiveEnhanced()` switch
4. **Update App.cpp:**
  - Parse in `telemEvery.check()` block
5. **Display (optional):**
  - Add to Normal or Debug view in `Display.cpp`

### Modifying OLED Layout
**Files:** `src/ui/Display.cpp`

**Functions:**
- `updateOledNormalView()` - 3 lines, flight data
- `updateOledDebugView()` - 3 lines, PID tuning data
- `updateOledNoTelemXXX()` - Fallback when no telemetry

**Layout constraints:**
- 128×32 pixels
- Font: 6×8 pixels → 21 chars/line
- 3 lines available (y=0, 11, 22)
- ALWAYS `display.clearDisplay()` before rendering
- ALWAYS `display.display()` after rendering

### Tuning Control Parameters
**Adjust in `config.h`, test with serial monitor:**
- `IIR_ALPHA`: 0.05-0.3 (lower = smoother, more lag)
- `THR_RATE_SCALE`: 0.3-1.0 (higher = faster throttle response)
- `ADC_SAMPLES_AXIS`: 4-16 (more = less noise, more latency)
- `DEADZONE_THRESHOLD`: 10-50 ADC units

### Debugging Telemetry Issues
```bash
# 1. Verify MAC addresses match
> M
TX MAC: A0:B7:...
Drone MAC: D8:3B:...

# 2. Check radio link quality
> D
Radio: 50 ACK (last 1s)  # Should be 50 for 100% success

# 3. Check telemetry reception
> E
Total Enhanced Packets: 5432  # Should increase continuously
ATTITUDE: 4000 rx
MOTORS: 1000 rx
STATUS: 432 rx

# 4. Enable verbose telemetry logging
log enable TELEM
# Watch for [DEBUG] TELEM: ATT: R=... logs every ~50ms
```

---

## Architecture Decisions (Why Things Are This Way)

### Enhanced Telemetry (Multi-Packet)
**Why:** Previous single-packet system (44 bytes @ 20Hz) was inefficient. Critical data (attitude) needed higher rate, while diagnostics (performance) could be slower.

**Trade-off:** More complex parsing, but 3× better bandwidth efficiency and prioritized data delivery.

### Throttle Integrator Mode
**Why:** Micro-drones are sensitive to throttle changes. Direct stick-to-throttle mapping causes jerky altitude control.

**Solution:** Stick position = rate of change. Center = hold altitude. Up/down = climb/descend at controlled rate.

**Reset:** Calibration (`C` command) resets integrator to zero.

### OLED Demo Mode
**Why:** Testing all display states manually is tedious and error-prone.

**Solution:** Automated 10-state cycle with mock data. Auto-stops on unsafe conditions (armed, throttle > 50).

**Use:** `O` command to activate, visual verification of all UI states.

### Global Modules (display, control, radio)
**Why:** Simple integration across codebase. Arduino ecosystem conventions.

**Trade-off:** Harder to unit test in isolation, but pragmatic for embedded systems.

**Alternative considered:** Full dependency injection (rejected for complexity in Arduino context).

### CRC-16/X.25
**Why:** Industry standard for drone communications. Balances error detection and computational cost.

**Details:** Polynomial 0x8408 (reflected), init 0xFFFF, final XOR 0xFFFF.

### Telemetry Forwarding System
**Why:** Need external UI dashboard (React) for advanced visualization without overloading ESP32.

**Solution:** TX forwards raw binary telemetry to UART → Python bridge → WebSocket → React UI.

**Modes:** DEBUG_TEXT for development, TELEMETRY_BINARY for UI. Runtime toggle with `U` command.

---

## Known Issues & Solutions

### Issue: Throttle Jumps at Power-Up
**Cause:** Integrator starts at center position.  
**Solution:** `control.calibrate()` resets to zero.  
**Status:** ✅ Fixed

### Issue: OLED Flickering
**Cause:** Partial updates without `clearDisplay()`.  
**Solution:** Always clear before render.  
**Status:** ✅ Fixed

### Issue: Telemetry Drops Under Load
**Cause:** ESP-NOW buffer overflow with all 7 packet types.  
**Solution:** Rate divisors (ATTITUDE 20Hz, STATUS 2.5Hz).  
**Status:** ✅ Fixed with enhanced telemetry design

### Issue: ARM Button Double-Triggers
**Cause:** No hardware debounce.  
**Solution:** Software debounce + press duration detection.  
**Status:** ✅ Implemented in ControlManager

### Issue: Stick Calibration Drift
**Cause:** Temperature, potentiometer aging.  
**Solution:** Periodic recalibration via `C` command.  
**Recommendation:** ⚠️ Calibrate before each flight session

---

## Testing Checklist

### Before Every Flight
- [ ] `M` - Verify MAC addresses match
- [ ] `C` - Calibrate sticks (hold neutral, wait for "Done")
- [ ] `D` - Check radio (>95% success rate)
- [ ] `E` - Verify telemetry (all packet types received)
- [ ] Throttle at zero after power-up
- [ ] ARM/DISARM responds (< 500ms press)
- [ ] Display toggle works (> 1500ms press)

### During Development
- [ ] `O` - Run OLED demo (verify all UI states)
- [ ] Monitor serial logs (no ERROR messages)
- [ ] Check telemetry FPS on OLED (~20 Hz)
- [ ] Verify drop indicator minimal (< 5 dots)

### After Code Changes
- [ ] `pio run` - Build succeeds
- [ ] `pio run -t upload` - Flash succeeds
- [ ] Serial monitor shows startup sequence
- [ ] OLED displays after init
- [ ] Joysticks respond (check serial logs with `log enable INPUTS`)

---

## Future Enhancement Areas

### Ready for Implementation
🔧 **Battery voltage telemetry** - Fields reserved in STATUS packet  
🔧 **RSSI measurement** - `rssi_hint` field currently 0  
🔧 **Magnetometer support** - `mag_mgauss` fields exist in SENSORS packet

### Needs Design Work
🔧 **Adaptive rate control** - Adjust telemetry rates based on link quality  
🔧 **Data compression** - Flag defined but not implemented  
🔧 **ACK system** - `ack_req` flag reserved for future  
🔧 **Non-volatile storage** - Persist stick calibration across power cycles

### External Integrations
🔧 **Python bridge** - Parse binary telemetry from UART → WebSocket  
🔧 **React UI dashboard** - Real-time artificial horizon, motor indicators, graphs

**See:** `.claude/TELEMETRY_SYSTEM_DESIGN.md` for detailed design docs

---

## When You Get Stuck

### No Telemetry
1. Check MAC addresses: `M`
2. Verify both devices on channel 1
3. Check drone firmware is sending (magic byte 0x5B)
4. Look for `[RECV]` messages in serial
5. Run `E` - should show packet counts increasing

### Erratic Control
1. Recalibrate: `C`
2. Verify RC filters in hardware (1kΩ + 100nF per axis)
3. Check 3.3V rail stability (multimeter on ESP VCC pin)
4. Adjust `IIR_ALPHA` in config.h (try 0.1-0.2 for smoother)
5. Keep joystick wires away from I²C/antenna

### High Packet Loss
1. Check radio diagnostics: `D` (should be >95% ACK rate)
2. Reduce distance (ESP-NOW range ~50m indoor)
3. Check for Wi-Fi interference (try different channel)
4. Verify both antennas oriented properly

### OLED Not Working
1. I²C scan: Look for 0x3C or 0x3D in startup logs
2. Check wiring: SDA=GPIO8, SCL=GPIO9
3. Verify 3.3V to OLED VCC
4. Run demo: `O` (cycles through all states)

### Need More Context
- Read `docs/transmitter/*.md` files (detailed specs)
- Check `include/config.h` (all tunable parameters)
- Look at `src/app/App.cpp` (main loop and integration)
- Review commit history for recent changes

---

## Reference Documentation

**Hardware:**
- `docs/transmitter/transmitter_hardware.md` - TX specifications
- `docs/transmitter/drone_hardware.md` - Drone specifications

**Software:**
- `docs/transmitter/telemetry.md` - Enhanced telemetry system
- `docs/transmitter/telemetry_forwarding.md` - UART forwarding
- `docs/transmitter/log_format.md` - Serial log interpretation

**External:**
- [ESP-NOW API](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c3/api-reference/network/esp_now.html)
- [ESP32-C3 Datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-c3_datasheet_en.pdf)
- [SSD1306 Controller](https://cdn-shop.adafruit.com/datasheets/SSD1306.pdf)

---

*Last updated: 2025-12-13*  
*Firmware version: Enhanced Telemetry v2 with UART Forwarding*