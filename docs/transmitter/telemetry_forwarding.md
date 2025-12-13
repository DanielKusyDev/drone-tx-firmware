# Telemetry Forwarding System - User Guide

## Przegląd

System Telemetry Forwarding umożliwia przekazywanie pakietów telemetrii z drona na UART w formacie binarnym, gotowym do przetworzenia przez Python bridge i React UI.

### Kluczowe Funkcje

- **Dwa tryby UART**: DEBUG_TEXT (logi tekstowe) i TELEMETRY_BINARY (pakiety binarne)
- **Runtime switching**: Przełączanie trybów bez rekompilacji (komenda 'U')
- **Selektywne forwardowanie**: Konfiguracja które typy pakietów są przekazywane
- **Statystyki**: Śledzenie przekazanych i utraconych pakietów

---

## Tryby Pracy UART

### DEBUG_TEXT (domyślny)
- Logi tekstowe w formacie czytelnym dla człowieka
- Format: `[INFO] CATEGORY: message`
- Używany podczas development i debugowania
- Brak forwardowania binarnej telemetrii

### TELEMETRY_BINARY (dla UI)
- Surowe pakiety binarne Enhanced Telemetry
- Format: zgodny z protokołem (magic 0x5B, version 2)
- Gotowe do parsowania przez Python bridge
- Logi tekstowe wyłączone (tylko w tym trybie)

---

## Konfiguracja

### Opcja 1: Compile-Time (config.h)

W pliku [include/config.h](../../include/config.h):

```cpp
// UART Mode Configuration
// Uncomment to enable binary telemetry forwarding to UART
// Comment out for debug text mode (default)
#define UART_MODE_TELEMETRY_BINARY

// UART Configuration
#define UART_BAUD_RATE 115200
```

**Aby włączyć TELEMETRY_BINARY:**
1. Odkomentuj `#define UART_MODE_TELEMETRY_BINARY`
2. Build & upload firmware
3. Nadajnik startuje w trybie binarnym

**Aby wrócić do DEBUG_TEXT:**
1. Zakomentuj `#define UART_MODE_TELEMETRY_BINARY`
2. Build & upload firmware

### Opcja 2: Runtime (komenda szeregowa)

Przełączanie bez rekompilacji:

```bash
# W Serial Monitor (115200 baud)
U   # Toggle UART mode

# Response:
[UART] Mode: TELEMETRY_BINARY (binary packets for UI)
[UART] Text logs DISABLED - switch back with 'U' command
```

**UWAGA:** Gdy przełączysz na TELEMETRY_BINARY, przestaniesz widzieć logi tekstowe! Wyślij 'U' ponownie aby wrócić.

---

## Komendy Szeregowe

### U - Toggle UART Mode
Przełącza między DEBUG_TEXT ↔ TELEMETRY_BINARY.

**Przykład:**
```
> U
[UART] Mode: TELEMETRY_BINARY (binary packets for UI)
[UART] Text logs DISABLED - switch back with 'U' command

> U
[UART] Mode: DEBUG_TEXT (human-readable logs)
[UART] Binary telemetry DISABLED
```

### F - Forwarder Statistics
Wyświetla statystyki forwardingu telemetrii.

**Przykład output:**
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

## Konfiguracja Forwardingu

Domyślnie forwardowane są tylko 3 typy pakietów:
- **ATTITUDE** (20 Hz) - roll, pitch, yaw + rates
- **MOTORS** (5 Hz) - komendy silników + throttle
- **STATUS** (2.5 Hz) - armed, safety flags, link quality

### Włączanie Dodatkowych Pakietów

W kodzie [src/telemetry/TelemetryForwarder.h](../../src/telemetry/TelemetryForwarder.h):

```cpp
struct ForwarderConfig {
    bool forward_attitude = true;       // ✅ Domyślnie ON
    bool forward_motors = true;         // ✅ Domyślnie ON
    bool forward_status = true;         // ✅ Domyślnie ON
    bool forward_control = false;       // ❌ Opcjonalny (10 Hz)
    bool forward_sensors = false;       // ❌ Opcjonalny (1.25 Hz)
    bool forward_safety = false;        // ❌ Opcjonalny (1.25 Hz)
    bool forward_performance = false;   // ❌ Opcjonalny (0.625 Hz)
};
```

