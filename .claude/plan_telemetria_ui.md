# Plan integracji ustrukturyzowanej telemetrii z UI (dron + nadajnik)

Ten dokument opisuje **plan działania** potrzebny do:
- wprowadzenia **ustrukturyzowanych logów / telemetrii**, 
- wykonania **zmian po stronie kontrolera**, które umożliwią integrację z UI (React + WebSocket bridge).

Dokument ma służyć jako **kontekst dla innego AI**, więc celowo opisuje założenia, decyzje i etapy prac.

---

## 1. Cele i założenia ogólne

1. Oddzielić dwa światy:
   - **Logi debugowe dla człowieka** (dowolny format, „ładne” stringi),
   - **Telemetrię maszynową** (stabilny, jednoznaczny format do parsowania przez skrypt + UI).
2. Wykorzystać istniejący system telemetrii drona (Enhanced Telemetry) zamiast wymyślać drugi protokół.
3. Zapewnić:
   - możliwość odbioru telemetrii na **ESP32-C3 (nadajnik)**,
   - przekazanie jej po **UART** do hosta (Python bridge),
   - ekspozycję do **React UI** przez WebSocket.
4. Zminimalizować zmiany w istniejącym firmware – ewolucja, nie rewolucja.

---

## 2. Stan obecny (wysokopoziomowy)

- Dron i nadajnik komunikują się przez **ESP-NOW**.
- Po stronie kontrolera (flight controller + nadajnik) istnieje system telemetrii, ale:
  - na UART/USB idą głównie **logi tekstowe** (linie typu `TEL: ATT: ...`),
  - format jest **niejednoznaczny** i słabo parsowalny dla narzędzi automatycznych.
- Cel: przejść z „logów tekstowych” do **świadomie zaprojektowanego strumienia telemetrii**, który można:
  - przekierować do pliku,
  - wystawić do UI,
  - wykorzystać do analizy lotów.

---

## 3. Docelowa architektura przepływu danych

1. **Dron (ESP32-S3 / FC)** generuje pakiety telemetrii w formacie **Enhanced Telemetry** (binarny, z nagłówkiem, typem, CRC).
2. Pakiety telemetrii są wysyłane:
   - radiowo: **ESP-NOW → nadajnik (ESP32-C3)**,
   - lokalnie: **UART / USB** do hosta (opcjonalne, np. do blackboxa lub bezpośredniego logowania).
3. **Nadajnik (ESP32-C3)**:
   - odbiera pakiety po ESP-NOW,
   - **w trybie telemetrycznym** przepuszcza je dalej po **UART** w tym samym formacie (lub minimalnie opakowanym).
4. **Python bridge (na PC)**:
   - czyta po UART ustrukturyzowane pakiety,
   - dekoduje je (`struct.unpack` + walidacja CRC),
   - mapuje na obiekty/JSON,
   - wystawia strumień po **WebSocket** do UI.
5. **React UI**:
   - łączy się z WebSocketem,
   - aktualizuje store (np. Zustand/Redux) na podstawie pakietów,
   - renderuje komponenty: sztuczny horyzont, wykresy silników, status systemu itd.

Z tego dokumentu: **Python bridge i React są poza zakresem implementacji**, ale ich istnienie wpływa na format i projekt telemetrii.

---

## 4. Plan dla ustrukturyzowanych logów / telemetrii

### 4.1. Rozdzielenie logów i telemetrii

**Decyzja:**  
Wprowadzamy dwa rozłączne kanały na UART:

1. **Kanał LOG (tekstowy)** – dla człowieka:
   - prefiks `LOG:`,
   - dowolny format, wykorzystywany głównie w trybie debugowym.
2. **Kanał TEL (binarny)** – dla maszyn:
   - format zgodny z Enhanced Telemetry,
   - brak `printf`, brak tekstu, tylko binarne ramki.

**Konsekwencja projektowa:**
- Firmware nadajnika musi mieć **tryb pracy**:
  - `DEBUG_TEXT` – logi tekstowe jak do tej pory,
  - `TELEMETRY_BINARY` – wyłączamy większość logów tekstowych; po UART lecą tylko pakiety binarne.

### 4.2. Format pakietów telemetrycznych (referencja / przypomnienie)

