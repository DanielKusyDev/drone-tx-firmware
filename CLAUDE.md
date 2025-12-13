# RC Transmitter Firmware - Kontekst Projektu

## Przegląd Ogólny

**RC Transmitter Firmware** to zaawansowany firmware nadajnika RC dla drona ESP32, zbudowany w środowisku PlatformIO dla ESP32-C3. System zapewnia dwukierunkową komunikację z dronem przez protokół ESP-NOW z profesjonalną telemetrią i interfejsem użytkownika.

### Podstawowe Informacje
- **Platforma**: ESP32-C3 Super Mini (USB-C, wbudowana antena)
- **Framework**: Arduino + PlatformIO
- **Komunikacja**: ESP-NOW (peer-to-peer, kanał 1)
- **Display**: SSD1306 128×32 OLED (I²C)
- **Częstotliwość RC**: 50 Hz (20ms interval)
- **System telemetrii**: Enhanced Multi-Packet (7 typów pakietów)

---

## Architektura Projektu

### Struktura Katalogów
```
transmitter-firmware/
├── src/
│   ├── main.cpp              # Entry point, setup/loop
│   ├── app/
│   │   └── App.cpp           # Główna logika aplikacji (RC, telemetria, OLED)
│   ├── hal/
│   │   └── control.cpp       # ControlManager: joysticki, przyciski, kalibracja
│   ├── radio/
│   │   └── radio.cpp         # RadioManager: ESP-NOW TX/RX, telemetria
│   ├── ui/
│   │   └── Display.cpp       # Funkcje renderowania OLED (Normal/Debug views)
│   ├── utils/
│   │   └── protocol.cpp      # CRC-16, packet validation
│   └── logger.cpp            # System logowania z filtrowaniem (INFO/DEBUG/ERROR)
│
├── include/
│   ├── config.h              # Wszystkie konfiguracje (piny, częstotliwości, limity)
│   ├── pins.h                # Mapowanie pinów GPIO
│   ├── protocol.h            # Definicje pakietów (RcPacket, TelemetryPackets)
│   ├── control.h             # Interfejs ControlManager
│   ├── radio.h               # Interfejs RadioManager
│   └── logger.h              # System logowania
│
├── docs/
│   └── transmitter/
│       ├── telemetry.md      # Dokumentacja systemu telemetrii
│       ├── log_format.md     # Format logów i interpretacja
│       ├── drone_hardware.md # Sprzęt drona (ESP32-S3, MPU6050)
│       └── transmitter_hardware.md  # Sprzęt TX (ESP32-C3, joysticki, OLED)
│
├── .claude/                  # Dokumenty planowania Claude
├── platformio.ini            # Konfiguracja PlatformIO
└── README.md                 # Dokumentacja użytkownika
```

---

## Hardware Setup

### Transmitter (ESP32-C3 Super Mini)
**Zasilanie:**
- 3× AA NiMH → LDO SPX5205-3.3V → Schottky 1N5819 → 3.3V rail
- Capacitors: 10-47µF (VIN), 22-100µF (VOUT), 100nF (decoupling)

**GPIO Mapping:**
| Funkcja | Pin | Typ | Szczegóły |
|---------|-----|-----|-----------|
| OLED SDA | GPIO 8 | I²C | SSD1306 128×32, addr 0x3C |
| OLED SCL | GPIO 9 | I²C | 400 kHz |
| THROTTLE | GPIO 0 | ADC1_CH0 | 1kΩ series + 100nF to GND |
| YAW | GPIO 1 | ADC1_CH1 | RC filter |
| PITCH | GPIO 4 | ADC1_CH4 | RC filter |
| ROLL | GPIO 2 | ADC1_CH2 | RC filter |
| ARM/MODE | GPIO 7 | INPUT_PULLUP | Button to GND |

**Kontrola:**
- **Throttle**: Integrator mode (stick → rate of change, 0-1000)
- **Yaw/Pitch/Roll**: Proportional mode (stick → direct value, ±1000)
- **ARM Button**:
  - Short press (< 500ms): Toggle ARM/DISARM
  - Long press (> 1500ms): Toggle display view (Normal ↔ Debug)

