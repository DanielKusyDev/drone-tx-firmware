# Micro-Drone Controller – Hardware Documentation (TX)

## 1) Overview
- **MCU:** ESP32-C3 Super Mini (on-board antenna)
- **Communication:** ESP-NOW (no Wi-Fi/BLE/pairing)
- **Power:** 3×AA NiMH → LDO 3.3 V → 3V3 rail (with Schottky diode)
- **Inputs:** 2× PS2 joystick (4 axes total) + 1× ARM/MODE button
- **Display:** OLED SSD1306 128×32, I²C
- **LED:** (optional) green power LED 3.3 V

---

## 2) Block Diagram (Logical)

```
[3×AA NiMH] --(SW)--> [LDO 3.3V SPX5205] -->|1N5819|--> [3V3]
                                              Schottky

[3V3] --> ESP32-C3 Super Mini <-- I²C --> SSD1306 128x32 (SDA=GPIO8, SCL=GPIO9)
   |            | \
   |            |  \__ ADC: THR(0), YAW(1), PITCH(4), ROLL(2)  [each axis: R~1k series + C=100nF to GND]
   |            |
   |            \__ GPIO7 (ARM/MODE) — button to GND, INPUT_PULLUP
   |
   \-- (optional) green LED + 220Ω to GND
```

---

## 3) Power Supply

**Path:** 3×AA NiMH → switch → **SPX5205-3.3** → **1N5819** → **3V3** rail

- **LDO:** SPX5205-3.3 (low dropout).
  - **EN** to **VIN** (always on after power switch).
  - **NC** not connected.
- **Schottky diode 1N5819** on LDO output (towards 3V3 rail) – adds protection and slightly reduces 3V3 (typ. ~0.2-0.3 V), still acceptable for ESP32-C3 and OLED.
- **Capacitors (close to pins):**
  - **LDO VIN:** 10-47 µF + 100 nF
  - **LDO VOUT:** 22-100 µF + 100 nF
  - **At ESP:** 10-47 µF + 100 nF (local reservoir for current spikes)
  - **At OLED VCC:** 100 nF (local)
- **Practical notes:**
  - Battery wires as short as possible; narrow ground loop.
  - Choke not required, but good ground routing and capacitors minimize ripple.
  - 3×NiMH range: ~3.0-4.2 V at LDO input (depending on load and cell condition).

---

## 4) MCU Connections (ESP32-C3 Super Mini)

### 4.1. I²C (OLED)
- **SDA:** GPIO **8**
- **SCL:** GPIO **9**
- **OLED Address:** 0x3C (typical; fallback 0x3D)
- **OLED Power:** VCC=3.3 V, common GND

