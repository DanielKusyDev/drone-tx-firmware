# Telemetry Forwarding System - User Guide

## Overview

The Telemetry Forwarding system enables forwarding of telemetry packets from the drone to UART in binary format, ready for processing by the Python bridge and React UI.

### Key Features

- **Two UART modes**: DEBUG_TEXT (text logs) and TELEMETRY_BINARY (binary packets)
- **Runtime switching**: Mode switching without recompilation ('U' command)
- **Selective forwarding**: Configure which packet types are forwarded
- **Statistics**: Track forwarded and dropped packets

---

## UART Operating Modes

### DEBUG_TEXT (default)
- Human-readable text logs
- Format: `[INFO] CATEGORY: message`
- Used during development and debugging
- No binary telemetry forwarding

### TELEMETRY_BINARY (for UI)
- Raw Enhanced Telemetry binary packets
- Format: compatible with protocol (magic 0x5B, version 2)
- Ready for parsing by Python bridge
- Text logs disabled (in this mode only)

---

## Configuration

### Option 1: Compile-Time (config.h)

In file [include/config.h](../../include/config.h):

```cpp
// UART Mode Configuration
// Uncomment to enable binary telemetry forwarding to UART
// Comment out for debug text mode (default)
#define UART_MODE_TELEMETRY_BINARY

// UART Configuration
#define UART_BAUD_RATE 115200
```

**To enable TELEMETRY_BINARY:**
1. Uncomment `#define UART_MODE_TELEMETRY_BINARY`
2. Build & upload firmware
3. Transmitter starts in binary mode

**To return to DEBUG_TEXT:**
1. Comment out `#define UART_MODE_TELEMETRY_BINARY`
2. Build & upload firmware

### Option 2: Runtime (serial command)

Switch without recompilation:

```bash
# In Serial Monitor (115200 baud)
U   # Toggle UART mode

# Response:
[UART] Mode: TELEMETRY_BINARY (binary packets for UI)
[UART] Text logs DISABLED - switch back with 'U' command
```

**WARNING:** When you switch to TELEMETRY_BINARY, you'll stop seeing text logs! Send 'U' again to return.

---

## Serial Commands

### U - Toggle UART Mode
Switches between DEBUG_TEXT ↔ TELEMETRY_BINARY.

**Example:**
```
> U
[UART] Mode: TELEMETRY_BINARY (binary packets for UI)
[UART] Text logs DISABLED - switch back with 'U' command

> U
[UART] Mode: DEBUG_TEXT (human-readable logs)
[UART] Binary telemetry DISABLED
```

### F - Forwarder Statistics
Displays telemetry forwarding statistics.

**Example output:**
```
> F
[FORWARDER_STATS]
UART Mode: TELEMETRY_BINARY
Forwarding Config:
  ATTITUDE: YES
  MOTORS: YES
  STATUS: YES
  CONTROL: NO
  SENSORS: NO
  SAFETY: NO
  PERFORMANCE: NO

Total Forwarded: 1523 packets
Total Dropped: 0 packets

Per-Packet Forwarded:
  ATTITUDE: 1000
  MOTORS: 250
  STATUS: 273
```

---

## Forwarding Configuration

By default, only 3 packet types are forwarded:
- **ATTITUDE** (20 Hz) - roll, pitch, yaw + rates
- **MOTORS** (5 Hz) - motor commands + throttle
- **STATUS** (2.5 Hz) - armed, safety flags, link quality

### Enabling Additional Packets

In code [src/telemetry/TelemetryForwarder.h](../../src/telemetry/TelemetryForwarder.h):

```cpp
struct ForwarderConfig {
    bool forward_attitude = true;       // ✅ Default ON
    bool forward_motors = true;         // ✅ Default ON
    bool forward_status = true;         // ✅ Default ON
    bool forward_control = false;       // ❌ Optional (10 Hz)
    bool forward_sensors = false;       // ❌ Optional (1.25 Hz)
    bool forward_safety = false;        // ❌ Optional (1.25 Hz)
    bool forward_performance = false;   // ❌ Optional (0.625 Hz)
};
```