### Drone (ESP32-S3 XIAO)
**Sprzęt:**
- FC: ESP32-S3 XIAO
- IMU: MPU-6050 (I²C, GPIO5/6)
- Silniki: 4× coreless 6-7mm, 31mm propellers
- Driver: 4× N-ch MOSFET (SI2300/AO3400) + 10kΩ pull-down + Schottky flyback
- Power: 1S Li-Po → LDO 3.3V (logic), VBAT (motors)

**Motor Mapping (X-frame):**
- M1 (FL, CW): GPIO7 (LEDC CH0)
- M2 (FR, CCW): GPIO4 (LEDC CH1)
- M3 (RL, CW): GPIO3 (LEDC CH2)
- M4 (RR, CCW): GPIO1 (LEDC CH3)

---

## Protokoły Komunikacyjne

### RC Packet (TX → Drone, 50 Hz)
**Struktura (16 bajtów):**
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

### Enhanced Telemetry System (Drone → TX)
System wielopakietowy z różnymi częstotliwościami dla różnych danych.

**Magic Byte**: `0x5B`, Version: `2`

**Typy pakietów:**
| Type ID | Name | Rate | Size | Zawartość |
|---------|------|------|------|-----------|
| 0x01 | ATTITUDE | 20 Hz | 24B | Roll/pitch/yaw angles & rates |
| 0x02 | CONTROL | 10 Hz | 30B | Setpoints, PID outputs, gain scaling |
| 0x03 | MOTORS | 5 Hz | 31B | Motor commands & actual outputs |
| 0x04 | STATUS | 2.5 Hz | 24B | Armed, mode, safety flags, link quality |
| 0x05 | SENSORS | 1.25 Hz | 30B | Raw IMU data (accel, gyro, mag) |
| 0x06 | SAFETY | 1.25 Hz | 20B | Ground confidence, error flags |
| 0x07 | PERFORMANCE | 0.625 Hz | 22B | Loop timing, CPU usage, heap |

**Wspólny Header (10 bajtów):**
```cpp
struct TelemetryHeader {
    uint8_t magic;           // 0x5B
    uint8_t version;         // 2
    uint8_t type;            // TelemetryPacketType (0x01-0x07)
    uint8_t flags;           // COMPRESSED, ACK_REQ
    uint16_t seq;            // Sequence per packet type
    uint32_t timestamp_us;   // Microsecond timestamp
};
```

**Przykład: TelemetryAttitude (najczęściej używany):**
```cpp
struct TelemetryAttitude {
    TelemetryHeader header;
    int16_t roll_deg_x100;      // ×0.01° resolution
    int16_t pitch_deg_x100;     // ×0.01° resolution
    int16_t yaw_deg_x100;       // ×0.01° resolution
    int16_t roll_rate_dps_x10;  // ×0.1°/s resolution
    int16_t pitch_rate_dps_x10;
    int16_t yaw_rate_dps_x10;
    uint16_t crc;               // CRC-16/X.25
};
```

**Safety Flags (w pakiecie STATUS):**
```cpp
#define TELEM_HORIZON_BIT      0x01  // Horizon/level OK
#define TELEM_LINK_ALIVE       0x02  // Link alive
#define TELEM_FORCE_DISARM     0x04  // Force disarm active
#define TELEM_FLAG_CAL_OK      0x08  // Accelerometer calibrated
#define TELEM_FLAG_CALIBRATING 0x10  // Calibration in progress
#define TELEM_FLAG_CAL_FAILED  0x20  // Calibration failed
#define TELEM_ARMED_BIT        0x01  // (in armed field)
```

---

## Kluczowe Komponenty

### 1. App (src/app/App.cpp)
**Odpowiedzialność:**
- Główna pętla aplikacji (50 Hz RC, 20 Hz OLED, 10 Hz telemetry processing)
- Integracja wszystkich modułów (control, radio, display)
- Obsługa komend szeregowych (M, O, C, D, E, T)
- Safety logic (horizon check, force disarm detection)
- ARM pulse countdown (3 packets = 60ms)

**Kluczowe metody:**
- `init()`: Inicjalizacja wszystkich systemów (Serial, I²C, OLED, Radio, Control)
- `loop()`: Main event loop z timingiem (Every, FlashTimer)
- `handleSerialCommands()`: Komendy diagnostyczne i konfiguracyjne

