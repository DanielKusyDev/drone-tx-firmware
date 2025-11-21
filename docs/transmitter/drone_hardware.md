# FPV Micro-Drone – Hardware Documentation (ESP32-S3 XIAO)

---

## 1) Bill of Materials (BOM)
- **FC**: Seeed XIAO ESP32-S3 (Arduino framework)
- **IMU**: MPU-6050 (I²C)
- **Motors**: 4× coreless 6-7 mm + **31 mm propellers** (CW/CCW pairs)
- **Driver**: 4× N-ch MOSFET (e.g. SI2300/AO3400/IRLML6344) + 4× **10 kΩ** (gate pull-down) + 4× **Schottky diode** (e.g. SS14) as flyback on each motor
- **Communication**: ESP-NOW (RX) – no external radio
- **Power**: Li-Po 1S 3.7 V; **LDO 3.3 V** for logic (ESP32-S3 + IMU); motors from VBAT
- (optional) Passive **Buzzer**, **LED** status; **FPV AIO 5.8 GHz camera** (powered from VBAT)

**Transmitter (ESP32-C3 Mini)**
- ESP32-C3 Mini + OLED SSD1306 128×32 (I²C), 2× joystick (ADC), ARM button
- ESP-NOW (TX), channel 1; Li-Po 1S + LDO 3.3 V

---

## 2) Architecture – Block Diagram
```
Li-Po 1S (3.7 V)
  ├─> FPV AIO Camera (5.8 GHz)  [VBAT]
  ├─> MOSFET Driver ──> 4× Motors 6-7 mm
  │
  └─> LDO 3.3 V ──> XIAO ESP32-S3 ── I2C ──> MPU6050
                         │
                         ├─ ESP-NOW RX (channel 1)
                         ├─ (optional) Buzzer/LED
                         └─ (optional) Telemetry/Debug (UART)

TX: Li-Po → ESP32-C3 → (I²C) OLED, (ADC) 2× joystick, (GPIO) ARM → ESP-NOW TX → Drone
```

---

## 3) Connections – **according to firmware**

### 3.1 IMU (MPU6050 – I²C)
- **SDA → GPIO5**, **SCL → GPIO6** (I²C 400 kHz)
- VCC → 3.3 V, GND → GND
- Recommendations: short I²C traces, 100 nF at VCC; keep IMU away from power traces

### 3.2 Motors (4×) – low-side topology
- Motor → **+VBAT** (Li-Po 1S); other motor terminal → **MOSFET DRAIN**
- **MOSFET SOURCE → GND**, **GATE → GPIO**
- **Pull-down 10 kΩ**: GATE → GND (each channel)
- **Flyback diode** parallel to motor (cathode to +VBAT, anode to DRAIN)

**Mapping (LEDC):**
- **M1 (Front-Left, CW)** – GATE: **GPIO7** (LEDC CH0)
- **M2 (Front-Right, CCW)** – GATE: **GPIO4** (LEDC CH1)
- **M3 (Rear-Left, CW)** – GATE: **GPIO3** (LEDC CH2)
- **M4 (Rear-Right, CCW)** – GATE: **GPIO1** (LEDC CH3)

### 3.3 PWM (LEDC)
- **Frequency: 12 kHz**, **resolution: 10-bit (0..1023)**, mode **LOW_SPEED**
- Channels: CH0..CH3; timer: TMR0; common parameters for all
- `T` on Serial starts test sequence M1→M4

### 3.4 Radio (ESP-NOW)
- Mode **RX**, **channel 1**; packet verification: magic, version, CRC-16/X.25

### 3.5 Power and EMC
- VBAT directly to motors and flyback diodes
- LDO 3.3 V: 1 µF + 10-22 µF on both sides; 100 nF locally at ESP/IMU
- Twisted motor wires; separate power and logic GND (star at LDO)
- (optional) thin Cu sheet under MCU/IMU to GND (shield)

---

## 4) Transmitter – connection summary (ESP32-C3 Mini)
- **OLED SSD1306 (I²C)**: SDA=GPIO8, SCL=GPIO9; VCC 3.3 V, GND
- **Joysticks (ADC)**: THR=GPIO0, YAW=GPIO1, ROLL=GPIO2, PITCH=GPIO4
- **ARM (button)**: GPIO7 (INPUT_PULLUP)
- **ESP-NOW TX**: channel 1, peer = drone MAC

---

## 5) Directions and mixing
- X-frame; front marked (camera/buzzer)
- Directions: **M1 FL – CW**, **M2 FR – CCW**, **M3 RL – CW**, **M4 RR – CCW**
- Props match directions; all push downward

---

## 6) Quick pin reference (ESP32-S3 XIAO)
| Module | MCU Pin | Module Pin |
|---|---|---|
| MPU6050 SDA | **GPIO5** | SDA |
| MPU6050 SCL | **GPIO6** | SCL |
| Motor M1 | **GPIO7 (LEDC0)** | MOSFET 1 Gate |
| Motor M2 | **GPIO4 (LEDC1)** | MOSFET 2 Gate |
| Motor M3 | **GPIO3 (LEDC2)** | MOSFET 3 Gate |
| Motor M4 | **GPIO1 (LEDC3)** | MOSFET 4 Gate |
| Buzzer | GPIO2 | +BUZ |

---