Docelowo używamy struktury:
- wspólny nagłówek `TelemetryHeader`:
  - `magic` (np. `0x5B`),
  - `version` (np. `2`),
  - `type` (enum: ATTITUDE, MOTORS, STATUS, CONTROL, PERF, …),
  - `flags`,
  - `seq`,
  - `timestamp_us`,
- payload zależny od `type`,
- `crc16` na końcu pakietu.

To jest **jedyny „kontrakt”**, którego trzeba się trzymać dla spójności z dronem i UI.

### 4.3. Minimalny zestaw typów pakietów

Na potrzeby UI (sztuczny horyzont, silniki, status) wystarczą:

1. `ATTITUDE` – roll, pitch, yaw + prędkości kątowe.
2. `MOTORS` – aktualne wartości (komendy/act) dla każdego silnika + ogólny throttle.
3. `STATUS` – uzbrojenie, tryb, RSSI/link, napięcie baterii, flagi bezpieczeństwa.
4. (Opcjonalnie) `CONTROL` – setpointy PID, użyteczne do tuningu (nie wymagane do podstawowego UI).

### 4.4. Dwa etapy wprowadzania struktury

#### Etap 1: „tekst, ale deterministyczny” (szybki krok pośredni)

Jeżeli wymagane jest szybkie uruchomienie Pythona i UI bez od razu grzebania w binarce, można przejściowo:

- Wprowadzić **kanoniczny tekstowy format** telemetrii (np. CSV/`key=value`), np.:
  - `ATT,ts=...,seq=...,roll=...,pitch=...,yaw=...,rr=...,pr=...,yr=...`
  - `MOT,ts=...,seq=...,m0=...,m1=...,m2=...,m3=...,thr=...`
  - `STA,ts=...,seq=...,armed=...,mode=...,link=...,uptime=...`
- Python parsuje to liniami (`split(',')`, `split('=')`),
- UI korzysta z JSON-a generowanego w bridge.

To jest **wariant tymczasowy**, aby szybko dostarczyć działający UI.

#### Etap 2: Pełna binarka (docelowo)

- W firmware nadajnika implementujemy ścieżkę:
  - odbiór binarnego pakietu z drona,
  - ewentualna minimalna modyfikacja (np. dopisanie pola „source”),
  - wysłanie po UART bajt w bajt (lub w minimalnie zmodyfikowanym formacie).
- Python bridge przechodzi z parsowania linii na parser pakietów binarnych:
  - buforowanie bajtów,
  - wyszukiwanie `magic`,
  - odczyt długości / typu,
  - weryfikacja CRC,
  - dekodowanie i konwersja na JSON.

---

## 5. Plan zmian po stronie kontrolera / nadajnika

Poniżej lista **konkretnych zadań** do wykonania w firmware, aby integracja z UI była możliwa.

### 5.1. Dodanie trybów pracy UART

**Task 1:** Wprowadzić globalną konfigurację trybu UART, np.:

```c
typedef enum {
    UART_MODE_DEBUG_TEXT,
    UART_MODE_TELEMETRY_BINARY
} UartMode;

static UartMode uart_mode = UART_MODE_DEBUG_TEXT;
```

- Domyślnie: `UART_MODE_DEBUG_TEXT` (zachowanie jak teraz).
- Możliwość przełączenia:
  - komendą po UART (np. `CFG:UART=TELBIN` / `CFG:UART=DEBUG`),
  - lub ilością `#ifdef`/`#define` przy kompilacji (prostsze na start).

**Task 2:** Wszystkie miejsca używające `printf` / logów mają być świadome trybu:
- w `TELEMETRY_BINARY` logi tekstowe są ograniczone do minimum lub wyłączone,
- w `DEBUG_TEXT` telemetria binarna może być wyłączona lub ograniczona.

### 5.2. Ścieżka przelotu telemetrii do UART

**Task 3:** Na nadajniku (ESP32-C3) dodać moduł:

- nasłuchuje na przychodzące pakiety Enhanced Telemetry (po ESP-NOW),
- dla każdego poprawnego pakietu:
  - jeśli `uart_mode == UART_MODE_TELEMETRY_BINARY` → wysyła go na UART.

Dwa możliwe warianty implementacyjne:

1. **Forward 1:1**  
   - Pakiet z drona jest wysyłany **bez zmian** na UART (ten sam `TelemetryHeader`, ten sam payload, ten sam `crc`).