**Timing (using Every pattern):**
```cpp
static Every rcEvery(20ms);      // 50 Hz RC packet TX
static Every oledEvery(50ms);    // 20 Hz OLED update
static Every telemEvery(100ms);  // 10 Hz telemetry processing
```

### 2. RadioManager (src/radio/radio.cpp)
**Odpowiedzialność:**
- ESP-NOW TX/RX (channel 1)
- Wysyłanie pakietów RC z ack tracking
- Odbieranie enhanced telemetry (7 typów pakietów)
- CRC validation, sequence tracking, drop detection
- Statistics (TX success/fail, RX per-packet-type)

**Kluczowe API:**
```cpp
bool init(uint8_t channel);
bool setPeerMac(const uint8_t* mac);
bool sendPacket(const void* data, size_t len);
bool hasNewEnhancedTelemetry();
const EnhancedTelemData& getEnhancedTelemetry();
uint32_t getSendSuccessCount();
uint32_t getTotalEnhancedDrops();
```

**EnhancedTelemData struct:**
Agreguje wszystkie typy telemetrii + timestampy odbioru (xxx_rx_ms).

### 3. ControlManager (src/hal/control.cpp)
**Odpowiedzialność:**
- Odczyt joysticków (ADC, averaging, IIR filtering)
- Kalibracja center points (64 samples per axis)
- ARM button debouncing (press duration detection)
- Throttle integrator logic
- Debug view toggle (long press detection)

**ControlInputs struct:**
```cpp
struct ControlInputs {
    uint16_t throttle;         // 0..1000 (integrator output)
    int16_t yaw, pitch, roll;  // ±1000 (proportional)
    bool armed;                // ARM state
    bool calibButtonPressed;   // Calibration request
    bool debugView;            // Normal/Debug display toggle
};
```

**Timing Parameters:**
- `SHORT_PRESS_MS = 500`: ARM toggle threshold
- `LONG_PRESS_MS = 1500`: Display toggle threshold
- `IIR_ALPHA = 0.15`: Joystick smoothing (lower = smoother)
- `THR_RATE_SCALE = 0.6`: Throttle rate multiplier

### 4. Display (src/ui/Display.cpp)
**Dwa tryby wyświetlania:**

**Normal View (linia po linii, 128×32):**
```
Line 1: ARM: ON  THR: 450
Line 2: R: 12.3  P: -5.4
Line 3: YR: 45  FPS: 25 [drop dot if ≥5]
```

**Debug View (dla tuningu PID):**
```
Line 1: setR: 12.3 setP: -5.4
Line 2: rateR: 45  rateP: -23
Line 3: outR: 123 outP:-45 Y:67
```

**Wskaźniki statusu:**
- `LINK LOST!`: Flash when telemetry timeout (> 300ms)
- `HORIZ?`: Pokazuje gdy horizon flag OFF
- `CALIB...`: Podczas kalibracji akcelerometru
- `CAL FAIL!`: Gdy kalibracja niepowodzenie
- Drop indicator: Mała kropka za każde 5 utraconych pakietów

### 5. Logger (src/logger.cpp)
**System logowania z kategoryzacją i filtrowaniem.**

**Kategorie:**
- SYSTEM, RADIO, TELEM, INPUTS, OLED

**Poziomy:**
- ERROR (zawsze aktywne)
- INFO (domyślnie włączone)
- DEBUG (domyślnie wyłączone dla TELEM)

**API:**
```cpp
LOG_ERROR(category, format, ...);
LOG_INFO(category, format, ...);
LOG_DEBUG(category, format, ...);
```

**Komendy szeregowe:**
- `log enable <category>`: Włącz DEBUG dla kategorii
- `log disable <category>`: Wyłącz kategorię
- `log status`: Pokaż aktywne kategorie

### 6. OLED Demo Mode (OledDemo class)
**Cykl demonstracyjny (10 stanów × 2s = 20s):**
1. No Telemetry Normal View
2. No Telemetry Flash Warning
3. No Telemetry Debug View
4. Normal View with Telemetry
5. Normal Flash Warning
6. Normal Status Indicator
7. Calibrating
8. Calibration Failed
9. Debug View (PID tuning)
10. Debug View with Drops