### 4.2. Joysticks (ADC + RC-filter on **each axis**)
- Each axis: **R≈1 kΩ** *in series* in signal line + **C=100 nF** to GND **at ADC pin**
  → f_c ≈ 1/(2π·1k·100nF) ≈ **1.6 kHz** (suppresses noise and contact bounce, doesn't limit ~kHz readings)
- **Axis mapping (final):**
  - **THR → GPIO 0** (ADC1_CH0)
  - **YAW → GPIO 1** (ADC1_CH1)
  - **PITCH → GPIO 4** (ADC1_CH4)
  - **ROLL → GPIO 2** (ADC1_CH2)
- **Joystick power:** 3.3 V, common GND

### 4.3. Button
- **ARM/MODE:** **GPIO 7**, to GND, input with **INPUT_PULLUP**
  - Short cable; optional 100 nF to GND at pin (hardware anti-bounce – unnecessary, debounce in FW).

### 4.4. LED (optional)
- **Green LED** from 3.3 V through **220 Ω** to GND (power indicator only).

---

## 5) Connectors and Wiring (Proposal)

- **BATTERY:** 2-pin JST-VH/MX or AA holder with switch in positive line.
- **OLED:** 4-pin (VCC, GND, SDA, SCL) 2.54 mm pitch; no need for twisted SDA/SCL, but route parallel and short.
- **JOYSTICKS:** 3-pin per axis (3.3 V, GND, signal) or 5/6-pin per module (common power + two axes).
- **BUTTON:** 2-pin (GND + signal).

---

## 6) Bill of Materials (BoM)

| Component | Model / Value | Notes |
|---|---|---|
| MCU | **ESP32-C3 Super Mini** | USB-C/Micro, built-in antenna |
| LDO | **SPX5205-3.3** | SOT-23-5; I_out typ. up to 150 mA |
| Diode | **1N5819** | Schottky, low drop |
| Battery | **AA NiMH ×3** | 3×AA holder, series switch |
| Capacitors | 10-47 µF (VIN), 22-100 µF (VOUT), **100 nF** (VIN/VOUT/ESP/OLED) | low-ESR recommended for larger |
| OLED | **SSD1306 128×32 I²C** | 0.91"/0.49" – 3.3 V |
| Joysticks | **PS2 x2** | 4 axes total |
| RC-filter | **R≈1 kΩ** series + **C=100 nF** to GND (per **each** axis) | C close to ADC pin |
| Button | Tact 6×6 mm | to GND, to GPIO7 |
| LED | Green + **220 Ω** | optional |

---

## 7) Assembly Tips

- **Ground:** one "thick" GND return to battery; branches as close to source (LDO) as possible.
- **Capacitors:** MLCC 100 nF **as close as possible** to VCC/GND pins of ICs (ESP, OLED); electrolytic/MLCC µF at LDO (VIN/VOUT).
- **ADC:** route axis signals away from I²C/antenna lines; **C=100 nF** *at pin*, **R≈1 kΩ** in series *close to source*.
- **I²C:** short, parallel lines; if wires >15-20 cm, consider 4.7 kΩ pull-ups (often OLED has them).
- **ESD:** for joysticks and button, consider protection (TVS) if device exposed to touch in dry environment.
- **Mounting:** OLED and joysticks on standoffs; ensure mechanical rigidity of potentiometers (joystick axes shouldn't "move" relative to board).

---

## 8) Operating Parameters and Power Budget (Approximate)

- **ESP32-C3:** ~40-120 mA (depending on clock and ESP-NOW TX)
- **OLED 128×32:** ~10-20 mA (content dependent)
- **Joysticks + rest:** ~<5 mA
**Total:** typically **<150 mA** from 3.3 V → margin for SPX5205.

---

## 9) Hardware Startup Tests

1. **Power:** 3.3 V on rail after LDO and diode (usually ~3.05-3.2 V).
2. **I²C:** I²C scanner detects OLED at **0x3C** (or 0x3D).
3. **ADC:** joysticks centered ~2048 (12-bit); edges ~0 and ~4095 (after RC-filter values stable; fluctuations ±5-20 OK).
4. **Button:** GPIO7 "LOW" when pressed (INPUT_PULLUP).
5. **ESP-NOW:** `WiFi.mode(WIFI_STA)` → check MAC; transmission on channel **1**.

---

## 10) Design Notes

- **Schottky diode 1N5819** after LDO gives extra margin when powered from programmer/USB (if ESP ever powered from USB and battery – prevents reverse current).
- **RC-filters** on axes significantly improve ADC read stability (especially on ESP32).
- **No separate status LEDs** – status shown on OLED; power LED (optional) gives quick 3V3 confirmation.
- **ESP-NOW** requires STA-MAC; remember to pair RX/TX on **same channel**.

---

## 11) Pinout — Quick Table

| Function | ESP32-C3 Pin | Notes |
|---|---:|---|
| I²C SDA | **GPIO8** | OLED SSD1306 |
| I²C SCL | **GPIO9** | OLED SSD1306 |
| THROTTLE (ADC) | **GPIO0** | R≈1 kΩ series, C=100 nF to GND |
| YAW (ADC) | **GPIO1** | same |
| PITCH (ADC) | **GPIO4** | same |
| ROLL (ADC) | **GPIO2** | same |
| ARM/MODE (BTN) | **GPIO7** | to GND, INPUT_PULLUP |
| 3V3 | — | from LDO through 1N5819 |
| GND | — | common ground |

> If you use different pin layout on your ESP32-C3 Super Mini board (different "versions" of clones), just adjust the table and wires – firmware is already configured for these GPIO numbers.

