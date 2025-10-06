# Kontroler do mikrodrona — dokumentacja hardware (TX)

## 1) Przegląd
- **MCU:** ESP32-C3 Super Mini (antenna on-board)
- **Łączność:** ESP-NOW (bez Wi-Fi/BLE/parowania)
- **Zasilanie:** 3×AA NiMH → LDO 3.3 V → szyna 3V3 (z diodą Schottky)
- **Wejścia:** 2× joystick PS2 (4 osie łącznie) + 1× przycisk ARM/MODE
- **Wyświetlacz:** OLED SSD1306 128×32, I²C
- **LED:** (opcjonalnie) zielona LED zasilania 3.3 V

---

## 2) Schemat blokowy (logiczny)

```
[3×AA NiMH] --(SW)--> [LDO 3.3V SPX5205] -->|1N5819|--> [3V3]
                                              Schottky

[3V3] --> ESP32-C3 Super Mini <-- I²C --> SSD1306 128x32 (SDA=GPIO8, SCL=GPIO9)
   |            | \
   |            |  \__ ADC: THR(0), YAW(1), PITCH(4), ROLL(2)  [każda oś: R~1k szereg + C=100nF do GND]
   |            |
   |            \__ GPIO7 (ARM/MODE) — przycisk do GND, INPUT_PULLUP
   |
   \-- (opcjonalnie) LED zielona + 220Ω do GND
```

---

## 3) Zasilanie

**Ścieżka:** 3×AA NiMH → włącznik → **SPX5205-3.3** → **1N5819** → szyna **3V3**

- **LDO:** SPX5205-3.3 (niski dropout).  
  - **EN** do **VIN** (cały czas włączony po włączeniu zasilania).  
  - **NC** niepodłączony.
- **Dioda Schottky 1N5819** na wyjściu LDO (kierunek do szyny 3V3) – dodaje zabezpieczenie i delikatnie obniża 3V3 (typ. ~0.2–0.3 V), co nadal jest akceptowalne dla ESP32-C3 i OLED.
- **Kondensatory (blisko pinów):**
  - **VIN LDO:** 10–47 µF + 100 nF
  - **VOUT LDO:** 22–100 µF + 100 nF
  - **Przy ESP:** 10–47 µF + 100 nF (lokalny zbiornik na szpilki prądu)
  - **Przy OLED VCC:** 100 nF (lokalny)
- **Uwagi praktyczne:**
  - Przewody baterii możliwie krótkie; pętla masy wąska.
  - Dławik nie jest wymagany, ale dobre prowadzenie masy i kondensatory minimalizują tętnienia.
  - Zakres 3×NiMH: ~3.0–4.2 V na wejściu LDO (zależnie od obciążenia i stanu ogniw).

---

## 4) Połączenia MCU (ESP32-C3 Super Mini)

### 4.1. I²C (OLED)
- **SDA:** GPIO **8**
- **SCL:** GPIO **9**
- **Adres OLED:** 0x3C (typowo; zapasowo 0x3D)
- **Zasilanie OLED:** VCC=3.3 V, GND wspólna

### 4.2. Joysticki (ADC + RC-filtr na **każdej osi**)
- Każda oś: **R≈1 kΩ** *szeregowo* w linii sygnałowej + **C=100 nF** do GND **przy pinie ADC**  
  → f_c ≈ 1/(2π·1k·100nF) ≈ **1.6 kHz** (tłumi szum i drgania styków, nie ogranicza odczytów ~kHz)
- **Mapowanie osi (ostateczne):**
  - **THR → GPIO 0** (ADC1_CH0)
  - **YAW → GPIO 1** (ADC1_CH1)
  - **PITCH → GPIO 4** (ADC1_CH4)
  - **ROLL → GPIO 2** (ADC1_CH2)
- **Zasilanie joysticków:** 3.3 V, GND wspólna

### 4.3. Przycisk
- **ARM/MODE:** **GPIO 7**, do GND, wejście z **INPUT_PULLUP**
  - Kabel krótki; opcjonalnie 100 nF do GND przy pinie (anty-bounce sprzętowy – niekonieczny, bo jest debounce w FW).

### 4.4. LED (opcjonalnie)
- **LED zielona** od 3.3 V przez **220 Ω** do GND (tylko sygnalizacja zasilania).

---

## 5) Złącza i okablowanie (propozycja)

- **BATERIA:** 2-pin JST-VH/MX lub koszyk AA z włącznikiem w linii dodatniej.
- **OLED:** 4-pin (VCC, GND, SDA, SCL) raster 2.54 mm; skrętka SDA/SCL nie jest potrzebna, ale prowadź równolegle i krótko.
- **JOYSTICKI:** 3-pin na oś (3.3 V, GND, sygnał) lub 5/6-pin na moduł (wspólne zasilanie + dwie osie).
- **PRZYCISK:** 2-pin (GND + sygnał).

---