**Safety:**
- Auto-stop gdy: `inputs.armed`, `throttle > 50`, lub `drone armed`
- Używa mock data (bezpieczne wartości)

**Aktywacja:** Serial command `O`

---

## Inicjalizacja Systemu (Sekwencja Startowa)

### setup() Flow
```
main.cpp::setup()
  ├─> RadioManager::setErrorLogger()  // Dependency injection
  └─> g_app.init()
        ├─> Serial.begin(115200)
        ├─> Logger::init()
        ├─> Wire.begin()                // I²C dla OLED
        ├─> display.begin(0x3C)         // SSD1306 init
        ├─> radio.init(channel=1)       // ESP-NOW setup
        ├─> radio.setPeerMac(drone_mac) // Peer registration
        ├─> control.init()              // GPIO setup, ADC config
        └─> control.calibrate()         // Center calibration (64 samples)
```

### loop() Flow (50 Hz)
```
main.cpp::loop()
  └─> g_app.loop()
        ├─> handleSerialCommands()      // M, O, C, D, E, T
        ├─> control.readInputs()        // Joysticks + button
        ├─> Safety logic                // Horizon, force disarm detection
        │
        ├─> [Every 20ms] RC TX          // 50 Hz
        │     ├─> buildRcPacket()
        │     ├─> radio.sendPacket()
        │     └─> [Every 1s] Log TX stats
        │
        ├─> [Every 100ms] Telemetry RX  // 10 Hz processing
        │     ├─> radio.hasNewEnhancedTelemetry()
        │     ├─> Parse ATTITUDE, CONTROL, MOTORS, STATUS
        │     └─> LOG_DEBUG(TELEM, ...)
        │
        └─> [Every 50ms] OLED Update    // 20 Hz
              ├─> OledDemo check (if active)
              ├─> updateOledNormalView() or
              └─> updateOledDebugView()
```

---

## Konfiguracja i Parametry

### Kluczowe Definicje (include/config.h)

**Komunikacja:**
```cpp
#define ESPNOW_CHANNEL 1
#define PACKET_RATE_HZ 50           // RC TX rate
#define TELEMETRY_RATE_HZ 10        // Processing rate
#define TELEM_TIMEOUT_MS 300        // 3× missed packets
```

**ADC:**
```cpp
#define ADC_RESOLUTION 12           // 0-4095
#define ADC_ATTENUATION ADC_11db    // Full range
#define ADC_SAMPLES_AXIS 8          // Noise reduction
#define ADC_SAMPLES_CAL 64          // Calibration precision
```

**Control:**
```cpp
#define DEADZONE_THRESHOLD 20
#define IIR_ALPHA 0.15f             // Smooth joystick
#define THR_DEADZONE 50
#define THR_RATE_SCALE 0.6f         // Throttle climb rate
```

**Timing:**
```cpp
#define SHORT_PRESS_MS 500          // ARM threshold
#define LONG_PRESS_MS 1500          // View toggle
#define DISPLAY_UPDATE_MS 20        // 50 Hz OLED
#define ARM_PULSE_PACKETS 3         // 60ms ARM pulse
```

**Drone MAC Address:**
```cpp
#define DEFAULT_DRONE_MAC {0xD8, 0x3B, 0xDA, 0x74, 0x83, 0x68}
```

---

## Komendy Szeregowe (115200 baud)

### Podstawowe Komendy
| Command | Opis |
|---------|------|
| **M** | Wyświetl MAC address TX i drona |
| **O** | Toggle OLED demo mode (10 stanów) |
| **C** | Manual stick calibration (hold neutral) |
| **D** | Radio diagnostics (TX/RX stats, success rate) |
| **E** | Enhanced telemetry stats (per-packet-type breakdown) |
| **T** | Toggle enhanced telemetry mode (ON/OFF) |

### Logger Commands
```bash
log status                  # Show active categories
log enable TELEM            # Enable DEBUG for TELEM
log disable INPUTS          # Disable INPUTS category
log quiet                   # Disable all DEBUG
log verbose                 # Enable all categories
```

