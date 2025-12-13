# Quick Start Guide - Python Telemetry Bridge

## Instalacja (5 minut)

### 1. Sprawdź Python

```bash
python --version  # Powinno być >= 3.9
```

### 2. Utwórz virtual environment

```bash
# W katalogu python-bridge
python -m venv venv

# Aktywuj
# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate
```

### 3. Zainstaluj dependencies

```bash
pip install -r requirements.txt
```

## Test Parsera (bez hardware)

```bash
python test_parser.py
```

**Expected output:**
```
=== Test 1: Single ATTITUDE Packet ===
✅ Single packet test passed!

=== Test 2: Multiple Packets ===
✅ Multiple packets test passed!

...

✅ ALL TESTS PASSED!
```

## Test z Hardware (nadajnik + dron)

### 1. Przygotowanie nadajnika

W Serial Monitor nadajnika (115200 baud):

```bash
U   # Przełącz na TELEMETRY_BINARY mode
F   # Sprawdź że forwarder działa
```

**Expected:**
```
[UART] Mode: TELEMETRY_BINARY
[FORWARDER_STATS]
UART Mode: TELEMETRY_BINARY
Total Forwarded: 523 packets
```

### 2. Sprawdź port COM

**Windows:**
```bash
python
>>> from serial_reader import list_serial_ports
>>> for p in list_serial_ports(): print(p['device'], p['description'])
COM3 USB Serial Port (COM3)
```

**Linux:**
```bash
ls /dev/ttyUSB*
# lub
python -c "from serial_reader import list_serial_ports; print([p['device'] for p in list_serial_ports()])"
```

### 3. Uruchom FastAPI server

```bash
# Option 1: CLI
python fastapi_example.py --port COM3 --baudrate 115200

# Option 2: Uvicorn
uvicorn fastapi_example:app --host 0.0.0.0 --port 8000 --reload
```

**Expected output:**
```
INFO:     Starting telemetry bridge: COM3 @ 115200
INFO:     Serial port opened: COM3
INFO:     Serial reader thread started
INFO:     ✅ Telemetry bridge started successfully
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 4. Test REST endpoints

Otwórz przeglądarkę:

**API Documentation:**
```
http://localhost:8000/docs
```

**Get latest telemetry:**
```
http://localhost:8000/telemetry/latest
```

**Expected response:**
```json
{
  "ATT": {
    "type": "ATT",
    "ts_us": 123456789,
    "seq": 42,
    "roll_deg": -8.98,
    "pitch_deg": 9.24,
    ...
  },
  "MOT": { ... },
  "STA": { ... }
}
```

**Health check:**
```
http://localhost:8000/health
```

### 5. Test WebSocket

Otwórz browser console (F12):

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/telemetry');

ws.onopen = () => console.log('✅ Connected');

ws.onmessage = (event) => {
    const packet = JSON.parse(event.data);
    console.log(`${packet.type} seq=${packet.seq}`);
};

ws.onerror = (error) => console.error('❌ Error:', error);
```

**Expected output:**
```
✅ Connected
ATT seq=123
MOT seq=45
STA seq=67
ATT seq=124
...
```

## Troubleshooting

### Problem 1: No packets received

**Symptoms:**
```
GET /telemetry/latest
→ 404 Not Found: "No telemetry received yet"
```

**Fix:**
1. Sprawdź Serial Monitor nadajnika:
   ```
   U  # Toggle to TELEMETRY_BINARY
   F  # Check forwarder stats
   ```

2. Sprawdź czy dron wysyła:
   ```
   E  # Check enhanced telemetry stats
   ```

3. Sprawdź logi FastAPI:
   ```
   Look for: "Serial port opened: COM3"
   ```

### Problem 2: Serial port not found

**Symptoms:**
```
serial.SerialException: could not open port 'COM3'
```

**Fix:**
1. List ports:
   ```bash
   python fastapi_example.py --list-ports
   ```

2. Try correct port:
   ```bash
   python fastapi_example.py --port COM4
   ```

3. Check permissions (Linux):
   ```bash
   sudo chmod 666 /dev/ttyUSB0
   # lub dodaj użytkownika do grupy dialout
   sudo usermod -a -G dialout $USER
   ```

### Problem 3: CRC errors in stats

**Symptoms:**
```
GET /stats
{
  "reader": {
    "parser_stats": {
      "crc_errors": 123
    }
  }
}
```

**Possible causes:**
- Zły kabel USB
- Interference
- Baud rate mismatch

**Fix:**
1. Sprawdź baud rate:
   ```bash
   python fastapi_example.py --baudrate 115200  # Must match firmware
   ```

2. Użyj lepszego kabla USB

3. Trzymaj kabel z dala od silników/WiFi

## Next Steps

### React UI Integration

1. Create React app:
   ```bash
   npx create-react-app drone-ui
   cd drone-ui
   ```

2. Connect to WebSocket:
   ```javascript
   const ws = new WebSocket('ws://localhost:8000/ws/telemetry');
   ```

3. Update state on packet:
   ```javascript
   ws.onmessage = (event) => {
       const packet = JSON.parse(event.data);
       // Update Zustand/Redux store
   };
   ```

**See:** `.claude/TELEMETRY_SYSTEM_DESIGN.md` section 7 for complete React integration

### Production Deployment

1. **Environment variables:**
   ```bash
   export TELEMETRY_PORT=/dev/ttyUSB0
   export TELEMETRY_BAUDRATE=115200
   ```

2. **Run with systemd:**
   ```ini
   [Unit]
   Description=Drone Telemetry API

   [Service]
   ExecStart=/path/to/venv/bin/python fastapi_example.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

3. **Nginx reverse proxy:**
   ```nginx
   location /api/ {
       proxy_pass http://localhost:8000/;
   }

   location /ws/ {
       proxy_pass http://localhost:8000/ws/;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection "upgrade";
   }
   ```

## Performance Tips

1. **Reduce history size** (if low memory):
   ```python
   bridge = TelemetryBridge('COM3', 115200, history_size=100)
   ```

2. **Filter packet types** (if high bandwidth):
   ```python
   # Forward only ATT, MOT, STA (not CTL, SENS, etc.)
   # Configure in firmware: src/telemetry/TelemetryForwarder.h
   ```

3. **Use Redis** (for multi-instance):
   ```python
   # TODO: Redis integration for scaling
   ```

## Support

**Logs:**
```bash
# Increase log level
python fastapi_example.py --log-level debug
```

**Documentation:**
- API docs: http://localhost:8000/docs
- README: `README.md`
- Full design: `.claude/TELEMETRY_SYSTEM_DESIGN.md`

---

*Quick Start v1.0*
*Last updated: 2025-12-03*