**To enable additional packets:**
1. Change `false` to `true` for the desired type
2. Rebuild & upload firmware
3. Verify with `F` command that configuration changed

**Why disabled by default?**
- Reduces UART bandwidth
- UI often only needs basic data (ATT, MOT, STA)
- Can enable only when needed (e.g., CONTROL for PID tuning)

---

## Data Flow

```
┌─────────────────────┐
│  Drone (ESP32-S3)   │
│  Flight Controller  │
└──────────┬──────────┘
           │ ESP-NOW (Enhanced Telemetry)
           │ Packets: ATT, MOT, STA, CTL, ...
           ▼
┌─────────────────────┐
│ Transmitter (C3)    │
│ RadioManager        │
└──────────┬──────────┘
           │
           ▼
    TelemetryForwarder
    ┌─────────────────┐
    │ if (TELEM_BIN)  │
    │   forward()     │
    └────────┬────────┘
             │ UART 115200 baud
             │ Raw binary packets
             ▼
    ┌─────────────────┐
    │ Python Bridge   │
    │ Parser + WS     │
    └────────┬────────┘
             │ WebSocket (JSON)
             ▼
    ┌─────────────────┐
    │  React UI       │
    │  Dashboard      │
    └─────────────────┘
```

---

## Packet Rates

| Packet Type | Rate      | Size | Forward Default |
|-------------|-----------|------|-----------------|
| ATTITUDE    | 20 Hz     | 24 B | ✅ YES          |
| CONTROL     | 10 Hz     | 30 B | ❌ NO           |
| MOTORS      | 5 Hz      | 31 B | ✅ YES          |
| STATUS      | 2.5 Hz    | 24 B | ✅ YES          |
| SENSORS     | 1.25 Hz   | 30 B | ❌ NO           |
| SAFETY      | 1.25 Hz   | 20 B | ❌ NO           |
| PERFORMANCE | 0.625 Hz  | 22 B | ❌ NO           |

**Bandwidth estimation (default configuration):**
```
ATTITUDE: 20 Hz × 24 B = 480 B/s
MOTORS:   5 Hz × 31 B  = 155 B/s
STATUS:   2.5 Hz × 24 B = 60 B/s
─────────────────────────────────
Total:                   ~695 B/s (~7% of 115200 baud)
```

---

## Troubleshooting

### Problem: No data in Python bridge

**Checklist:**
1. Is UART mode = TELEMETRY_BINARY? (`F` command)
2. Is drone sending telemetry? (`E` command - check RX packets)
3. Is COM port correct in Python bridge?
4. Is baud rate = 115200?
5. Are packets being forwarded? (`F` command - Total Forwarded > 0)

**Debug steps:**
```bash
# 1. Check UART mode
> F
[FORWARDER_STATS]
UART Mode: TELEMETRY_BINARY  # <-- Should be TELEMETRY_BINARY

# 2. Check telemetry reception
> E
Total Enhanced Packets: 5432  # <-- Should increase

# 3. Check forward counter
> F
Total Forwarded: 5432 packets  # <-- Should increase with RX

# 4. If Total Forwarded = 0:
> U  # Switch to TELEMETRY_BINARY
```

### Problem: "Total Dropped" > 0

**Possible causes:**
1. **UART buffer overflow** - Python bridge not reading fast enough
2. **Too many packets** - enable only needed types (ATT, MOT, STA)
3. **Slow Serial.write()** - normal at very high rates

**Solution:**
- Disable unnecessary packet types (CONTROL, SENSORS, etc.)
- Check if Python bridge has parsing delays
- Increase Python bridge thread priority

### Problem: Seeing binary garbage in Serial Monitor

**This is normal!** When UART mode = TELEMETRY_BINARY, raw binary packets go to UART.

