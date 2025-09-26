# Transformacja Kodu Arduino do Projektu PlatformIO

## Opis Transformacji

Otrzymaliśmy prosty kod Arduino dla nadajnika RC (ESP32-C3) komunikującego się z dronem przez ESP-NOW i przekształciliśmy go w pełnoprawny, modularny projekt PlatformIO zachowując dokładnie tę samą funkcjonalność.

## Kod Źródłowy Arduino (Referencja)

Oryginalny kod to pojedynczy plik `.ino` z następującymi cechami:

### Funkcjonalności Oryginalne:
- **ESP-NOW komunikacja** na kanale 1 z MAC `{0xD8, 0x3B, 0xDA, 0x74, 0x83, 0x68}`
- **OLED SSD1306** 128x32 na pinach SDA=8, SCL=9
- **4 osie sterowania**: 
  - THR (GPIO 0) - tryb integratora (drążek kontroluje szybkość zmian)
  - YAW (GPIO 1) - tryb proporcjonalny
  - PITCH (GPIO 4) - tryb proporcjonalny z inwersją
  - ROLL (GPIO 2) - tryb proporcjonalny
- **Przycisk ARM** (GPIO 7) - przełączanie arm/disarm bez blokad
- **Kalibracja centrów** - proste zapisywanie pozycji neutralnych drążków
- **Filtracja IIR** z α=0.3 dla płynności sterowania
- **Pakiety 50Hz** z protokołem CRC-16/X.25
- **Wyświetlanie na OLED** stanu arm, throttle i pozycji osi

### Specyficzne Zachowania:
- **Throttle integrator**: Pozycja drążka = szybkość zmiany throttle (nie pozycja)
- **Start z zerem**: Throttle zawsze zaczyna od 0 przy starcie
- **Centrowanie**: Kalibracja tylko pozycji środkowych, nie min/max
- **Bez blokad ARM**: Można arm-ować przy dowolnej pozycji throttle

## Struktura Projektu PlatformIO

### Struktura Katalogów
```
transmitter-firmware/
├── .github/
│   └── copilot-instructions.md    # Instrukcje dla AI
├── .vscode/
│   ├── tasks.json                # Zadania build/upload
│   └── launch.json               # Konfiguracja debuggera
├── include/
│   ├── config.h                  # Konfiguracja sprzętowa i parametry
│   ├── control.h                 # Interfejs systemu sterowania
│   ├── protocol.h                # Definicje protokołu komunikacji
│   └── radio.h                   # Interfejs komunikacji ESP-NOW
├── src/
│   ├── main.cpp                  # Główna pętla programu
│   ├── control.cpp               # Obsługa drążków i kalibracja
│   ├── protocol.cpp              # Implementacja CRC-16/X.25
│   └── radio.cpp                 # Implementacja ESP-NOW
├── platformio.ini                # Konfiguracja PlatformIO
├── README.md                     # Dokumentacja projektu
└── .gitignore                    # Pliki ignorowane przez Git
```

### Modularyzacja Kodu

#### **1. Separacja Konfiguracji (`include/config.h`)**
```cpp
// Wszystkie stałe sprzętowe i systemowe w jednym miejscu
#define PIN_THR   0
#define PIN_YAW   1  
#define PIN_PITCH 4
#define PIN_ROLL  2
#define PIN_ARM   7

#define DEFAULT_DRONE_MAC {0xD8, 0x3B, 0xDA, 0x74, 0x83, 0x68}
#define PACKET_RATE_HZ    50
#define IIR_ALPHA         0.3f
// ... etc
```

#### **2. Zarządzanie Sterowaniem (`control.h/cpp`)**
```cpp
class ControlManager {
    // Enkapsulacja całej logiki sterowania
    bool init();
    void calibrate();
    ControlInputs readInputs();
    
    // Prywatne: kalibracja, filtracja, ARM
    uint16_t updateThrottle();        // Tryb integratora
    int16_t readAxisCentered();       // Tryb proporcjonalny
    void updateArmState();            // Obsługa przycisku ARM
};
```

#### **3. Protokół Komunikacji (`protocol.h/cpp`)**
```cpp
// Struktura pakietu identyczna z oryginałem
#pragma pack(push,1)
struct RcPacket {
    uint8_t  magic;     // 0xA5
    uint8_t  version;   // 1
    uint16_t seq;       // Licznik sekwencji
    uint16_t thr;       // 0..1000
    int16_t  yaw;       // -1000..1000
    int16_t  pitch;     // -1000..1000
    int16_t  roll;      // -1000..1000
    uint8_t  flags;     // bit0=armed
    uint8_t  rssi_hint; // RSSI (obecnie 0)
    uint16_t crc;       // CRC-16/X.25
};
#pragma pack(pop)

uint16_t crc16_x25(const uint8_t* data, size_t len);
```

