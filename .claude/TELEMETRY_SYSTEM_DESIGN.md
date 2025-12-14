# Kompletny Projekt Techniczny Systemu Telemetrii Drona
## Enhanced Telemetry System - Full Technical Specification

**Data utworzenia:** 2025-12-03
**Wersja:** 1.0
**Status:** Ready for Implementation

---

## Spis Treści

1. [Wprowadzenie](#1-wprowadzenie)
2. [Architektura Systemu](#2-architektura-systemu)
3. [Format Protokołu Binarnego](#3-format-protokołu-binarnego)
4. [Implementacja Firmware - Nadajnik (ESP32-C3)](#4-implementacja-firmware---nadajnik-esp32-c3)
5. [Implementacja Firmware - Dron (ESP32-S3)](#5-implementacja-firmware---dron-esp32-s3)
6. [Python Bridge - Parser i WebSocket](#6-python-bridge---parser-i-websocket)
7. [React UI - Kontrakt i Integracja](#7-react-ui---kontrakt-i-integracja)
8. [Optymalizacje i Rozszerzenia](#8-optymalizacje-i-rozszerzenia)

---

## 1. Wprowadzenie

### 1.1. Cele Projektu

System telemetrii drona jest zaprojektowany do:
- **Oddzielenia logów debugowych od telemetrii maszynowej**
- **Wykorzystania istniejącego Enhanced Telemetry Protocol** (już zaimplementowanego)
- **Umożliwienia prezentacji telemetrii w czasie rzeczywistym w React UI**
- **Minimalizacji zmian w istniejącym firmware** (ewolucja, nie rewolucja)

### 1.2. Obecny Stan Implementacji

**✅ Co już istnieje:**
- Pełny protokół Enhanced Telemetry (7 typów pakietów)
- RadioManager z odbiorem ESP-NOW i parsowaniem pakietów
- Struktury danych dla wszystkich typów telemetrii
- CRC-16/X.25 walidacja pakietów
- Thread-safe przechowywanie telemetrii (FreeRTOS mutex)

**⚠️ Co wymaga implementacji:**
- Forward telemetrii z nadajnika na UART
- Tryby pracy UART (DEBUG_TEXT / TELEMETRY_BINARY)
- Python bridge do parsowania i przekazywania WebSocket
- React UI do wizualizacji telemetrii

### 1.3. Przepływ Danych (High-Level)

```
┌─────────────────┐
│  Dron (ESP32-S3) │
│  Flight Controller│
└────────┬────────┘
         │ ESP-NOW
         │ (Enhanced Telemetry Packets)
         │
         ▼
┌─────────────────┐
│ Nadajnik (C3)   │
│ RadioManager    │
└────────┬────────┘
         │ UART (115200 baud)
         │ (Binary Telemetry Stream)
         │
         ▼
┌─────────────────┐
│ Python Bridge   │
│ Serial Parser   │
└────────┬────────┘
         │ WebSocket
         │ (JSON Messages)
         │
         ▼
┌─────────────────┐
│  React UI       │
│  Dashboard      │
└─────────────────┘
```

---

## 2. Architektura Systemu

### 2.1. Komponenty Systemu

| Komponent | Platforma | Funkcja | Status |
|-----------|-----------|---------|--------|
| **Flight Controller** | ESP32-S3 | Generuje pakiety telemetrii | ✅ Zaimplementowany |
| **Transmitter** | ESP32-C3 | Odbiera ESP-NOW, forward na UART | ⚠️ Częściowy |
| **Python Bridge** | Python 3.9+ | Parser UART → WebSocket | ❌ Do implementacji |
| **React UI** | TypeScript/React | Wizualizacja telemetrii | ❌ Do implementacji |

### 2.2. Tryby Pracy UART

System wspiera dwa tryby pracy:

#### Tryb 1: DEBUG_TEXT (domyślny)
```
- Logi tekstowe na UART (printf, LOG_xxx)
- Telemetria binarna wyłączona lub ograniczona
- Format: "LOG: [kategoria] wiadomość\r\n"
- Cel: Debugowanie, development
```

#### Tryb 2: TELEMETRY_BINARY (produkcyjny)
```
- Telemetria binarna na UART (pakiety Enhanced Telemetry)
- Logi tekstowe wyłączone lub minimalne
- Format: surowe bajty binarnych pakietów
- Cel: UI, analiza lotów, blackbox
```

### 2.3. Konfiguracja Trybów

**Opcja A: Compile-time (prostsze)**
```cpp
// config.h
#define UART_MODE_TELEMETRY_BINARY  // lub zakomentować dla DEBUG_TEXT
```

**Opcja B: Runtime (elastyczniejsze)**
```cpp
// Komenda po UART: "CFG:UART=TELBIN" lub "CFG:UART=DEBUG"
// Wymaga parsera komend w firmware
```

**Rekomendacja:** Opcja A dla pierwszej implementacji, Opcja B jako future enhancement.

---

## 3. Format Protokołu Binarnego

### 3.1. Obecna Struktura Pakietów

Wszystkie pakiety Enhanced Telemetry mają wspólny format:

```
┌─────────────────────────────────────┐
│  TelemetryHeader (10 bytes)         │
├─────────────────────────────────────┤
│  magic (0x5B)                       │ 1 byte
│  version (2)                        │ 1 byte
│  type (enum TelemetryPacketType)    │ 1 byte
│  flags                              │ 1 byte
│  seq (sequence number)              │ 2 bytes (uint16_t)
│  timestamp_us                       │ 4 bytes (uint32_t)
├─────────────────────────────────────┤
│  Payload (typ-specific)             │ N bytes
├─────────────────────────────────────┤
│  crc16                              │ 2 bytes
└─────────────────────────────────────┘
```

### 3.2. Typy Pakietów i Rozmiary

| Type | Enum | Nazwa | Rozmiar | Częstotliwość |
|------|------|-------|---------|---------------|
| 0x01 | TELEM_TYPE_ATTITUDE | TelemetryAttitude | 24 bytes | 20 Hz |
| 0x02 | TELEM_TYPE_CONTROL | TelemetryControl | 30 bytes | 10 Hz |
| 0x03 | TELEM_TYPE_MOTORS | TelemetryMotors | 31 bytes | 5 Hz |
| 0x04 | TELEM_TYPE_STATUS | TelemetryStatus | 24 bytes | 2.5 Hz |
| 0x05 | TELEM_TYPE_SENSORS | TelemetrySensors | 30 bytes | 1.25 Hz |
| 0x06 | TELEM_TYPE_SAFETY | TelemetrySafety | 20 bytes | 1.25 Hz |
| 0x07 | TELEM_TYPE_PERFORMANCE | TelemetryPerformance | 22 bytes | 0.625 Hz |

### 3.3. Payload Definitions (z protocol.h)

#### 3.3.1. ATTITUDE (0x01) - 24 bytes
```cpp
struct TelemetryAttitude {
    TelemetryHeader header;      // 10 bytes
    int16_t roll_deg_x100;       // Roll angle (*100)
    int16_t pitch_deg_x100;      // Pitch angle (*100)
    int16_t yaw_deg_x100;        // Yaw angle (*100)
    int16_t roll_rate_dps_x10;   // Roll rate (*10)
    int16_t pitch_rate_dps_x10;  // Pitch rate (*10)
    int16_t yaw_rate_dps_x10;    // Yaw rate (*10)
    uint16_t crc;                // 2 bytes
};
```

**Przykładowe dane:**
```
Magic:     0x5B
Version:   0x02
Type:      0x01 (ATTITUDE)
Flags:     0x00
Seq:       0x002A (42)
Timestamp: 0x075BCD15 (123456789 µs)
Roll:      0xFC7A (-898 = -8.98°)
Pitch:     0x039C (924 = 9.24°)
Yaw:       0x0000 (0 = 0.00°)
Roll rate: 0xFF33 (-205 = -20.5°/s)
Pitch rate:0x0073 (115 = 11.5°/s)
Yaw rate:  0x0000 (0 = 0.0°/s)
CRC:       0xXXXX (calculated)
```

#### 3.3.2. MOTORS (0x03) - 31 bytes
```cpp
struct TelemetryMotors {
    TelemetryHeader header;      // 10 bytes
    uint16_t motor_cmd[4];       // Motor commands 0-1000
    uint16_t motor_actual[4];    // Actual motor outputs
    uint16_t throttle;           // Base throttle
    uint8_t mixer_table_id;      // Active mixer table
    uint16_t crc;                // 2 bytes
};
```

#### 3.3.3. STATUS (0x04) - 24 bytes
```cpp
struct TelemetryStatus {
    TelemetryHeader header;      // 10 bytes
    uint8_t armed;               // Arming state (0/1)
    uint8_t flight_mode;         // Flight mode enum
    uint8_t safety_flags;        // Bitfield (horizon, link, disarm, cal)
    uint8_t ground_state;        // Ground detection state
    uint8_t link_quality;        // RC link quality 0-100
    uint8_t battery_pct;         // Battery percentage
    uint16_t uptime_s;           // System uptime in seconds
    uint32_t loop_rate_hz_x10;   // Main loop rate (*10)
    uint16_t crc;                // 2 bytes
};
```

**Safety flags bitfield:**
```cpp
#define TELEM_HORIZON_BIT      0x01  // bit 0: horizon/level OK
#define TELEM_LINK_ALIVE       0x02  // bit 1: link alive
#define TELEM_FORCE_DISARM     0x04  // bit 2: force disarm triggered
#define TELEM_FLAG_CAL_OK      0x08  // bit 3: accel calibration valid
#define TELEM_FLAG_CALIBRATING 0x10  // bit 4: calibration in progress
#define TELEM_FLAG_CAL_FAILED  0x20  // bit 5: calibration failed
```

### 3.4. CRC-16/X.25 Validation

**Algorytm:**
```cpp
uint16_t crc16_x25(const uint8_t* data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; bit++) {
            if (crc & 1) {
                crc = (crc >> 1) ^ 0x8408;
            } else {
                crc >>= 1;
            }
        }
    }
    return crc ^ 0xFFFF;
}
```

**Zastosowanie:**
- CRC obliczane na wszystkich bajtach pakietu **z wyjątkiem** pola CRC
- Dla pakietu 24-bajtowego: CRC = crc16_x25(data, 22)
- Walidacja: `calculatedCrc == packet->crc`

---

## 4. Implementacja Firmware - Nadajnik (ESP32-C3)

### 4.1. Moduły do Implementacji

#### 4.1.1. Nowy moduł: TelemetryForwarder

**Lokalizacja:** `src/telemetry/TelemetryForwarder.h`, `src/telemetry/TelemetryForwarder.cpp`

**Odpowiedzialność:**
- Odczyt pakietów telemetrii z RadioManager
- Forward pakietów na UART w trybie TELEMETRY_BINARY
- Respektowanie konfiguracji UART mode

**Header:**
```cpp
#pragma once
#include <cstdint>
#include "radio.h"

enum class UartMode : uint8_t {
    DEBUG_TEXT,
    TELEMETRY_BINARY
};

class TelemetryForwarder {
public:
    void init(RadioManager* radio);
    void setUartMode(UartMode mode);
    UartMode getUartMode() const;

    // Call from main loop
    void update();

    // Statistics
    uint32_t getForwardedCount() const;
    uint32_t getDroppedCount() const;

private:
    RadioManager* m_radio = nullptr;
    UartMode m_uartMode = UartMode::DEBUG_TEXT;

    uint32_t m_forwardedCount = 0;
    uint32_t m_droppedCount = 0;

    // Forward single packet to UART
    void forwardPacket(const uint8_t* data, size_t len);

    // Check and forward specific packet types
    void checkAndForwardAttitude();
    void checkAndForwardMotors();
    void checkAndForwardStatus();
    // ... other types as needed
};
```

**Implementation:**
```cpp
#include "TelemetryForwarder.h"
#include <Arduino.h>

void TelemetryForwarder::init(RadioManager* radio) {
    m_radio = radio;
}

void TelemetryForwarder::setUartMode(UartMode mode) {
    m_uartMode = mode;
}

UartMode TelemetryForwarder::getUartMode() const {
    return m_uartMode;
}

void TelemetryForwarder::update() {
    if (m_uartMode != UartMode::TELEMETRY_BINARY) {
        return; // Only forward in TELEMETRY_BINARY mode
    }

    if (!m_radio || !m_radio->hasNewEnhancedTelemetry()) {
        return;
    }

    // Forward all available packet types
    checkAndForwardAttitude();
    checkAndForwardMotors();
    checkAndForwardStatus();
    // Add more types as needed

    m_radio->clearNewEnhancedFlag();
}

void TelemetryForwarder::checkAndForwardAttitude() {
    if (m_radio->hasAttitude()) {
        const auto& telem = m_radio->getEnhancedTelemetry();
        forwardPacket(
            reinterpret_cast<const uint8_t*>(&telem.attitude),
            sizeof(TelemetryAttitude)
        );
    }
}

void TelemetryForwarder::checkAndForwardMotors() {
    if (m_radio->hasMotors()) {
        const auto& telem = m_radio->getEnhancedTelemetry();
        forwardPacket(
            reinterpret_cast<const uint8_t*>(&telem.motors),
            sizeof(TelemetryMotors)
        );
    }
}

void TelemetryForwarder::checkAndForwardStatus() {
    if (m_radio->hasStatus()) {
        const auto& telem = m_radio->getEnhancedTelemetry();
        forwardPacket(
            reinterpret_cast<const uint8_t*>(&telem.status),
            sizeof(TelemetryStatus)
        );
    }
}

void TelemetryForwarder::forwardPacket(const uint8_t* data, size_t len) {
    // Forward raw bytes to UART
    size_t written = Serial.write(data, len);

    if (written == len) {
        m_forwardedCount++;
    } else {
        m_droppedCount++;
    }
}

uint32_t TelemetryForwarder::getForwardedCount() const {
    return m_forwardedCount;
}

uint32_t TelemetryForwarder::getDroppedCount() const {
    return m_droppedCount;
}
```

#### 4.1.2. Modyfikacja main.cpp

**Dodanie instancji TelemetryForwarder:**
```cpp
#include "telemetry/TelemetryForwarder.h"

// Global instances
RadioManager radio;
ControlManager control;
RadioErrorLogger radioErrorLogger;
TelemetryForwarder telemForwarder;  // NEW

void setup() {
    // ... existing setup code ...

    // Initialize telemetry forwarder
    telemForwarder.init(&radio);

    // Set UART mode (compile-time or runtime)
    #ifdef UART_MODE_TELEMETRY_BINARY
        telemForwarder.setUartMode(UartMode::TELEMETRY_BINARY);
    #else
        telemForwarder.setUartMode(UartMode::DEBUG_TEXT);
    #endif
}

void loop() {
    // ... existing loop code ...

    // Forward telemetry to UART
    telemForwarder.update();
}
```

#### 4.1.3. Modyfikacja config.h

**Dodanie opcji konfiguracji:**
```cpp
// UART Mode Configuration
// Uncomment to enable binary telemetry forwarding to UART
// Comment out for debug text mode
// #define UART_MODE_TELEMETRY_BINARY

// UART Configuration
#define UART_BAUD_RATE 115200
```

### 4.2. Testowanie Firmware

**Test 1: Weryfikacja trybu DEBUG_TEXT**
```
1. Skomentować #define UART_MODE_TELEMETRY_BINARY
2. Build & flash
3. Otworzyć Serial Monitor (115200 baud)
4. Spodziewany output: tekstowe logi "LOG: ..."
```

**Test 2: Weryfikacja trybu TELEMETRY_BINARY**
```
1. Odkomentować #define UART_MODE_TELEMETRY_BINARY
2. Build & flash
3. Uruchomić Python test script (patrz sekcja 6.3)
4. Spodziewany output: binarne pakiety parsowane do JSON
```

---

## 5. Implementacja Firmware - Dron (ESP32-S3)

### 5.1. Stan Obecny

**✅ Dron już wysyła Enhanced Telemetry przez ESP-NOW!**

RadioManager po stronie nadajnika odbiera pakiety i przechowuje je w `EnhancedTelemData`.

### 5.2. Wymagania do Implementacji

**Jeśli dron nie wysyła telemetrii:**

1. **Dodać scheduler telemetrii** (prawdopodobnie już istnieje w loopie flight controllera)
2. **Wywołania RadioManager::sendPacket()** z pakietami telemetrii
3. **Frekvencje wysyłania** zgodne z tabelą w sekcji 3.2

**Przykładowy kod dla drona:**
```cpp
// W głównym loopie flight controllera (500 Hz)

static uint32_t lastAttitudeSend = 0;
static uint32_t lastMotorsSend = 0;
static uint32_t lastStatusSend = 0;

uint32_t now = millis();

// ATTITUDE @ 20 Hz (co 50ms)
if (now - lastAttitudeSend >= 50) {
    TelemetryAttitude pkt = {};
    pkt.header.magic = TELEM_ENHANCED_MAGIC;
    pkt.header.version = TELEM_ENHANCED_VERSION;
    pkt.header.type = TELEM_TYPE_ATTITUDE;
    pkt.header.seq = attitudeSeq++;
    pkt.header.timestamp_us = micros();

    // Fill attitude data from flight controller state
    pkt.roll_deg_x100 = (int16_t)(state.roll * 100.0f);
    pkt.pitch_deg_x100 = (int16_t)(state.pitch * 100.0f);
    pkt.yaw_deg_x100 = (int16_t)(state.yaw * 100.0f);
    pkt.roll_rate_dps_x10 = (int16_t)(state.rollRate * 10.0f);
    pkt.pitch_rate_dps_x10 = (int16_t)(state.pitchRate * 10.0f);
    pkt.yaw_rate_dps_x10 = (int16_t)(state.yawRate * 10.0f);

    // Calculate CRC
    pkt.crc = crc16_x25((uint8_t*)&pkt, sizeof(pkt) - 2);

    // Send via ESP-NOW
    radio.sendPacket(&pkt, sizeof(pkt));

    lastAttitudeSend = now;
}

// MOTORS @ 5 Hz (co 200ms)
if (now - lastMotorsSend >= 200) {
    TelemetryMotors pkt = {};
    // ... similar to above ...
    lastMotorsSend = now;
}

// STATUS @ 2.5 Hz (co 400ms)
if (now - lastStatusSend >= 400) {
    TelemetryStatus pkt = {};
    // ... similar to above ...
    lastStatusSend = now;
}
```

### 5.3. Walidacja Drona

**Checklist:**
- [ ] ESP-NOW initialized and peer added
- [ ] Telemetry packets sent at correct frequencies
- [ ] CRC calculated correctly for all packets
- [ ] Timestamps in microseconds (micros())
- [ ] Sequence numbers incrementing correctly

---

## 6. Python Bridge - Parser i WebSocket

### 6.1. Architektura Python Bridge

```
┌─────────────────────────────────────────┐
│  main.py                                │
│  ├─ SerialReader (Thread)               │
│  │  └─ PacketParser                     │
│  ├─ WebSocketServer (asyncio)           │
│  └─ TelemetryStore (queue)              │
└─────────────────────────────────────────┘
```

### 6.2. Implementacja Parser Python

**Plik: `telemetry_parser.py`**

```python
import struct
from enum import IntEnum
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class TelemetryPacketType(IntEnum):
    ATTITUDE = 0x01
    CONTROL = 0x02
    MOTORS = 0x03
    STATUS = 0x04
    SENSORS = 0x05
    SAFETY = 0x06
    PERFORMANCE = 0x07

TELEM_ENHANCED_MAGIC = 0x5B
TELEM_ENHANCED_VERSION = 2

# Packet sizes (total including header and CRC)
PACKET_SIZES = {
    TelemetryPacketType.ATTITUDE: 24,
    TelemetryPacketType.CONTROL: 30,
    TelemetryPacketType.MOTORS: 31,
    TelemetryPacketType.STATUS: 24,
    TelemetryPacketType.SENSORS: 30,
    TelemetryPacketType.SAFETY: 20,
    TelemetryPacketType.PERFORMANCE: 22,
}

def crc16_x25(data: bytes) -> int:
    """Calculate CRC-16/X.25 checksum."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return crc ^ 0xFFFF

class TelemetryHeader:
    """Common telemetry header (10 bytes)."""
    FORMAT = '<BBBBHHI'  # little-endian: 4 bytes + uint16 + uint32
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, data: bytes):
        unpacked = struct.unpack(self.FORMAT, data[:self.SIZE])
        self.magic = unpacked[0]
        self.version = unpacked[1]
        self.type = unpacked[2]
        self.flags = unpacked[3]
        self.seq = unpacked[4]
        self.timestamp_us = unpacked[5]

    def is_valid(self) -> bool:
        return (self.magic == TELEM_ENHANCED_MAGIC and
                self.version == TELEM_ENHANCED_VERSION)

class TelemetryParser:
    """Parser for Enhanced Telemetry packets."""

    def __init__(self):
        self.buffer = bytearray()
        self.stats = {
            'packets_parsed': 0,
            'crc_errors': 0,
            'unknown_types': 0,
        }

    def feed(self, data: bytes) -> list[Dict[str, Any]]:
        """Feed data to parser, returns list of parsed packets."""
        self.buffer.extend(data)
        packets = []

        while True:
            packet = self._try_parse_packet()
            if packet is None:
                break
            packets.append(packet)

        # Trim buffer if too large (prevent memory growth)
        if len(self.buffer) > 4096:
            # Look for next magic byte
            try:
                idx = self.buffer.index(TELEM_ENHANCED_MAGIC)
                self.buffer = self.buffer[idx:]
            except ValueError:
                self.buffer.clear()

        return packets

    def _try_parse_packet(self) -> Optional[Dict[str, Any]]:
        """Try to parse one packet from buffer."""
        # Need at least header to proceed
        if len(self.buffer) < TelemetryHeader.SIZE:
            return None

        # Find magic byte
        try:
            magic_idx = self.buffer.index(TELEM_ENHANCED_MAGIC)
        except ValueError:
            # No magic byte found, clear buffer
            self.buffer.clear()
            return None

        # Discard bytes before magic
        if magic_idx > 0:
            self.buffer = self.buffer[magic_idx:]

        # Parse header
        if len(self.buffer) < TelemetryHeader.SIZE:
            return None

        header = TelemetryHeader(bytes(self.buffer[:TelemetryHeader.SIZE]))

        # Validate header
        if not header.is_valid():
            # Invalid header, skip this byte and try next
            self.buffer.pop(0)
            return None

        # Check if we know this packet type
        try:
            packet_type = TelemetryPacketType(header.type)
        except ValueError:
            logger.warning(f"Unknown packet type: 0x{header.type:02X}")
            self.stats['unknown_types'] += 1
            self.buffer.pop(0)
            return None

        # Check if we have full packet
        expected_size = PACKET_SIZES[packet_type]
        if len(self.buffer) < expected_size:
            return None  # Wait for more data

        # Extract packet
        packet_data = bytes(self.buffer[:expected_size])

        # Validate CRC
        crc_calculated = crc16_x25(packet_data[:-2])
        crc_received = struct.unpack('<H', packet_data[-2:])[0]

        if crc_calculated != crc_received:
            logger.warning(f"CRC error: calc=0x{crc_calculated:04X} rcv=0x{crc_received:04X}")
            self.stats['crc_errors'] += 1
            self.buffer.pop(0)
            return None

        # Parse payload
        parsed = self._parse_packet_payload(packet_type, header, packet_data)

        # Remove parsed packet from buffer
        self.buffer = self.buffer[expected_size:]

        self.stats['packets_parsed'] += 1
        return parsed

    def _parse_packet_payload(self, packet_type: TelemetryPacketType,
                               header: TelemetryHeader, data: bytes) -> Dict[str, Any]:
        """Parse payload based on packet type."""

        if packet_type == TelemetryPacketType.ATTITUDE:
            return self._parse_attitude(header, data)
        elif packet_type == TelemetryPacketType.MOTORS:
            return self._parse_motors(header, data)
        elif packet_type == TelemetryPacketType.STATUS:
            return self._parse_status(header, data)
        # Add more types as needed
        else:
            return {
                'type': packet_type.name,
                'ts_us': header.timestamp_us,
                'seq': header.seq,
            }

    def _parse_attitude(self, header: TelemetryHeader, data: bytes) -> Dict[str, Any]:
        """Parse ATTITUDE packet (24 bytes total)."""
        # Skip header (10 bytes), parse payload (12 bytes), skip CRC (2 bytes)
        payload = struct.unpack('<hhhhhh', data[10:22])

        return {
            'type': 'ATT',
            'ts_us': header.timestamp_us,
            'seq': header.seq,
            'roll_deg': payload[0] / 100.0,
            'pitch_deg': payload[1] / 100.0,
            'yaw_deg': payload[2] / 100.0,
            'roll_rate_dps': payload[3] / 10.0,
            'pitch_rate_dps': payload[4] / 10.0,
            'yaw_rate_dps': payload[5] / 10.0,
        }

    def _parse_motors(self, header: TelemetryHeader, data: bytes) -> Dict[str, Any]:
        """Parse MOTORS packet (31 bytes total)."""
        # Skip header (10 bytes), parse payload (19 bytes), skip CRC (2 bytes)
        payload = struct.unpack('<HHHHHHHHB', data[10:29])

        return {
            'type': 'MOT',
            'ts_us': header.timestamp_us,
            'seq': header.seq,
            'motors': list(payload[0:4]),  # motor_cmd[4]
            'motors_actual': list(payload[4:8]),  # motor_actual[4]
            'throttle': payload[8],
            'mixer_id': payload[9],
        }

    def _parse_status(self, header: TelemetryHeader, data: bytes) -> Dict[str, Any]:
        """Parse STATUS packet (24 bytes total)."""
        # Skip header (10 bytes), parse payload (12 bytes), skip CRC (2 bytes)
        payload = struct.unpack('<BBBBBBHI', data[10:22])

        safety_flags = payload[2]

        return {
            'type': 'STA',
            'ts_us': header.timestamp_us,
            'seq': header.seq,
            'armed': bool(payload[0]),
            'mode': payload[1],
            'link_quality': payload[4],
            'battery_pct': payload[5],
            'uptime_s': payload[6],
            'loop_rate_hz': payload[7] / 10.0,
            'flags': {
                'ARM': bool(payload[0]),
                'HRZ': bool(safety_flags & 0x01),
                'LINK': bool(safety_flags & 0x02),
                'DISARM': bool(safety_flags & 0x04),
                'CAL': bool(safety_flags & 0x08),
                'CALIB': bool(safety_flags & 0x10),
                'FAIL': bool(safety_flags & 0x20),
            }
        }

    def get_stats(self) -> Dict[str, int]:
        """Get parser statistics."""
        return self.stats.copy()
```

### 6.3. WebSocket Server

**Plik: `websocket_server.py`**

```python
import asyncio
import websockets
import json
import logging
from typing import Set
from queue import Queue

logger = logging.getLogger(__name__)

class TelemetryWebSocketServer:
    """WebSocket server for telemetry broadcast."""

    def __init__(self, host: str = 'localhost', port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.telemetry_queue = Queue()

    async def register(self, websocket):
        """Register new client."""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")

    async def unregister(self, websocket):
        """Unregister client."""
        self.clients.remove(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")

    async def handler(self, websocket, path):
        """Handle WebSocket connection."""
        await self.register(websocket)
        try:
            async for message in websocket:
                # Handle incoming messages (if needed)
                pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)

    async def broadcast_loop(self):
        """Broadcast telemetry to all connected clients."""
        while True:
            if not self.telemetry_queue.empty():
                packet = self.telemetry_queue.get()
                message = json.dumps(packet)

                # Broadcast to all clients
                if self.clients:
                    await asyncio.gather(
                        *[client.send(message) for client in self.clients],
                        return_exceptions=True
                    )

            await asyncio.sleep(0.01)  # 100 Hz check rate

    def queue_telemetry(self, packet: dict):
        """Queue telemetry packet for broadcast (thread-safe)."""
        self.telemetry_queue.put(packet)

    async def start(self):
        """Start WebSocket server."""
        async with websockets.serve(self.handler, self.host, self.port):
            logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
            await self.broadcast_loop()
```

### 6.4. Main Application

**Plik: `main.py`**

```python
import asyncio
import serial
import threading
import logging
from telemetry_parser import TelemetryParser
from websocket_server import TelemetryWebSocketServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SerialReaderThread(threading.Thread):
    """Thread for reading serial port."""

    def __init__(self, port: str, baudrate: int, websocket_server: TelemetryWebSocketServer):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.websocket_server = websocket_server
        self.parser = TelemetryParser()
        self.running = True

    def run(self):
        """Run serial reader loop."""
        try:
            with serial.Serial(self.port, self.baudrate, timeout=1) as ser:
                logger.info(f"Serial port opened: {self.port} @ {self.baudrate}")

                while self.running:
                    data = ser.read(1024)
                    if data:
                        packets = self.parser.feed(data)
                        for packet in packets:
                            # Queue for WebSocket broadcast
                            self.websocket_server.queue_telemetry(packet)

                            # Log for debugging
                            logger.debug(f"Parsed: {packet['type']} seq={packet['seq']}")

        except serial.SerialException as e:
            logger.error(f"Serial error: {e}")

    def stop(self):
        """Stop reader thread."""
        self.running = False

async def main():
    """Main application entry point."""
    # Configuration
    SERIAL_PORT = 'COM3'  # Change to your port (e.g., /dev/ttyUSB0 on Linux)
    SERIAL_BAUD = 115200
    WS_HOST = 'localhost'
    WS_PORT = 8765

    # Create WebSocket server
    ws_server = TelemetryWebSocketServer(WS_HOST, WS_PORT)

    # Start serial reader thread
    serial_thread = SerialReaderThread(SERIAL_PORT, SERIAL_BAUD, ws_server)
    serial_thread.start()

    # Run WebSocket server (blocking)
    try:
        await ws_server.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        serial_thread.stop()
        serial_thread.join()

if __name__ == '__main__':
    asyncio.run(main())
```

### 6.5. Testowanie Python Bridge

**Test Script: `test_parser.py`**

```python
import struct
from telemetry_parser import TelemetryParser, crc16_x25, TELEM_ENHANCED_MAGIC, TELEM_ENHANCED_VERSION

def create_test_attitude_packet():
    """Create test ATTITUDE packet."""
    data = bytearray(24)

    # Header
    struct.pack_into('<BBBBHHI', data, 0,
        TELEM_ENHANCED_MAGIC,   # magic
        TELEM_ENHANCED_VERSION,  # version
        0x01,                    # type (ATTITUDE)
        0x00,                    # flags
        42,                      # seq
        123456789                # timestamp_us
    )

    # Payload
    struct.pack_into('<hhhhhh', data, 10,
        -898,   # roll (*100) = -8.98°
        924,    # pitch (*100) = 9.24°
        0,      # yaw
        -205,   # roll rate (*10) = -20.5°/s
        115,    # pitch rate (*10) = 11.5°/s
        0       # yaw rate
    )

    # CRC
    crc = crc16_x25(bytes(data[:22]))
    struct.pack_into('<H', data, 22, crc)

    return bytes(data)

def test_parser():
    """Test parser with synthetic data."""
    parser = TelemetryParser()

    # Create test packet
    packet_data = create_test_attitude_packet()

    # Feed to parser
    packets = parser.feed(packet_data)

    # Verify
    assert len(packets) == 1
    pkt = packets[0]

    assert pkt['type'] == 'ATT'
    assert pkt['seq'] == 42
    assert pkt['ts_us'] == 123456789
    assert abs(pkt['roll_deg'] - (-8.98)) < 0.01
    assert abs(pkt['pitch_deg'] - 9.24) < 0.01

    print("✅ Parser test passed!")
    print(f"Parsed packet: {pkt}")

if __name__ == '__main__':
    test_parser()
```

**Uruchomienie testu:**
```bash
python test_parser.py
```

---

## 7. React UI - Kontrakt i Integracja

### 7.1. Kontrakt JSON dla UI

UI odbiera pakiety telemetrii jako wiadomości WebSocket w formacie JSON:

#### 7.1.1. ATTITUDE Packet
```json
{
  "type": "ATT",
  "ts_us": 123456789,
  "seq": 42,
  "roll_deg": -8.98,
  "pitch_deg": 9.24,
  "yaw_deg": 0.00,
  "roll_rate_dps": -20.5,
  "pitch_rate_dps": 11.5,
  "yaw_rate_dps": 0.0
}
```

#### 7.1.2. MOTORS Packet
```json
{
  "type": "MOT",
  "ts_us": 123456800,
  "seq": 43,
  "motors": [0, 5120, 31488, 4864],
  "motors_actual": [0, 5120, 31488, 4864],
  "throttle": 2686,
  "mixer_id": 0
}
```

#### 7.1.3. STATUS Packet
```json
{
  "type": "STA",
  "ts_us": 123456820,
  "seq": 44,
  "armed": true,
  "mode": 0,
  "link_quality": 100,
  "battery_pct": 85,
  "uptime_s": 45,
  "loop_rate_hz": 500.0,
  "flags": {
    "ARM": true,
    "HRZ": true,
    "LINK": true,
    "DISARM": false,
    "CAL": true,
    "CALIB": false,
    "FAIL": false
  }
}
```

### 7.2. TypeScript Interfaces

**Plik: `src/types/telemetry.ts`**

```typescript
export interface TelemetryAttitude {
  type: 'ATT';
  ts_us: number;
  seq: number;
  roll_deg: number;
  pitch_deg: number;
  yaw_deg: number;
  roll_rate_dps: number;
  pitch_rate_dps: number;
  yaw_rate_dps: number;
}

export interface TelemetryMotors {
  type: 'MOT';
  ts_us: number;
  seq: number;
  motors: [number, number, number, number];
  motors_actual: [number, number, number, number];
  throttle: number;
  mixer_id: number;
}

export interface TelemetryStatus {
  type: 'STA';
  ts_us: number;
  seq: number;
  armed: boolean;
  mode: number;
  link_quality: number;
  battery_pct: number;
  uptime_s: number;
  loop_rate_hz: number;
  flags: {
    ARM: boolean;
    HRZ: boolean;
    LINK: boolean;
    DISARM: boolean;
    CAL: boolean;
    CALIB: boolean;
    FAIL: boolean;
  };
}

export type TelemetryPacket = TelemetryAttitude | TelemetryMotors | TelemetryStatus;
```

### 7.3. Zustand Store dla Telemetrii

**Plik: `src/store/telemetryStore.ts`**

```typescript
import { create } from 'zustand';
import { TelemetryAttitude, TelemetryMotors, TelemetryStatus } from '../types/telemetry';

interface TelemetryState {
  // Latest packets
  attitude: TelemetryAttitude | null;
  motors: TelemetryMotors | null;
  status: TelemetryStatus | null;

  // Connection state
  connected: boolean;
  lastUpdate: number;

  // Actions
  updateAttitude: (data: TelemetryAttitude) => void;
  updateMotors: (data: TelemetryMotors) => void;
  updateStatus: (data: TelemetryStatus) => void;
  setConnected: (connected: boolean) => void;
}

export const useTelemetryStore = create<TelemetryState>((set) => ({
  attitude: null,
  motors: null,
  status: null,
  connected: false,
  lastUpdate: 0,

  updateAttitude: (data) => set({ attitude: data, lastUpdate: Date.now() }),
  updateMotors: (data) => set({ motors: data, lastUpdate: Date.now() }),
  updateStatus: (data) => set({ status: data, lastUpdate: Date.now() }),
  setConnected: (connected) => set({ connected }),
}));
```

### 7.4. WebSocket Hook

**Plik: `src/hooks/useTelemetryWebSocket.ts`**

```typescript
import { useEffect, useRef } from 'react';
import { useTelemetryStore } from '../store/telemetryStore';
import { TelemetryPacket } from '../types/telemetry';

export function useTelemetryWebSocket(url: string = 'ws://localhost:8765') {
  const wsRef = useRef<WebSocket | null>(null);
  const { updateAttitude, updateMotors, updateStatus, setConnected } = useTelemetryStore();

  useEffect(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnected(false);
    };

    ws.onmessage = (event) => {
      try {
        const packet: TelemetryPacket = JSON.parse(event.data);

        switch (packet.type) {
          case 'ATT':
            updateAttitude(packet);
            break;
          case 'MOT':
            updateMotors(packet);
            break;
          case 'STA':
            updateStatus(packet);
            break;
        }
      } catch (error) {
        console.error('Failed to parse telemetry:', error);
      }
    };

    return () => {
      ws.close();
    };
  }, [url, updateAttitude, updateMotors, updateStatus, setConnected]);
}
```

### 7.5. React Components

#### 7.5.1. Sztuczny Horyzont

**Plik: `src/components/ArtificialHorizon.tsx`**

```typescript
import React from 'react';
import { useTelemetryStore } from '../store/telemetryStore';

export const ArtificialHorizon: React.FC = () => {
  const attitude = useTelemetryStore((state) => state.attitude);

  if (!attitude) {
    return <div className="horizon-placeholder">Waiting for attitude data...</div>;
  }

  const { roll_deg, pitch_deg } = attitude;

  return (
    <div className="artificial-horizon">
      <svg width="300" height="300" viewBox="-150 -150 300 300">
        {/* Sky */}
        <rect x="-150" y="-150" width="300" height="150" fill="#4A90E2" />

        {/* Ground */}
        <rect x="-150" y="0" width="300" height="150" fill="#8B4513" />

        {/* Pitch lines */}
        <g transform={`rotate(${-roll_deg})`}>
          {/* Horizon line */}
          <line
            x1="-120" y1={pitch_deg * 3} x2="120" y2={pitch_deg * 3}
            stroke="white" strokeWidth="2"
          />

          {/* ±10° lines */}
          <line
            x1="-60" y1={(pitch_deg - 10) * 3} x2="60" y2={(pitch_deg - 10) * 3}
            stroke="white" strokeWidth="1"
          />
          <line
            x1="-60" y1={(pitch_deg + 10) * 3} x2="60" y2={(pitch_deg + 10) * 3}
            stroke="white" strokeWidth="1"
          />
        </g>

        {/* Center reference */}
        <circle cx="0" cy="0" r="5" fill="none" stroke="yellow" strokeWidth="2" />
        <line x1="-40" y1="0" x2="-10" y2="0" stroke="yellow" strokeWidth="2" />
        <line x1="10" y1="0" x2="40" y2="0" stroke="yellow" strokeWidth="2" />

        {/* Roll indicator */}
        <g transform={`rotate(${-roll_deg})`}>
          <path d="M 0,-130 L -5,-120 L 5,-120 Z" fill="yellow" />
        </g>
      </svg>

      <div className="attitude-values">
        <div>Roll: {roll_deg.toFixed(1)}°</div>
        <div>Pitch: {pitch_deg.toFixed(1)}°</div>
      </div>
    </div>
  );
};
```

#### 7.5.2. Wskaźniki Silników

**Plik: `src/components/MotorIndicators.tsx`**

```typescript
import React from 'react';
import { useTelemetryStore } from '../store/telemetryStore';

export const MotorIndicators: React.FC = () => {
  const motors = useTelemetryStore((state) => state.motors);

  if (!motors) {
    return <div>Waiting for motor data...</div>;
  }

  const motorLabels = ['M1', 'M2', 'M3', 'M4'];

  return (
    <div className="motor-indicators">
      {motors.motors.map((value, index) => {
        const percent = (value / 65535) * 100;

        return (
          <div key={index} className="motor-bar">
            <div className="motor-label">{motorLabels[index]}</div>
            <div className="motor-bar-bg">
              <div
                className="motor-bar-fill"
                style={{ height: `${percent}%` }}
              />
            </div>
            <div className="motor-value">{value}</div>
          </div>
        );
      })}

      <div className="throttle-info">
        Throttle: {motors.throttle}
      </div>
    </div>
  );
};
```

#### 7.5.3. Status Display

**Plik: `src/components/StatusDisplay.tsx`**

```typescript
import React from 'react';
import { useTelemetryStore } from '../store/telemetryStore';

export const StatusDisplay: React.FC = () => {
  const status = useTelemetryStore((state) => state.status);
  const connected = useTelemetryStore((state) => state.connected);

  if (!status) {
    return (
      <div className="status-display">
        <div className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
          {connected ? 'Connected' : 'Disconnected'}
        </div>
      </div>
    );
  }

  return (
    <div className="status-display">
      <div className={`armed-status ${status.armed ? 'armed' : 'disarmed'}`}>
        {status.armed ? '⚠️ ARMED' : 'DISARMED'}
      </div>

      <div className="status-grid">
        <div className="status-item">
          <span className="label">Link:</span>
          <span className="value">{status.link_quality}%</span>
        </div>

        <div className="status-item">
          <span className="label">Battery:</span>
          <span className="value">{status.battery_pct}%</span>
        </div>

        <div className="status-item">
          <span className="label">Uptime:</span>
          <span className="value">{status.uptime_s}s</span>
        </div>

        <div className="status-item">
          <span className="label">Loop:</span>
          <span className="value">{status.loop_rate_hz.toFixed(1)} Hz</span>
        </div>
      </div>

      <div className="status-flags">
        {Object.entries(status.flags).map(([key, value]) => (
          <div key={key} className={`flag ${value ? 'active' : 'inactive'}`}>
            {key}
          </div>
        ))}
      </div>
    </div>
  );
};
```

#### 7.5.4. Main Dashboard

**Plik: `src/App.tsx`**

```typescript
import React from 'react';
import { useTelemetryWebSocket } from './hooks/useTelemetryWebSocket';
import { ArtificialHorizon } from './components/ArtificialHorizon';
import { MotorIndicators } from './components/MotorIndicators';
import { StatusDisplay } from './components/StatusDisplay';
import './App.css';

function App() {
  useTelemetryWebSocket();

  return (
    <div className="app">
      <header>
        <h1>Drone Telemetry Dashboard</h1>
      </header>

      <div className="dashboard">
        <div className="panel horizon-panel">
          <h2>Artificial Horizon</h2>
          <ArtificialHorizon />
        </div>

        <div className="panel motors-panel">
          <h2>Motor Outputs</h2>
          <MotorIndicators />
        </div>

        <div className="panel status-panel">
          <h2>System Status</h2>
          <StatusDisplay />
        </div>
      </div>
    </div>
  );
}

export default App;
```

---

## 8. Optymalizacje i Rozszerzenia

### 8.1. Opcjonalne Optymalizacje (zgodne z planem)

#### 8.1.1. Kompresja Telemetrii

**Cel:** Zmniejszenie bandwidth ESP-NOW (obecnie ~60 pakietów/sek → max ~240 bytes/s)

**Implementacja:**
- Wykorzystać pole `flags` w `TelemetryHeader` (bit 0 = compressed)
- Algorytm: delta encoding + variable-length integers
- Trade-off: CPU time vs bandwidth

**Priorytet:** ⭐⭐ (średni - tylko jeśli bandwidth ESP-NOW jest problemem)

#### 8.1.2. Adaptive Rate Control

**Cel:** Dynamiczne dostosowanie częstotliwości wysyłki na podstawie obciążenia sieci

**Implementacja:**
```cpp
// W flight controller:
if (radio_tx_queue_full || packet_loss > 10%) {
    // Reduce ATTITUDE from 20Hz to 10Hz
    attitude_interval_ms = 100;
} else {
    attitude_interval_ms = 50;
}
```

**Priorytet:** ⭐ (niski - tylko dla zaawansowanych scenariuszy)

#### 8.1.3. Blackbox Logging

**Cel:** Zapis telemetrii do pliku dla post-flight analysis

**Implementacja:**
```python
# W Python bridge:
class BlackboxLogger:
    def __init__(self, filename):
        self.file = open(filename, 'wb')

    def log_packet(self, packet_data: bytes):
        # Write timestamp + packet to file
        timestamp = int(time.time() * 1e6)
        self.file.write(struct.pack('<Q', timestamp))
        self.file.write(packet_data)
```

**Priorytet:** ⭐⭐⭐ (wysoki - bardzo użyteczne do debugowania)

#### 8.1.4. Multi-Drone Support

**Cel:** Obsługa telemetrii z wielu dronów jednocześnie

**Implementacja:**
- Dodać pole `drone_id` do nagłówka pakietu
- W Python bridge: routing pakietów do osobnych store'ów
- W UI: dropdown do wyboru aktywnego drona

**Priorytet:** ⭐ (niski - tylko dla zaawansowanych use case'ów)

### 8.2. Możliwe Rozszerzenia (poza zakresem obecnego planu)

#### 8.2.1. CONTROL Packets dla Tuningu

**Cel:** Live tuning PID controller z UI

**Wymagania:**
- Wysyłka `TelemetryControl` pakietów @ 10 Hz
- UI z sliderami dla PID gains
- Dwukierunkowa komunikacja (UI → Python → UART → Nadajnik → Dron)

**Status:** ⚠️ Wymaga implementacji reverse channel (UART → ESP-NOW)

#### 8.2.2. Graficzny Flight Path (3D)

**Cel:** Wizualizacja trajektorii lotu w 3D

**Wymagania:**
- Integracja gyro → position estimation
- Three.js w React UI
- Przechowywanie historii pozycji

**Status:** ⚠️ Wymaga dodatkowych sensorów (GPS/optical flow)

#### 8.2.3. Spektogram FFT dla Vibracji

**Cel:** Analiza wibracji silników w czasie rzeczywistym

**Wymagania:**
- FFT raw gyro data na dronie
- Nowy typ pakietu: `TELEM_TYPE_FFT`
- Waterfall plot w UI

**Status:** ⚠️ Wymaga dużej mocy obliczeniowej i bandwidth

---

## 9. Podsumowanie i Checklist Implementacji

### 9.1. Checklist - Firmware Nadajnika (ESP32-C3)

- [ ] Utworzyć `src/telemetry/TelemetryForwarder.h`
- [ ] Utworzyć `src/telemetry/TelemetryForwarder.cpp`
- [ ] Dodać `#define UART_MODE_TELEMETRY_BINARY` do `config.h`
- [ ] Zintegrować `TelemetryForwarder` w `main.cpp`
- [ ] Przetestować tryb DEBUG_TEXT (logi tekstowe)
- [ ] Przetestować tryb TELEMETRY_BINARY (pakiety binarne)
- [ ] Zweryfikować forward wszystkich typów pakietów (ATT, MOT, STA)

### 9.2. Checklist - Firmware Drona (ESP32-S3)

- [ ] Zweryfikować wysyłanie pakietów Enhanced Telemetry
- [ ] Sprawdzić częstotliwości wysyłania (ATT@20Hz, MOT@5Hz, STA@2.5Hz)
- [ ] Walidować poprawność CRC we wszystkich pakietach
- [ ] Przetestować z RadioManager nadajnika

### 9.3. Checklist - Python Bridge

- [ ] Utworzyć `telemetry_parser.py`
- [ ] Utworzyć `websocket_server.py`
- [ ] Utworzyć `main.py`
- [ ] Dodać `requirements.txt` (pyserial, websockets)
- [ ] Utworzyć `test_parser.py` i przetestować parser
- [ ] Przetestować połączenie UART z nadajnikiem
- [ ] Przetestować WebSocket broadcast

### 9.4. Checklist - React UI

- [ ] Utworzyć TypeScript interfaces (`src/types/telemetry.ts`)
- [ ] Utworzyć Zustand store (`src/store/telemetryStore.ts`)
- [ ] Utworzyć WebSocket hook (`src/hooks/useTelemetryWebSocket.ts`)
- [ ] Zaimplementować `ArtificialHorizon.tsx`
- [ ] Zaimplementować `MotorIndicators.tsx`
- [ ] Zaimplementować `StatusDisplay.tsx`
- [ ] Zintegrować w `App.tsx`
- [ ] Dodać CSS styling
- [ ] Przetestować z Python bridge

### 9.5. Checklist - Integracja End-to-End

- [ ] Dron wysyła telemetrię → Nadajnik odbiera
- [ ] Nadajnik forwarduje na UART → Python odbiera
- [ ] Python parsuje pakiety → WebSocket broadcast
- [ ] React UI odbiera JSON → aktualizuje komponenty
- [ ] Zweryfikować latency end-to-end (<100ms)
- [ ] Przetestować stabilność przy długim czasie działania (>10 min)

---

## 10. Struktura Plików Projektu

```
transmitter-firmware/
├── include/
│   ├── config.h                    (+ UART mode config)
│   ├── protocol.h                  (✅ exists)
│   └── radio.h                     (✅ exists)
├── src/
│   ├── telemetry/
│   │   ├── TelemetryForwarder.h    (NEW)
│   │   └── TelemetryForwarder.cpp  (NEW)
│   ├── radio/
│   │   └── radio.cpp               (✅ exists)
│   └── main.cpp                    (modify)
└── .claude/
    ├── plan_telemetria_ui.md       (✅ exists)
    └── TELEMETRY_SYSTEM_DESIGN.md  (this file)

python-bridge/
├── telemetry_parser.py             (NEW)
├── websocket_server.py             (NEW)
├── main.py                         (NEW)
├── test_parser.py                  (NEW)
└── requirements.txt                (NEW)

react-ui/
├── src/
│   ├── types/
│   │   └── telemetry.ts            (NEW)
│   ├── store/
│   │   └── telemetryStore.ts       (NEW)
│   ├── hooks/
│   │   └── useTelemetryWebSocket.ts (NEW)
│   ├── components/
│   │   ├── ArtificialHorizon.tsx   (NEW)
│   │   ├── MotorIndicators.tsx     (NEW)
│   │   └── StatusDisplay.tsx       (NEW)
│   ├── App.tsx                     (modify)
│   └── App.css                     (NEW styles)
├── package.json
└── tsconfig.json
```

---

## 11. Przewidywany Timeline Implementacji

| Etap | Zadanie | Szacowany Czas | Priorytet |
|------|---------|----------------|-----------|
| 1 | Firmware Nadajnika (TelemetryForwarder) | 2-3 godziny | 🔴 Krytyczny |
| 2 | Python Bridge (parser + WebSocket) | 3-4 godziny | 🔴 Krytyczny |
| 3 | React UI (base components) | 4-6 godzin | 🔴 Krytyczny |
| 4 | Testowanie integracji end-to-end | 2-3 godziny | 🔴 Krytyczny |
| 5 | CSS styling i UX polish | 2-3 godziny | 🟡 Średni |
| 6 | Blackbox logging | 1-2 godziny | 🟡 Średni |
| 7 | Optymalizacje (kompresja, adaptive rate) | 4-6 godzin | 🟢 Opcjonalny |

**Total MVP:** ~15-20 godzin pracy
**Total z optymalizacjami:** ~25-30 godzin pracy

---

## 12. FAQ i Troubleshooting

### Q1: Dlaczego pakiety nie docierają do Python bridge?

**Sprawdź:**
1. Czy nadajnik jest w trybie `TELEMETRY_BINARY`?
2. Czy baud rate UART to 115200?
3. Czy port COM jest poprawny? (użyj `ls /dev/ttyUSB*` na Linuxie)
4. Czy dron wysyła telemetrię? (sprawdź ESP-NOW send success count)

### Q2: CRC errors w Python parser

**Przyczyny:**
1. Niezgodna endianność (ESP32 = little-endian, sprawdź struct format)
2. Błędna implementacja CRC (użyj tej samej funkcji co w firmware)
3. Uszkodzenie danych na UART (sprawdź kabel, baud rate)

### Q3: React UI nie odbiera danych

**Sprawdź:**
1. Czy Python bridge uruchomiony? (`python main.py`)
2. Czy WebSocket połączony? (sprawdź console.log w przeglądarce)
3. Czy firewall blokuje port 8765?
4. Czy URL WebSocket poprawny? (`ws://localhost:8765`)

### Q4: Sztuczny horyzont nie aktualizuje się płynnie

**Optymalizacje:**
1. Zwiększyć częstotliwość ATTITUDE z 20Hz do 50Hz
2. Dodać interpolację w React (lerp między pakietami)
3. Użyć `requestAnimationFrame` zamiast re-render na każdy pakiet

### Q5: Jak dodać obsługę nowego typu pakietu?

**Kroki:**
1. Dodać case w `TelemetryForwarder::update()`
2. Dodać `_parse_xxx()` w Python `TelemetryParser`
3. Dodać interface w TypeScript `telemetry.ts`
4. Dodać action w Zustand store
5. Utworzyć komponent React dla wizualizacji

---

## 13. Kontakt i Wsparcie

**Dokumentacja:**
- Plan telemetrii: `.claude/plan_telemetria_ui.md`
- Ten dokument: `.claude/TELEMETRY_SYSTEM_DESIGN.md`

**Repozytorium:**
- Firmware: `transmitter-firmware/`
- Python Bridge: `python-bridge/` (do utworzenia)
- React UI: `react-ui/` (do utworzenia)

---

**Koniec dokumentu projektowego**
**Wersja:** 1.0
**Data:** 2025-12-03
**Autor:** Claude (Anthropic) + Daniel (projekt lead)
