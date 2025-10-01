# Transmitter Firmware Baseline Audit
*Generated: October 1, 2025*

## Current Architecture Summary

### Project Structure
```
transmitter-firmware/
├── include/               # Headers (4 files)
│   ├── config.h          # Hardware pins, timing constants
│   ├── control.h         # Input management class interface  
│   ├── protocol.h        # RC/Telemetry packet structures
│   └── radio.h           # ESP-NOW wrapper class interface
├── src/                  # Implementation (4 files)
│   ├── main.cpp          # Main loop, OLED rendering, logging
│   ├── control.cpp       # ControlManager: joysticks, ARM button
│   ├── protocol.cpp      # CRC-16/X.25 implementation
│   └── radio.cpp         # RadioManager: ESP-NOW TX/RX
└── docs/transmitter/     # New: documentation
```

### Key Modules & Responsibilities

**main.cpp** (~600 lines)
- Main event loop with fixed 50Hz RC transmission
- OLED display management (normal/debug views)  
- Telemetry buffering and frequency calculation
- Structured logging system (Logger namespace)
- Horizon safety and ARM pulse systems

**ControlManager** (control.h/cpp)
- Joystick reading with IIR filtering (α=0.3)
- ARM button debounce and short/long press detection
- Throttle integrator mode (speed-controlled)
- Calibration (center positions only)

**RadioManager** (radio.h/cpp) 
- ESP-NOW initialization and peer management
- RC packet transmission (50Hz)
- Telemetry packet reception and parsing
- Static callbacks for ESP-NOW events

**Protocol** (protocol.h/cpp)
- RcPacket: 14-byte structure with CRC-16/X.25
- TelemetryPacket: 52-byte structure with attitude/motor data
- Bitfield helpers for armed state parsing

### Data Flow & Timing

**Main Loop (50Hz, ~20ms)**
1. Read joystick inputs → ControlInputs struct
2. Apply horizon safety logic → effectiveArmed 
3. Handle ARM pulse mechanism (3-packet bursts)
4. Build & send RC packet via ESP-NOW
5. Process incoming telemetry (if available)
6. Update OLED display (20Hz throttled)

**Telemetry Processing (10Hz expected)**
- Buffered last telemetry to prevent OLED flicker
- Timeout detection (TELEM_TIMEOUT_MS = 300ms)
- Frequency calculation with exponential smoothing

**Key Timing Constants**
- RC_RATE: 50Hz (PACKET_RATE_HZ)
- TELEMETRY_RATE: 10Hz (TELEMETRY_RATE_HZ) 
- OLED_UPDATE: 20Hz (50ms interval)
- ARM_PULSE: 3 packets (~60ms duration)

### Current Build Status
- **Build**: ✅ SUCCESS (3.80s)
- **Memory**: RAM 11.7% (38KB/327KB), Flash 57.4% (752KB/1310KB)
- **Dependencies**: Adafruit GFX/SSD1306, Wire, WiFi

### Known Features & Behavior
- **RC Protocol**: Maintains original Arduino packet layout
- **ARM Modes**: Short press=toggle, Long press=debug view switch  
- **Safety Systems**: Horizon check, throttle=0 requirement, telemetry timeout
- **OLED Anti-flicker**: Telemetry buffering eliminates view switching
- **CSV Logging**: Structured telemetry format for external tools

### Architecture Strengths
- Modular class separation (Control, Radio, Protocol)
- Centralized configuration (config.h)
- Rich telemetry integration with safety logic
- Comprehensive logging system

### Refactor Opportunities  
- main.cpp contains multiple responsibilities (OLED, logging, safety)
- Global state and tight coupling between modules
- No formal task scheduling (ad-hoc millis() checks)
- UI rendering scattered throughout main loop
- No unit test structure

---
*Next: Introduce light folder structure and extract App orchestration layer*