### Przykładowy Output
```
[INFO] SYSTEM: Transmitter starting up...
[INFO] RADIO: Initializing ESP-NOW radio (channel 1)...
[DEBUG] TELEM: ATT: R=6.45 P=3.80 Y Rate=97.90 seq=402
[DEBUG] RADIO: RC: queued seq=1699, 50 ACK (last 1s)
```

---

## Format Logów (Interpretacja)

### TEL: Telemetry Logs
**ATT (Attitude, 20 Hz):**
```
TEL: ATT: R=6.45 P=3.80 Y Rate=97.90 seq=402
```
- R: Roll angle (degrees, ×0.01 resolution)
- P: Pitch angle (degrees, ×0.01 resolution)
- Y Rate: Yaw rate (deg/s, ×0.1 resolution)

**CTL (Control, 10 Hz):**
```
TEL: CTL: setR=0.00 setP=0.00 setYR=0.0 rateSetR=0.0 rateSetP=0.0 outR=0.0 outP=0.0 outY=0.0 thrScale=1.00 seq=200
```
- setR/P: Angle setpoints z RC (degrees)
- setYR: Yaw rate setpoint z RC (deg/s)
- rateSetR/P: Rate setpoints z angle PID (deg/s)
- outR/P/Y: PID outputs (×10 scaling)
- thrScale: Throttle-dependent gain scaling

**MOT (Motors, 5 Hz):**
```
TEL: MOT: cmd=[2048 2048 4096 1792] act=[2048 2048 4096 1792] seq=141 THR=2162
```
- cmd: Motor commands 0-65535 (16-bit)
- act: Actual outputs (may differ if feedback)
- THR: Base throttle from RC

**STA (Status, 2.5 Hz):**
```
TEL: STA: armed=1 mode=0 link=100% uptime=23s seq=65 [ARM:1 HRZ:1 CAL:1 CALIB:0 FAIL:0 FD:0]
```
- Safety flags: ARM, HRZ (horizon OK), CAL (calibration valid), CALIB (in progress), FAIL, FD (force disarm)

### RAD: Radio Logs
```
RAD: RC: queued seq=1699, 50 ACK (last 1s)
```
- 50 ACK = perfect transmission (50 packets in 1s @ 50 Hz)
- FAIL count pokazuje problemy z linkiem

### INP: Input Logs
```
INP: Press duration: 139 ms
INP: Short press - ARM toggle
```
- Short press: < 500ms → ARM toggle
- Long press: ≥ 1500ms → Display toggle

---

## Typowe Scenariusze

### 1. Normal Flight Sequence
```
1. Drone disarmed, horizon OK, cal valid
2. User short-press ARM button (< 500ms)
3. ARM flag pulsuje przez 3 packets (60ms)
4. Drone arms successfully
5. Throttle integrator starts from zero
6. Motors spin up with throttle input
7. Telemetry shows attitude, PID outputs, motor commands
```

### 2. Display Toggle
```
1. User long-press ARM button (> 1500ms)
2. debugView flag toggles
3. OLED switches Normal ↔ Debug view
4. Normal: Angles, yaw rate, FPS
5. Debug: Setpoints, rates, PID outputs
```

### 3. Calibration Procedure
```
1. User sends 'C' command or long-press button
2. TX: "Hold sticks neutral!"
3. control.calibrate() reads 64 samples per axis
4. Center points stored in ControlManager
5. Throttle integrator resets to zero
```

### 4. Force Disarm Detection
```
1. Drone armed and flying
2. Extreme attitude or crash detected on drone
3. Drone sets TELEM_FORCE_DISARM flag in STATUS packet
4. TX detects transition: armed → disarmed + FD flag
5. g_forceDisarmActive = true
6. Warning shown on OLED for 5 seconds
```

### 5. Link Lost Recovery
```
1. Telemetry timeout > 300ms (3 missed packets)
2. OLED shows "LINK LOST!" flashing warning
3. User checks distance, interference
4. When telemetry resumes: flash stops, drop counter resets
```

---

## Debugging Workflow

### Problem: No Telemetry
**Check:**
1. `M` command → Verify TX MAC address
2. Drone firmware: Verify TX MAC address matches
3. Both on ESP-NOW channel 1
4. Serial monitor: Look for `[RECV]` messages
5. `E` command → Check per-packet-type stats
6. Drone sending magic `0x5B` packets?