#### **4. Komunikacja Radiowa (`radio.h/cpp`)**
```cpp
class RadioManager {
    bool init(uint8_t channel = 1);
    bool setPeerMac(const uint8_t* mac);
    bool sendPacket(const void* data, size_t len);
    
    // Enkapsulacja ESP-NOW
    // Automatyczna konfiguracja Wi-Fi
    // Zarządzanie peerami
};
```

#### **5. Główna Pętla (`main.cpp`)**
```cpp
// Zachowano strukturę identyczną z oryginałem
// Globalne obiekty OLED (jak w Arduino)
// Prosta pętla 50Hz z delay(20)
// Bezpośrednie sterowanie OLED

void loop() {
    ControlInputs inputs = control.readInputs();
    
    // Budowanie i wysyłanie pakietu
    RcPacket packet = {};
    // ... wypełnienie pól ...
    radio.sendPacket(&packet, sizeof(packet));
    
    // OLED update (identyczny z oryginałem)
    display.clearDisplay();
    display.setCursor(0, 0);
    display.print("ARM: ");
    display.println(inputs.armed ? "ON" : "OFF");
    // ... etc ...
    
    delay(20); // 50 Hz
}
```

## Zachowane Funkcjonalności

### ✅ **100% Zgodność Behawioralna**
- **Throttle integrator**: Identyczne zachowanie - drążek = szybkość, nie pozycja
- **Kalibracja**: Tylko centra, nie min/max, identyczny flow
- **ARM**: Bez blokad throttle, prosty toggle
- **Filtracja**: IIR α=0.3 na każdej osi
- **Timing**: 50Hz z delay(20ms)
- **OLED**: Identyczne wyświetlanie

### ✅ **Zachowany Protokół**
- **Struktura pakietu**: Byte-to-byte identyczna
- **CRC-16/X.25**: Identyczna implementacja
- **MAC address**: Poprawiony na docelowy
- **ESP-NOW**: Te same parametry kanału i konfiguracji

### ✅ **Zachowane Interfejsy**
- **GPIO mapping**: Identyczne piny
- **ADC**: Te same parametry (12-bit, 11dB)
- **I2C OLED**: Te same adresy i konfiguracja

## Korzyści Transformacji

### **1. Organizacja Kodu**
- **Separacja odpowiedzialności**: Każda klasa ma jasno określone zadanie
- **Łatwość modyfikacji**: Zmiana parametrów w jednym pliku (`config.h`)
- **Testowalność**: Każdy moduł można testować niezależnie

### **2. Rozwój i Utrzymanie**
- **Czytelność**: Kod podzielony logicznie na moduły
- **Rozszerzalność**: Łatwe dodawanie nowych funkcji
- **Debugowanie**: Izolowane błędy w konkretnych modułach

### **3. Narzędzia Deweloperskie**
- **PlatformIO IDE**: Zaawansowane narzędzia build i debug
- **Task automation**: Automatyczne zadania build/upload/monitor
- **Zarządzanie bibliotekami**: Automatyczne pobieranie zależności
- **IntelliSense**: Pełne wsparcie IDE z autouzupełnianiem

### **4. Kontrola Wersji**
- **Git integration**: Pełna historia zmian
- **Modułowa struktura**: Łatwiejsze merge'owanie zmian
- **Dokumentacja**: README i komentarze w kodzie

### **5. Konfiguracja i Deployment**
- **Centralna konfiguracja**: Wszystkie parametry w `config.h`
- **Multiple targets**: Możliwość kompilacji dla różnych płytek
- **CI/CD ready**: Gotowość do automatyzacji build/deploy

## Przykład Użycia

### **Przed (Arduino IDE)**
```cpp
// Wszystko w jednym pliku .ino
// Brak separacji konfiguracji
// Trudne debugowanie
// Brak kontroli wersji
// Ręczne zarządzanie bibliotekami
```

### **Po (PlatformIO)**
```bash
# Clone repository
git clone https://github.com/DanielKusyDev/drone-tx-firmware.git
cd drone-tx-firmware

# Build and upload
pio run --target upload --target monitor

# Modify configuration
# Edit include/config.h
# Rebuild automatically handles dependencies
```

## Podsumowanie

Transformacja kodu Arduino w modularny projekt PlatformIO zachowuje **100% funkcjonalności** oryginalnego kodu, jednocześnie zapewniając:

- **Profesjonalną strukturę projektu**
- **Łatwość rozwoju i utrzymania**  
- **Zaawansowane narzędzia deweloperskie**
- **Kontrolę wersji i dokumentację**
- **Skalowalność dla przyszłych rozszerzeń**

Projekt jest gotowy do dalszego rozwoju przy zachowaniu pełnej kompatybilności z istniejącym odbiornikiem drona.