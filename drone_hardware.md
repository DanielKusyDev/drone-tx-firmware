# Mikro‑dron FPV – dokumentacja sprzętu (ESP32‑S3 XIAO)

---

## 1) Lista komponentów (BOM)
- **FC**: Seeed XIAO ESP32‑S3 (Arduino framework)
- **IMU**: MPU‑6050 (I²C)
- **Silniki**: 4× coreless 6–7 mm + **śmigła 31 mm** (CW/CCW w parach)
- **Driver**: 4× MOSFET N‑ch (np. SI2300/AO3400/IRLML6344) + 4× **10 kΩ** (pull‑down gate) + 4× **dioda Schottky** (np. SS14) jako flyback na każdym silniku
- **Łączność**: ESP‑NOW (RX) – brak zewnętrznego radia
- **Zasilanie**: Li‑Po 1S 3.7 V; **LDO 3.3 V** dla logiki (ESP32‑S3 + IMU); silniki z VBAT
- (opcjonalnie) **Buzzer** pasywny, **LED** status; **kamera FPV AIO 5.8 GHz** (zasilanie z VBAT)

**Nadajnik (ESP32‑C3 Mini)**
- ESP32‑C3 Mini + OLED SSD1306 128×32 (I²C), 2× joystick (ADC), przycisk ARM
- ESP‑NOW (TX), kanał 1; Li‑Po 1S + LDO 3.3 V

---

## 2) Architektura – schemat blokowy
```
Li‑Po 1S (3.7 V)
  ├─> Kamera FPV AIO (5.8 GHz)  [VBAT]
  ├─> Driver MOSFET ──> 4× Silniki 6–7 mm
  │
  └─> LDO 3.3 V ──> XIAO ESP32‑S3 ── I2C ──> MPU6050
                         │
                         ├─ ESP‑NOW RX (kanał 1)
                         ├─ (opcjonalnie) Buzzer/LED
                         └─ (opcjonalnie) Telemetria/Debug (UART)

TX: Li‑Po → ESP32‑C3 → (I²C) OLED, (ADC) 2× joystick, (GPIO) ARM → ESP‑NOW TX → Dron
```

---

## 3) Połączenia – **zgodnie z firmware**

### 3.1 IMU (MPU6050 – I²C)
- **SDA → GPIO5**, **SCL → GPIO6** (I²C 400 kHz)
- VCC → 3.3 V, GND → GND
- Zalecenia: krótki I²C, 100 nF przy VCC; dystans IMU od torów mocy

### 3.2 Silniki (4×) – topologia low‑side
- Silnik → **+VBAT** (Li‑Po 1S); drugi zacisk silnika → **DRAIN MOSFET**
- **SOURCE MOSFET → GND**, **GATE → GPIO**
- **Pull‑down 10 kΩ**: GATE → GND (każdy kanał)
- **Dioda flyback** równolegle do silnika (katoda do +VBAT, anoda do DRAIN)

**Mapowanie (LEDC):**
- **M1 (Front‑Left, CW)** – GATE: **GPIO7** (LEDC CH0)
- **M2 (Front‑Right, CCW)** – GATE: **GPIO4** (LEDC CH1)
- **M3 (Rear‑Left, CW)** – GATE: **GPIO3** (LEDC CH2)
- **M4 (Rear‑Right, CCW)** – GATE: **GPIO1** (LEDC CH3)

### 3.3 PWM (LEDC)
- **Częstotliwość: 12 kHz**, **rozdzielczość: 10‑bit (0..1023)**, tryb **LOW_SPEED**
- Kanały: CH0..CH3; timer: TMR0; wspólne parametry dla wszystkich
- `T` po Serial uruchamia sekwencję testową M1→M4

### 3.4 Radio (ESP‑NOW)
- Tryb **RX**, **kanał 1**; weryfikacja pakietu: magic, version, CRC‑16/X.25

### 3.5 Zasilanie i EMC
- VBAT bezpośrednio do silników i diod flyback
- LDO 3.3 V: 1 µF + 10–22 µF po obu stronach; 100 nF lokalnie przy ESP/IMU
- Skręcone przewody silników; separacja GND mocy i logiki (gwiazda przy LDO)
- (opcjonalnie) cienka blaszka Cu pod MCU/IMU do GND (ekran)

---

## 4) Nadajnik – skrót połączeń (ESP32‑C3 Mini)
- **OLED SSD1306 (I²C)**: SDA=GPIO8, SCL=GPIO9; VCC 3.3 V, GND
- **Joysticki (ADC)**: THR=GPIO0, YAW=GPIO1, ROLL=GPIO2, PITCH=GPIO4
- **ARM (przycisk)**: GPIO7 (INPUT_PULLUP)
- **ESP‑NOW TX**: kanał 1, peer = MAC drona

---

## 5) Kierunki i miksowanie
- X‑frame; przód oznaczony (kamera/buzzer)
- Kierunki: **M1 FL – CW**, **M2 FR – CCW**, **M3 RL – CW**, **M4 RR – CCW**
- Śmigła zgodne z kierunkami; wszystkie pchają w dół

---

## 6) Szybka ściąga pinów (ESP32‑S3 XIAO)
| Moduł | Pin MCU | Pin modułu |
|---|---|---|
| MPU6050 SDA | **GPIO5** | SDA |
| MPU6050 SCL | **GPIO6** | SCL |
| Silnik M1 | **GPIO7 (LEDC0)** | Gate MOSFET 1 |
| Silnik M2 | **GPIO4 (LEDC1)** | Gate MOSFET 2 |
| Silnik M3 | **GPIO3 (LEDC2)** | Gate MOSFET 3 |
| Silnik M4 | **GPIO1 (LEDC3)** | Gate MOSFET 4 |
| Buzzer | GPIO2 | +BUZ |

---