**Expected:**
```
[DEBUG] TELEM: ATT: R=... (every ~50ms)
[DEBUG] TELEM: STA: armed=... (every ~400ms)
```

### Problem: Erratic Control
**Check:**
1. ADC noise: Verify RC filters (1kΩ + 100nF)
2. Power supply stability: Check 3.3V rail ripple
3. Joystick wiring: Away from I²C/antenna
4. `C` command → Recalibrate stick centers
5. Adjust `IIR_ALPHA` (lower = smoother, 0.1-0.3 range)

### Problem: High Packet Loss
**Check:**
1. `D` command → Radio diagnostics (success rate)
2. Distance between TX and drone (ESP-NOW range ~50m indoor)
3. Wi-Fi interference (channel 1 congestion)
4. Antenna orientation (both TX and RX)
5. `E` command → Per-packet-type drop rates

**Expected:** > 95% success rate

### Problem: OLED Not Working
**Steps:**
1. I²C scanner: Check address 0x3C or 0x3D
2. Verify SDA/SCL wiring (GPIO 8/9)
3. Power: 3.3V to OLED VCC
4. `O` command → Demo mode (cycles through all states)
5. Check Wire.begin() success in serial logs

---

## Najlepsze Praktyki Rozwoju

### 1. Dodawanie Nowego Packet Type do Telemetrii
**Steps:**
1. Zdefiniuj struct w `protocol.h` (z TelemetryHeader + CRC)
2. Dodaj TelemetryPacketType enum (np. 0x08)
3. RadioManager: Dodaj pole do EnhancedTelemData
4. RadioManager: Rozszerz `onReceiveEnhanced()` switch case
5. App: Dodaj parsing w `telemEvery.check()`
6. Display: Opcjonalnie dodaj do Normal/Debug view

### 2. Modyfikacja Display Layout
**Location:** `src/ui/Display.cpp`
**Functions:**
- `updateOledNormalView()`: 3 linie, normalne info
- `updateOledDebugView()`: 3 linie, dane PID
- `updateOledNoTelemXXX()`: Fallback bez telemetrii

**Tips:**
- Używaj `display.setCursor(x, y)` dla pozycjonowania
- Font size: 6×8 pikseli (21 znaków / linia przy 128px)
- 3 linie przy wysokości 32px (line 0, 11, 22)
- `display.display()` na końcu aby zaktualizować

### 3. Tuning Control Parameters
**config.h Settings:**
```cpp
// Joystick smoothing (0.05-0.3)
#define IIR_ALPHA 0.15f

// Throttle climb rate (0.3-1.0)
#define THR_RATE_SCALE 0.6f

// ADC averaging (4-16 samples)
#define ADC_SAMPLES_AXIS 8

// Deadzone (10-50 ADC units)
#define DEADZONE_THRESHOLD 20
```

**Efekty:**
- Lower IIR_ALPHA → smoother, more lag
- Higher THR_RATE_SCALE → faster throttle response
- More ADC_SAMPLES → less noise, more latency

### 4. Logger Usage
**W nowym kodzie:**
```cpp
#include "logger.h"

// Error (zawsze widoczne)
LOG_ERROR(SYSTEM, "Critical failure: %d", error_code);

// Info (domyślnie widoczne)
LOG_INFO(RADIO, "Connected to peer: %02X:%02X:...", mac[0], mac[1]);

// Debug (domyślnie wyłączone dla TELEM)
LOG_DEBUG(TELEM, "Packet received: seq=%u", seq);
```

**Enable DEBUG runtime:**
```bash
log enable RADIO    # Włącz DEBUG dla RADIO
log verbose         # Włącz wszystko
```

### 5. Testing Checklist
**Before Flight:**
- [ ] `M` → Verify MAC addresses
- [ ] `C` → Calibrate sticks (hold neutral)
- [ ] `D` → Check radio link (> 95% success)
- [ ] `E` → Verify telemetry reception (all packet types)
- [ ] `O` → Test OLED demo (all views working)
- [ ] Check throttle at zero after power-up
- [ ] ARM/DISARM toggle responds (< 500ms press)
- [ ] Display toggle works (> 1500ms press)