**Aby włączyć dodatkowe pakiety:**
1. Zmień `false` na `true` dla wybranego typu
2. Rebuild & upload firmware
3. Sprawdź `F` komendą że konfiguracja się zmieniła

**Dlaczego domyślnie wyłączone?**
- Zmniejsza bandwidth UART
- UI często potrzebuje tylko podstawowych danych (ATT, MOT, STA)
- Można włączyć tylko gdy potrzebne (np. CONTROL do tuningu PID)

---

## Przepływ Danych

```
┌─────────────────────┐
│  Dron (ESP32-S3)    │
│  Flight Controller  │
└──────────┬──────────┘
           │ ESP-NOW (Enhanced Telemetry)
           │ Pakiety: ATT, MOT, STA, CTL, ...
           ▼
┌─────────────────────┐
│ Nadajnik (ESP32-C3) │
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
             │ Surowe binarne pakiety
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

## Częstotliwości Pakietów

| Typ Pakietu | Częstotliwość | Rozmiar | Forward domyślnie |
|-------------|---------------|---------|-------------------|
| ATTITUDE    | 20 Hz         | 24 B    | ✅ YES            |
| CONTROL     | 10 Hz         | 30 B    | ❌ NO             |
| MOTORS      | 5 Hz          | 31 B    | ✅ YES            |
| STATUS      | 2.5 Hz        | 24 B    | ✅ YES            |
| SENSORS     | 1.25 Hz       | 30 B    | ❌ NO             |
| SAFETY      | 1.25 Hz       | 20 B    | ❌ NO             |
| PERFORMANCE | 0.625 Hz      | 22 B    | ❌ NO             |

**Bandwidth estimation (domyślna konfiguracja):**
```
ATTITUDE: 20 Hz × 24 B = 480 B/s
MOTORS:   5 Hz × 31 B  = 155 B/s
STATUS:   2.5 Hz × 24 B = 60 B/s
─────────────────────────────────
Total:                   ~695 B/s (~7% of 115200 baud)
```

---

## Troubleshooting

### Problem: Brak danych w Python bridge

**Check list:**
1. Czy UART mode = TELEMETRY_BINARY? (`F` komenda)
2. Czy dron wysyła telemetrię? (`E` komenda - sprawdź RX packets)
3. Czy port COM poprawny w Python bridge?
4. Czy baud rate = 115200?
5. Czy pakiety są forwardowane? (`F` komenda - Total Forwarded > 0)

**Debug steps:**
```bash
# 1. Sprawdź tryb UART
> F
[FORWARDER_STATS]
UART Mode: TELEMETRY_BINARY  # <-- Powinno być TELEMETRY_BINARY

# 2. Sprawdź odbiór telemetrii
> E
Total Enhanced Packets: 5432  # <-- Powinno rosnąć

# 3. Sprawdź forward counter
> F
Total Forwarded: 5432 packets  # <-- Powinno rosnąć równo z RX