2. **Forward z lokalnym nagłówkiem** (opcjonalnie)  
   - Nadajnik dokleja własny mini-header (np. identyfikator linku, RSSI), a następnie oryginalny pakiet.
   - Wymaga dopisania obsługi w Pythonie, ale daje więcej informacji.

Na początek zalecany jest **wariant 1:1**, bo jest prostszy i spójny z tym, co już istnieje po stronie drona.

### 5.3. Synchronizacja częstotliwości i zestawu pakietów

**Task 4:** Ustalić, jakie typy pakietów i z jaką częstotliwością mają iść do UI (przez nadajnik):

- `ATTITUDE` – 20 Hz (lub wyżej, jeśli potrzebne do płynniejszej animacji),
- `MOTORS` – 5–10 Hz,
- `STATUS` – 1–2 Hz.

Te wartości powinny być:
- skonfigurowane po stronie drona (scheduler telemetrii),
- odzwierciedlone 1:1 na nadajniku (forward „jak leci”).

**Task 5:** Dopilnować, żeby kolejność i sekwencja (`seq`) pakietów była spójna między dronem a bridge’em – ułatwia to debugowanie i wykrywanie braków.

### 5.4. Opcjonalne: równoległe logi tekstowe na osobnym porcie

W przyszłości można rozważyć:

- osobny UART tylko do logów tekstowych,
- lub multiplexing logów i telemetrii z prostym framingiem na jednym porcie.

Na tym etapie projektu **nie jest to wymagane**, ale warto, aby inny AI przy projektowaniu dalej pamiętał o tej opcji.

---

## 6. Wymagania dla integracji z UI (kontrakt z Python / React)

Poniższa sekcja to „kontrakt”, którego powinien trzymać się Python bridge i UI – ważne jako kontekst dla innego AI.

### 6.1. Co musi wyjść z kontrolera / nadajnika

1. Strumień pakietów telemetrycznych w formacie:

   - `TelemetryHeader` + payload + `crc16`
   - typy co najmniej: `ATTITUDE`, `MOTORS`, `STATUS`

2. Stabilny `timestamp_us` i `seq`:
   - `timestamp_us` pozwala na interpolację w UI,
   - `seq` umożliwia wykrywanie utraconych pakietów.

3. Znana endianowość (przyjmujemy little-endian na ESP32 i w bridge).

### 6.2. Zakładany format JSON dla UI

Inny AI może założyć następujące mapowanie pakietów binarnych na JSON (przykład, można lekko zmienić):

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

```json
{
  "type": "MOT",
  "ts_us": 123456800,
  "seq": 43,
  "motors": [0, 5120, 31488, 4864],
  "throttle": 2686
}
```

```json
{
  "type": "STA",
  "ts_us": 123456820,
  "seq": 44,
  "armed": true,
  "mode": 0,
  "link_quality": 100,
  "uptime_s": 45,
  "flags": {
    "ARM": 1,
    "HRZ": 1,
    "CAL": 1,
    "CALIB": 0,
    "FAIL": 0,
    "FD": 0
  }
}
```

Python bridge:
- jest odpowiedzialny za *tłumaczenie binarki na JSON*,
- UI nie musi znać szczegółów protokołu binarnego – opiera się tylko na JSON.

---

## 7. Podsumowanie planu

1. **Rozdzielić logi i telemetrię**:
   - wprowadzić tryby UART (`DEBUG_TEXT` vs `TELEMETRY_BINARY`),
   - traktować telemetrię jako osobny, stabilny protokół, nie jako logi.

2. **Użyć istniejącego Enhanced Telemetry** jako podstawy formatu:
   - forward pakietów z drona na nadajnik,
   - opcjonalne tymczasowe wsparcie dla „kanonicznego tekstu”.

3. **W nadajniku dodać ścieżkę forwardowania telemetrii na UART**:
   - odbiór ESP-NOW,
   - wysyłka pakietów telemetrycznych po UART,
   - ustalić częstotliwości wysyłki dla ATT/MOT/STA.

4. **Zdefiniować kontrakt dla Python bridge i UI**:
   - co dokładnie wychodzi z nadajnika (pakiety, typy, pola),
   - przykładowe mapowanie na JSON.

Ten plan jest punktem odniesienia dla kolejnego AI, które może:
- doprojektować szczegóły protokołu,
- napisać kod po stronie firmware,
- przygotować Python bridge i UI w React.