**During Flight:**
- [ ] Monitor telemetry FPS (should be ~20 Hz)
- [ ] Check drop indicator (should be minimal)
- [ ] Debug view: PID outputs reasonable (< 2000)
- [ ] Motor commands balanced in hover (~2000-5000 range)

---

## Znane Problemy i Rozwiązania

### Issue: Throttle Jumps at Power-Up
**Cause:** Integrator starts at center position
**Solution:** `control.calibrate()` resets throttle to zero
**Status:** Fixed in firmware

### Issue: OLED Flickering
**Cause:** Partial display updates bez clearDisplay()
**Solution:** Zawsze `display.clearDisplay()` przed renderowaniem
**Status:** Fixed in Display.cpp

### Issue: Telemetry Drops Under Load
**Cause:** ESP-NOW buffer overflow przy 7 packet types
**Solution:** Rate divisors (ATTITUDE 20Hz, STATUS 2.5Hz, etc.)
**Status:** Enhanced telemetry design solves this

### Issue: ARM Button Double-Triggers
**Cause:** Brak debounce w sprzęcie
**Solution:** Software debounce + press duration detection
**Status:** Implemented in ControlManager

### Issue: Stick Calibration Drift
**Cause:** Temperatura, starzenie się potencjometrów
**Solution:** Periodic recalibration (`C` command)
**Recommendation:** Calibrate before each session

---

## Przydatne Linki i Referencje

### ESP-NOW Documentation
- [Espressif ESP-NOW Overview](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c3/api-reference/network/esp_now.html)
- Range: ~50m indoor, ~200m outdoor (line of sight)
- Max peers: 20 (encrypted), 6 (unencrypted)
- Max packet size: 250 bytes

### Hardware Datasheets
- **ESP32-C3**: [Datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-c3_datasheet_en.pdf)
- **SSD1306**: [OLED Controller](https://cdn-shop.adafruit.com/datasheets/SSD1306.pdf)
- **MPU-6050**: [IMU Datasheet](https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Datasheet1.pdf)

### PlatformIO
- [PlatformIO Core CLI](https://docs.platformio.org/en/latest/core/index.html)
- Build: `pio run`
- Upload: `pio run -t upload`
- Monitor: `pio device monitor -b 115200`

### Related Projects
- **Crazyflie**: Drone firmware inspiracja dla control loops
- **Betaflight**: Advanced PID tuning reference
- **ArduPilot**: Professional MAVLink telemetry

---

## Notatki dla Przyszłych Sesji Claude

### Co Działa Dobrze
✅ Enhanced telemetry system (7 packet types)
✅ OLED demo mode (comprehensive testing)
✅ Logger system with filtering
✅ Integrator throttle mode
✅ Force disarm detection
✅ Per-packet-type statistics
✅ Clean architecture (App → Radio/Control/Display)

### Obszary do Rozbudowy
🔧 Battery voltage telemetry (currently placeholder)
🔧 RSSI measurement (rssi_hint currently 0)
🔧 Magnetometer support (mag_mgauss fields reserved)
🔧 Adaptive rate control (based on link quality)
🔧 Data compression (flag defined, not implemented)
🔧 Acknowledgment system (ack_req flag reserved)
🔧 Non-volatile storage (stick calibration persistence)

### Architecture Decisions
- **Dependency Injection**: RadioErrorLogger przekazywany do RadioManager (unika forward declarations)
- **Global extern**: Display, control, radio są globalne dla prostszej integracji (trade-off: testability)
- **Every pattern**: Timing bez delay() dla non-blocking operation
- **Pack pragma**: Wszystkie packety packed(1) dla deterministycznego rozmiaru
- **CRC-16/X.25**: Standard dla drone communications (polynomial 0x8408)

### Testowanie
- **OLED Demo**: 10 stanów × 2s = 20s cykl, auto-stop na unsafe conditions
- **Mock Data**: Realistic values dla wszystkich telemetry fields
- **Safety First**: Demo nie pozwala na ARM, throttle > 50, lub drone armed

---

*Dokument stworzony: 2025-12-03*
*Ostatnia aktualizacja: 2025-12-03*
*Wersja firmware: Enhanced Telemetry (Version 2)*