**Solution:**
- Switch to DEBUG_TEXT: send `U` command
- Or use hex dump in serial monitor to verify packets
- Or run Python bridge which parses binary

**How to verify binary is correct?**
```bash
# In Serial Monitor with hex view:
5B 02 01 00 2A 00 ...  # Magic 0x5B, Version 0x02, Type 0x01 (ATTITUDE)
```

### Problem: Logs appear despite TELEMETRY_BINARY

**Reasons:**
1. ERROR logs always sent (even in TELEMETRY_BINARY)
2. 'U' / 'F' commands send text response

**This is intentional:**
- ERROR logs are critical and must be visible
- Serial commands always send text response
- Only regular INFO/DEBUG logs are disabled

---

## Usage Examples

### Example 1: Development & Debug

```bash
# 1. Start in DEBUG_TEXT mode (default)
# 2. Check that telemetry works
> E
Total Enhanced Packets: 1234

# 3. Monitor telemetry logs
log enable TELEM
[DEBUG] TELEM: ATT: R=5.23 P=-2.14 ...
```

### Example 2: Launch UI

```bash
# 1. Switch to TELEMETRY_BINARY
> U
[UART] Mode: TELEMETRY_BINARY

# 2. Check forward stats
> F
Total Forwarded: 523 packets

# 3. Launch Python bridge
python main.py -p COM3 -b 115200

# 4. Open React UI
# Dashboard should update
```

### Example 3: Debug Forward Issues

```bash
# 1. Check that drone is sending
> E
Total Enhanced Packets: 5000  # OK - drone sending

# 2. Check forward counter
> F
Total Forwarded: 0 packets    # Problem! Nothing forwarding

# 3. Check UART mode
UART Mode: DEBUG_TEXT         # Aha! Need to switch

# 4. Switch to binary
> U
[UART] Mode: TELEMETRY_BINARY

# 5. Check again
> F
Total Forwarded: 234 packets  # Working!
```

---

## API Reference

### TelemetryForwarder Class

```cpp
class TelemetryForwarder {
public:
    void init(RadioManager* radio);
    void setUartMode(UartMode mode);
    UartMode getUartMode() const;
    void setConfig(const ForwarderConfig& config);
    void update();  // Call from main loop

    // Statistics
    uint32_t getForwardedCount() const;
    uint32_t getDroppedCount() const;
    uint32_t getForwardedCount(TelemetryPacketType type) const;
};
```

**Used in:** [src/app/App.cpp](../../src/app/App.cpp)

**Initialization:**
```cpp
m_telemForwarder.init(&radio);
m_telemForwarder.setUartMode(UartMode::TELEMETRY_BINARY);
```

**Main loop:**
```cpp
// Called every loop() iteration (~1000 Hz)
m_telemForwarder.update();
```

---

## Next Steps

### Python Bridge

The next step is implementing the Python bridge to parse packets:

1. **Serial Reader** - reads UART in thread
2. **Packet Parser** - parses binary packets, validates CRC
3. **WebSocket Server** - broadcasts to React UI

**See:** `.claude/TELEMETRY_SYSTEM_DESIGN.md` section 6

### React UI

Frontend for telemetry visualization:

1. **Artificial Horizon** - roll/pitch from ATTITUDE
2. **Motor Indicators** - bar charts from MOTORS
3. **Status Display** - armed, flags, link quality from STATUS

**See:** `.claude/TELEMETRY_SYSTEM_DESIGN.md` section 7

---

## Changelog

### v1.0 (2025-12-03)
- ✅ Initial implementation of TelemetryForwarder
- ✅ UART mode switching (DEBUG_TEXT / TELEMETRY_BINARY)
- ✅ Runtime mode toggle via 'U' command
- ✅ Forwarder statistics via 'F' command
- ✅ Selective packet forwarding (ATT, MOT, STA by default)

---

*Document created: 2025-12-03*
*Last updated: 2025-12-03*