## 6) Lista materiałowa (BoM)

| Element | Model / Wartość | Uwagi |
|---|---|---|
| MCU | **ESP32-C3 Super Mini** | USB-C/Micro, antena wbudowana |
| LDO | **SPX5205-3.3** | SOT-23-5; I_out typ. do 150 mA |
| Dioda | **1N5819** | Schottky, mały spadek |
| Bateria | **AA NiMH ×3** | koszyk 3×AA, włącznik w szeregu |
| Kondensatory | 10–47 µF (VIN), 22–100 µF (VOUT), **100 nF** (VIN/VOUT/ESP/OLED) | low-ESR wskazany dla większych |
| OLED | **SSD1306 128×32 I²C** | 0.91"/0.49" – 3.3 V |
| Joysticki | **PS2 x2** | 4 osie łącznie |
| RC-filtr | **R≈1 kΩ** szereg + **C=100 nF** do GND (na **każdą** oś) | C blisko pinu ADC |
| Przycisk | Tact 6×6 mm | do GND, do GPIO7 |
| LED | Zielona + **220 Ω** | opcjonalna |

---

## 7) Wskazówki montażowe

- **Masa:** jeden „gruby” powrót GND do baterii; rozgałęzienia jak najbliżej źródła (LDO).  
- **Kondensatory:** MLCC 100 nF **jak najbliżej** pinów VCC/GND układów (ESP, OLED); elektrolity/MLCC µF przy LDO (VIN/VOUT).  
- **ADC:** prowadź sygnały osi z dala od linii I²C/anteny; **C=100 nF** *przy pinie*, **R≈1 kΩ** w szeregu *blisko źródła*.  
- **I²C:** linie krótko, równolegle; jeżeli przewody >15–20 cm, rozważ 4.7 kΩ pull-upy (często OLED już ma).  
- **ESD:** przy joystickach i przycisku warto rozważyć ochronę (TVS) jeśli urządzenie będzie narażone na dotyk w suchym środowisku.  
- **Mocowanie:** OLED i joysticki na dystansach; zadbaj o mechaniczną sztywność potencjometrów (osie joysticków nie mogą „chodzić” względem płytki).

---

## 8) Parametry pracy i budżet prądowy (orientacyjnie)

- **ESP32-C3:** ~40–120 mA (zależnie od taktowania i TX ESP-NOW)  
- **OLED 128×32:** ~10–20 mA (treść zależna)  
- **Joysticki + reszta:** ~<5 mA  
**Razem:** typowo **<150 mA** z 3.3 V → zapas dla SPX5205.

---

## 9) Testy uruchomieniowe (hardware)

1. **Zasilanie**: 3.3 V na szynie po LDO i diodzie (zwykle ~3.05–3.2 V).  
2. **I²C**: skaner I²C wykrywa OLED na **0x3C** (ew. 0x3D).  
3. **ADC**: na środku joysticków ~2048 (12-bit); skraje ~0 i ~4095 (po RC-filtrze wartości stabilne; fluktuacje ±5–20 OK).  
4. **Przycisk**: GPIO7 „LOW” po wciśnięciu (INPUT_PULLUP).  
5. **ESP-NOW**: `WiFi.mode(WIFI_STA)` → sprawdzenie MAC; transmisja na kanale **1**.

---

## 10) Notatki projektowe

- Dioda **Schottky 1N5819** po LDO daje dodatkowy margines przy zasilaniu z programatora/USB (gdyby ESP był kiedyś zasilany z USB i z baterii – zapobiega cofaniu prądu).  
- **RC-filtry** na osiach znacząco poprawiają stabilność odczytu ADC (szczególnie w ESP32).  
- **Brak osobnych LED statusowych** – statusy wyświetlane na OLED; LED zasilania (opcjonalna) daje szybkie potwierdzenie 3V3.  
- **ESP-NOW** wymaga STA-MAC; pamiętaj, aby na RX/TX spiąć **ten sam kanał**.

---

## 11) Pinout — szybka tabela

| Funkcja | Pin ESP32-C3 | Uwagi |
|---|---:|---|
| I²C SDA | **GPIO8** | OLED SSD1306 |
| I²C SCL | **GPIO9** | OLED SSD1306 |
| THROTTLE (ADC) | **GPIO0** | R≈1 kΩ szereg, C=100 nF do GND |
| YAW (ADC) | **GPIO1** | jw. |
| PITCH (ADC) | **GPIO4** | jw. |
| ROLL (ADC) | **GPIO2** | jw. |
| ARM/MODE (BTN) | **GPIO7** | do GND, INPUT_PULLUP |
| 3V3 | — | z LDO przez 1N5819 |
| GND | — | wspólna masa |

> Jeśli używasz innego rozkładu pinów na Twojej płytce ESP32-C3 Super Mini (różne „wersje” klonów), dopasuj tylko tabelkę i przewody – firmware już masz pod te numery GPIO.

