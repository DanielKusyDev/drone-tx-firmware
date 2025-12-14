# Quick Start Guide - Python Telemetry Bridge

**Get up and running in 5 minutes!**

## Installation

### 1. Check Python

```bash
python --version  # Should be >= 3.11
```

### 2. Create virtual environment

```bash
# In python-bridge directory
python -m venv venv

# Activate
# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate
```

### 3. Install dependencies

```bash
# Install package in editable mode
pip install -e .

# Or install dev dependencies too
pip install -e ".[dev]"
```

### 4. Configure environment

Create a `.env` file:

```bash
TELEMETRY_PORT=/dev/ttyACM0  # or COM3 on Windows
BAUDRATE=115200
```

## Run Tests (no hardware needed)

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html
```

**Expected output:**
```
tests/test_parser.py::test_single_attitude_packet PASSED
tests/test_parser.py::test_multiple_packets PASSED
tests/test_parser.py::test_crc_validation PASSED
...

======= 15 passed in 0.42s =======
```

## Hardware Test (transmitter + drone)

### 1. Prepare transmitter

In Serial Monitor of transmitter (115200 baud):

```bash
U   # Switch to TELEMETRY_BINARY mode
F   # Check that forwarder is working
```

**Expected:**
```
[UART] Mode: TELEMETRY_BINARY
[FORWARDER_STATS]
UART Mode: TELEMETRY_BINARY
Total Forwarded: 523 packets
```

### 2. Check COM port

**Option 1: Using API (after starting server):**
```bash
curl http://localhost:8000/ports
```

**Option 2: Python:**
```bash
python -c "from app.services.telemetry_bridge import TelemetryBridge; print(TelemetryBridge.list_ports())"
```

**Option 3: System commands:**
```bash
# Linux
ls /dev/ttyACM* /dev/ttyUSB*

# Windows
mode
```

### 3. Run FastAPI server

```bash
# Option 1: Direct run (reads .env)
python main.py

# Option 2: Uvicorn with auto-reload (development)
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Option 3: Production
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

**Expected output:**
```
INFO:     Starting telemetry bridge: /dev/ttyACM0 @ 115200
INFO:     Serial port opened: /dev/ttyACM0
INFO:     ✅ Telemetry bridge started successfully
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 4. Test REST endpoints

Open browser:

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

Open browser console (F12):

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
1. Check transmitter Serial Monitor:
   ```
   U  # Toggle to TELEMETRY_BINARY
   F  # Check forwarder stats
   ```

2. Check if drone is sending:
   ```
   E  # Check enhanced telemetry stats
   ```

3. Check FastAPI logs:
   ```
   Look for: "Serial port opened: COM3"
   ```

### Problem 2: Serial port not found

**Symptoms:**
```
serial.SerialException: could not open port 'COM3'
```

**Fix:**
1. List available ports:
   ```bash
   curl http://localhost:8000/ports
   ```

2. Update `.env` with correct port:
   ```bash
   TELEMETRY_PORT=/dev/ttyACM0  # Use the correct port
   ```

3. Check permissions (Linux):
   ```bash
   sudo chmod 666 /dev/ttyACM0
   # or add user to dialout group
   sudo usermod -a -G dialout $USER
   # Log out and back in for group changes to take effect
   ```

4. Restart the server:
   ```bash
   # Stop with Ctrl+C, then restart
   python main.py
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
- Bad USB cable
- Interference
- Baud rate mismatch

**Fix:**
1. Check baud rate in `.env`:
   ```bash
   BAUDRATE=115200  # Must match firmware (default is 115200)
   ```

2. Use better USB cable (avoid cheap or damaged cables)

3. Keep cable away from motors/WiFi/interference sources

4. Check stats to verify if issue persists:
   ```bash
   curl http://localhost:8000/stats
   ```

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

1. **Production deployment:**
   - Use multiple Uvicorn workers: `--workers 4`
   - Enable HTTP/2 with a reverse proxy (Nginx/Caddy)
   - Use systemd for automatic restart on failure

2. **Filter packet types** (if high bandwidth):
   - Configure which packets to forward in firmware
   - Edit `src/telemetry/TelemetryForwarder.h` on transmitter
   - Default: ATT, MOT, STA are forwarded

3. **Monitor performance:**
   ```bash
   # Check stats endpoint
   curl http://localhost:8000/stats

   # Look for CRC errors, packet drops
   # High CRC errors = cable/interference issues
   # Packet drops = check serial buffer settings
   ```

4. **WebSocket optimization:**
   - Limit number of concurrent clients
   - Use message compression for remote clients
   - Implement client-side buffering/throttling

## Support

**Check logs:**
```bash
# FastAPI outputs logs to stdout by default
# Look for errors during startup

# For systemd service:
sudo journalctl -u drone-telemetry -f
```

**Increase log verbosity:**
Edit `app/config.py` and change:
```python
logging.basicConfig(level=logging.DEBUG, ...)
```

**Documentation:**
- Interactive API docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- README: `README.md`
- Testing guide: `TESTING.md`
- Full design: `../.claude/TELEMETRY_SYSTEM_DESIGN.md`

**Useful endpoints for debugging:**
- Health: `GET /health`
- Stats: `GET /stats`
- Ports: `GET /ports`

---

**Status:** ✅ Production Ready
**Quick Start Version:** 2.0
**Last Updated:** 2025-12-14
**Python:** ≥3.11
**Framework:** FastAPI + Uvicorn