# 4. Jeśli Total Forwarded = 0:
> U  # Przełącz na TELEMETRY_BINARY
```

### Problem: "Total Dropped" > 0

**Możliwe przyczyny:**
1. **UART buffer overflow** - Python bridge nie czyta wystarczająco szybko
2. **Zbyt wiele pakietów** - włącz tylko potrzebne typy (ATT, MOT, STA)
3. **Wolny Serial.write()** - normalny przy bardzo wysokich częstotliwościach

**Rozwiązanie:**
- Wyłącz niepotrzebne typy pakietów (CONTROL, SENSORS, etc.)
- Sprawdź czy Python bridge nie ma opóźnień w parsowaniu
- Zwiększ priorytet wątku Python bridge

### Problem: Widzę binarne śmieci w Serial Monitor

**To normalne!** Gdy UART mode = TELEMETRY_BINARY, na UART idą surowe binarne pakiety.

**Rozwiązanie:**
- Przełącz na DEBUG_TEXT: wyślij komendę `U`
- Lub użyj hex dump w serial monitor do weryfikacji pakietów
- Lub uruchom Python bridge który parsuje binarkę

**Jak zweryfikować że binarka jest poprawna?**
```bash
# W Serial Monitor z hex view:
5B 02 01 00 2A 00 ...  # Magic 0x5B, Version 0x02, Type 0x01 (ATTITUDE)
```

### Problem: Logi się pojawiają pomimo TELEMETRY_BINARY

**Przyczyny:**
1. Logi ERROR zawsze są wysyłane (nawet w TELEMETRY_BINARY)
2. Komenda 'U' / 'F' wysyła response w trybie tekstowym

**To jest celowe:**
- ERROR logi są krytyczne i muszą być widoczne
- Komendy szeregowe zawsze wysyłają tekstowy response
- Tylko regularne INFO/DEBUG logi są wyłączone

---

## Przykłady Użycia

### Przykład 1: Development & Debug

```bash
# 1. Start w trybie DEBUG_TEXT (domyślny)
# 2. Sprawdź że telemetria działa
> E
Total Enhanced Packets: 1234

# 3. Monitor logów telemetrii
log enable TELEM
[DEBUG] TELEM: ATT: R=5.23 P=-2.14 ...
```

### Przykład 2: Uruchomienie UI

```bash
# 1. Przełącz na TELEMETRY_BINARY
> U
[UART] Mode: TELEMETRY_BINARY

# 2. Sprawdź forward stats
> F
Total Forwarded: 523 packets

# 3. Uruchom Python bridge
python main.py -p COM3 -b 115200

# 4. Otwórz React UI
# Dashboard powinien się aktualizować
```

### Przykład 3: Debug Forward Issues

```bash
# 1. Sprawdź że dron wysyła
> E
Total Enhanced Packets: 5000  # OK - dron wysyła

# 2. Sprawdź forward counter
> F
Total Forwarded: 0 packets    # Problem! Nic nie forwarduje

# 3. Sprawdź tryb UART
UART Mode: DEBUG_TEXT         # Aha! Trzeba przełączyć

# 4. Przełącz na binary
> U
[UART] Mode: TELEMETRY_BINARY

# 5. Sprawdź ponownie
> F
Total Forwarded: 234 packets  # Działa!
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

**Używane w:** [src/app/App.cpp](../../src/app/App.cpp)

**Inicjalizacja:**
```cpp
m_telemForwarder.init(&radio);
m_telemForwarder.setUartMode(UartMode::TELEMETRY_BINARY);
```

**Main loop:**
```cpp
// Wywołanie w każdej iteracji loop() (~1000 Hz)
m_telemForwarder.update();
```

---

## Dalsze Kroki

### Python Bridge

Następnym krokiem jest implementacja Python bridge do parsowania pakietów:

1. **Serial Reader** - czyta UART w wątku
2. **Packet Parser** - parsuje binarne pakiety, waliduje CRC
3. **WebSocket Server** - broadcast do React UI

**Zobacz:** `.claude/TELEMETRY_SYSTEM_DESIGN.md` sekcja 6

### React UI

Frontend do wizualizacji telemetrii:

1. **Artificial Horizon** - roll/pitch z ATTITUDE
2. **Motor Indicators** - bar charts z MOTORS
3. **Status Display** - armed, flags, link quality z STATUS

**Zobacz:** `.claude/TELEMETRY_SYSTEM_DESIGN.md` sekcja 7

---

## Changelog

### v1.0 (2025-12-03)
- ✅ Initial implementation of TelemetryForwarder
- ✅ UART mode switching (DEBUG_TEXT / TELEMETRY_BINARY)
- ✅ Runtime mode toggle via 'U' command
- ✅ Forwarder statistics via 'F' command
- ✅ Selective packet forwarding (ATT, MOT, STA by default)

---

*Dokument utworzony: 2025-12-03*
*Ostatnia aktualizacja: 2025-12-03*
