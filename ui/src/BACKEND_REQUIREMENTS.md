# Drone Telemetry Dashboard - Backend Implementation Requirements

## Overview
This document specifies the complete backend API requirements for a professional drone telemetry dashboard. The frontend React application is fully implemented and expects a WebSocket-based real-time telemetry streaming service with REST API endpoints for configuration and control.

---

## Architecture

**Technology Stack:** Python (FastAPI recommended), WebSocket, REST API  
**Base URL:** `http://localhost:8000` (configurable in frontend)  
**WebSocket Endpoint:** `ws://localhost:8000/ws/telemetry`  
**CORS:** Must allow frontend origin (typically `http://localhost:5173` for Vite dev server)

---

## 1. WebSocket Telemetry Streaming

### Endpoint
```
ws://localhost:8000/ws/telemetry
```

### Behavior
- **Connection:** Frontend establishes WebSocket connection on app load
- **Streaming:** Server sends individual telemetry packets as JSON messages at various frequencies
- **Packet Types:** 7 different packet types (see below)
- **Frequency:** 
  - ATT (Attitude): ~20 Hz (every 50ms)
  - MOT (Motors): ~5 Hz (every 200ms)
  - STA (Status): ~1 Hz (every 1000ms)
  - CTL (Control): ~20 Hz (every 50ms)
  - SENS (Sensors): ~10 Hz (every 100ms)
  - PERF (Performance): ~2 Hz (every 500ms)
  - SAFETY: ~1 Hz (every 1000ms)

### Packet Format
Each packet is a JSON object with the following structure:

#### 1.1 ATT - Attitude Packet (20 Hz)
```json
{
  "type": "ATT",
  "ts_us": 1234567890,
  "seq": 12345,
  "roll_deg": 5.23,
  "pitch_deg": -2.45,
  "yaw_deg": 180.5,
  "roll_rate_dps": 12.3,
  "pitch_rate_dps": -8.5,
  "yaw_rate_dps": 3.2
}
```

**Fields:**
- `type` (string): Always "ATT"
- `ts_us` (integer): Timestamp in microseconds
- `seq` (integer): Sequence number (monotonically increasing)
- `roll_deg` (float): Roll angle in degrees (-180 to 180)
- `pitch_deg` (float): Pitch angle in degrees (-90 to 90)
- `yaw_deg` (float): Yaw angle/heading in degrees (0 to 360)
- `roll_rate_dps` (float): Roll rate in degrees per second
- `pitch_rate_dps` (float): Pitch rate in degrees per second
- `yaw_rate_dps` (float): Yaw rate in degrees per second

#### 1.2 MOT - Motors Packet (5 Hz)
```json
{
  "type": "MOT",
  "ts_us": 1234567890,
  "seq": 234,
  "motors": [32768, 33000, 32500, 33200],
  "motors_actual": [32700, 32950, 32450, 33150],
  "throttle": 32768,
  "mixer_id": 0
}
```

**Fields:**
- `type` (string): Always "MOT"
- `ts_us` (integer): Timestamp in microseconds
- `seq` (integer): Sequence number
- `motors` (array[4]): Commanded motor values [M1, M2, M3, M4] (0-65535, 16-bit range)
- `motors_actual` (array[4]): Actual motor values from ESC feedback (0-65535)
- `throttle` (integer): Base throttle value (0-65535)
- `mixer_id` (integer): Motor mixer type (0=QUAD_X, 1=QUAD_PLUS, 2=HEX_X, 3=HEX_PLUS)

**Motor Layout for QUAD_X:**
- M1 = Front Right
- M2 = Rear Right
- M3 = Rear Left
- M4 = Front Left

#### 1.3 STA - Status Packet (1 Hz)
```json
{
  "type": "STA",
  "ts_us": 1234567890,
  "seq": 45,
  "armed": false,
  "mode": 0,
  "ground_state": 1,
  "link_quality": 95,
  "battery_pct": 87.5,
  "uptime_s": 1234.5,
  "loop_rate_hz": 250,
  "flags": {
    "ARM": false,
    "HRZ": true,
    "LINK": true,
    "DISARM": false,
    "CAL": true,
    "CALIB": false,
    "FAIL": false
  }
}
```

**Fields:**
- `type` (string): Always "STA"
- `ts_us` (integer): Timestamp in microseconds
- `seq` (integer): Sequence number
- `armed` (boolean): Whether drone is armed
- `mode` (integer): Flight mode (0=STABILIZE, 1=ACRO, 2=ALT_HOLD, 3=AUTO, 4=GUIDED, 5=LOITER, 6=RTL, 7=LAND)
- `ground_state` (integer): Ground detection state
- `link_quality` (float): Radio link quality percentage (0-100)
- `battery_pct` (float): Battery percentage (0-100)
- `uptime_s` (float): System uptime in seconds
- `loop_rate_hz` (integer): Control loop frequency
- `flags` (object): Safety flags
  - `ARM` (boolean): Armed status
  - `HRZ` (boolean): Horizon check OK
  - `LINK` (boolean): Link alive
  - `DISARM` (boolean): Force disarm triggered
  - `CAL` (boolean): Calibration OK
  - `CALIB` (boolean): Currently calibrating
  - `FAIL` (boolean): Calibration failed

#### 1.4 CTL - Control Packet (20 Hz)
```json
{
  "type": "CTL",
  "ts_us": 1234567890,
  "seq": 5678,
  "set_roll_deg": 10.0,
  "set_pitch_deg": -5.0,
  "set_yaw_rate_dps": 0.0,
  "rate_set_roll_dps": 50.0,
  "rate_set_pitch_dps": -25.0,
  "out_roll": 0.3,
  "out_pitch": -0.15,
  "out_yaw": 0.0,
  "pid_gains_scale": 1.0,
  "throttle_gain_scale": 1.0
}
```

**Fields:**
- `type` (string): Always "CTL"
- `ts_us` (integer): Timestamp in microseconds
- `seq` (integer): Sequence number
- `set_roll_deg` (float): Roll angle setpoint
- `set_pitch_deg` (float): Pitch angle setpoint
- `set_yaw_rate_dps` (float): Yaw rate setpoint
- `rate_set_roll_dps` (float): Roll rate setpoint
- `rate_set_pitch_dps` (float): Pitch rate setpoint
- `out_roll` (float): Roll PID output (-1 to 1)
- `out_pitch` (float): Pitch PID output (-1 to 1)
- `out_yaw` (float): Yaw PID output (-1 to 1)
- `pid_gains_scale` (float): PID gains scaling factor
- `throttle_gain_scale` (float): Throttle gain scaling factor

#### 1.5 SENS - Sensors Packet (10 Hz)
```json
{
  "type": "SENS",
  "ts_us": 1234567890,
  "seq": 890,
  "accel_mg": [100, -50, 1000],
  "gyro_mdps": [1000, -500, 200],
  "mag_mgauss": [300, 400, -200],
  "temperature_c": 35.5
}
```

**Fields:**
- `type` (string): Always "SENS"
- `ts_us` (integer): Timestamp in microseconds
- `seq` (integer): Sequence number
- `accel_mg` (array[3]): Accelerometer [X, Y, Z] in milligravity
- `gyro_mdps` (array[3]): Gyroscope [X, Y, Z] in milli-degrees per second
- `mag_mgauss` (array[3]): Magnetometer [X, Y, Z] in milligauss
- `temperature_c` (float): IMU temperature in Celsius

#### 1.6 PERF - Performance Packet (2 Hz)
```json
{
  "type": "PERF",
  "ts_us": 1234567890,
  "seq": 123,
  "loop_time_us": 4000,
  "imu_time_us": 1500,
  "control_time_us": 2000,
  "cpu_usage_pct": 45.5,
  "free_heap_kb": 128,
  "stack_usage_pct": 60.0
}
```

**Fields:**
- `type` (string): Always "PERF"
- `ts_us` (integer): Timestamp in microseconds
- `seq` (integer): Sequence number
- `loop_time_us` (integer): Control loop execution time in microseconds
- `imu_time_us` (integer): IMU read time in microseconds
- `control_time_us` (integer): Control calculation time in microseconds
- `cpu_usage_pct` (float): CPU usage percentage
- `free_heap_kb` (integer): Free heap memory in KB
- `stack_usage_pct` (float): Stack usage percentage

#### 1.7 SAFETY - Safety Packet (1 Hz)
```json
{
  "type": "SAFETY",
  "ts_us": 1234567890,
  "seq": 67,
  "ground_confidence": 0.95,
  "safety_gates": 7,
  "error_flags": 0,
  "total_flight_time_s": 3600.0,
  "crash_count": 2
}
```

**Fields:**
- `type` (string): Always "SAFETY"
- `ts_us` (integer): Timestamp in microseconds
- `seq` (integer): Sequence number
- `ground_confidence` (float): Ground detection confidence (0-1)
- `safety_gates` (integer): Number of passed safety gates
- `error_flags` (integer): Error flags bitmask
- `total_flight_time_s` (float): Total flight time in seconds
- `crash_count` (integer): Number of recorded crashes

---

## 2. REST API Endpoints

### 2.1 Health Check
```
GET /health
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "last_packet_age_s": 0.05,
  "packets_received": 12345,
  "is_alive": true
}
```

**Purpose:** Check if backend is alive and receiving data from drone

---

### 2.2 Get Latest Telemetry (All Packets)
```
GET /telemetry/latest
```

**Response (200 OK):**
```json
{
  "ATT": { /* Latest ATT packet */ },
  "MOT": { /* Latest MOT packet */ },
  "STA": { /* Latest STA packet */ },
  "CTL": { /* Latest CTL packet */ },
  "SENS": { /* Latest SENS packet */ },
  "SAFE": null,
  "PERF": { /* Latest PERF packet */ },
  "SAFETY": { /* Latest SAFETY packet */ }
}
```

**Purpose:** Get the most recent packet of each type (used for initial state load)

---

### 2.3 Get Latest Attitude
```
GET /telemetry/attitude
```

**Response (200 OK):**
```json
{
  "type": "ATT",
  "ts_us": 1234567890,
  "seq": 12345,
  "roll_deg": 5.23,
  "pitch_deg": -2.45,
  "yaw_deg": 180.5,
  "roll_rate_dps": 12.3,
  "pitch_rate_dps": -8.5,
  "yaw_rate_dps": 3.2
}
```

---

### 2.4 Get Latest Motors
```
GET /telemetry/motors
```

**Response (200 OK):**
```json
{
  "type": "MOT",
  "ts_us": 1234567890,
  "seq": 234,
  "motors": [32768, 33000, 32500, 33200],
  "motors_actual": [32700, 32950, 32450, 33150],
  "throttle": 32768,
  "mixer_id": 0
}
```

---

### 2.5 Get Latest Status
```
GET /telemetry/status
```

**Response (200 OK):**
```json
{
  "type": "STA",
  "ts_us": 1234567890,
  "seq": 45,
  "armed": false,
  "mode": 0,
  "ground_state": 1,
  "link_quality": 95,
  "battery_pct": 87.5,
  "uptime_s": 1234.5,
  "loop_rate_hz": 250,
  "flags": { /* ... */ }
}
```

---

### 2.6 Get Packet History
```
GET /telemetry/history/{packet_type}?max_count={count}
```

**Parameters:**
- `packet_type` (path): Packet type (ATT, MOT, STA, CTL, SENS, PERF, SAFETY)
- `max_count` (query, optional): Maximum number of packets to return (default: 100)

**Response (200 OK):**
```json
{
  "packet_type": "ATT",
  "count": 100,
  "packets": [
    { /* ATT packet 1 */ },
    { /* ATT packet 2 */ },
    { /* ... */ }
  ]
}
```

**Purpose:** Used for populating historical charts on initial load

---

### 2.7 Get Stats
```
GET /stats
```

**Response (200 OK):**
```json
{
  "total_packets": 50000,
  "packets_per_type": {
    "ATT": 25000,
    "MOT": 6250,
    "STA": 1250,
    "CTL": 25000,
    "SENS": 12500,
    "PERF": 2500,
    "SAFETY": 1250
  },
  "uptime_s": 2500.0,
  "websocket_connections": 1
}
```

---

### 2.8 Get Available Serial Ports
```
GET /ports
```

**Response (200 OK):**
```json
{
  "ports": [
    {
      "device": "/dev/ttyUSB0",
      "description": "USB Serial Port",
      "hwid": "USB VID:PID=10C4:EA60"
    },
    {
      "device": "COM3",
      "description": "USB-SERIAL CH340",
      "hwid": "USB VID:PID=1A86:7523"
    }
  ]
}
```

**Purpose:** List available serial ports for drone connection (optional feature)

---

## 3. Implementation Requirements

### 3.1 WebSocket Server
- **Concurrent connections:** Support at least 1 simultaneous client
- **Auto-reconnect handling:** Handle client disconnections gracefully
- **Packet buffering:** Buffer last N packets per type for history endpoint
- **Frequency control:** Emit packets at specified frequencies (see section 1)

### 3.2 Data Source Options
The backend should support multiple data sources:

**Option A: Serial/UART from ESP32 Drone**
- Read telemetry packets from serial port (e.g., `/dev/ttyUSB0` at 115200 baud)
- Parse incoming binary/text protocol
- Convert to JSON format
- Stream via WebSocket

**Option B: UDP Telemetry Stream**
- Listen on UDP port for telemetry packets
- Parse incoming packets
- Convert to JSON
- Stream via WebSocket

**Option C: Simulated Data Generator**
- Generate realistic telemetry data for testing
- Use sine waves for smooth attitude changes
- Simulate armed/disarmed transitions
- Generate random alerts

### 3.3 Error Handling
- **WebSocket errors:** Log and attempt reconnection
- **Invalid packets:** Skip and log malformed packets
- **Data source disconnection:** Set `is_alive: false` in `/health` endpoint
- **CORS errors:** Ensure proper CORS headers for frontend origin

### 3.4 Performance Requirements
- **Latency:** <50ms from packet receipt to WebSocket transmission
- **Throughput:** Handle 20 Hz packet rate (20 packets/second minimum)
- **Memory:** Maintain history buffer without memory leaks
- **CPU:** Minimal CPU usage (<10% on modern hardware)

---

## 4. Testing Requirements

### 4.1 Unit Tests
- Packet parsing and validation
- History buffer management
- WebSocket connection handling

### 4.2 Integration Tests
- End-to-end WebSocket streaming
- REST API endpoints
- Data source connection

### 4.3 Load Tests
- Multiple concurrent WebSocket clients
- High-frequency packet transmission (>20 Hz)
- Long-running connections (>1 hour)

---

## 5. Deployment

### 5.1 Development
```bash
# Example for FastAPI + Python
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 5.2 Production
- Use production ASGI server (e.g., `uvicorn` with workers)
- Add authentication/authorization if needed
- Use reverse proxy (nginx) for SSL termination
- Monitor with logging and metrics

### 5.3 Docker (Optional)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 6. Example Implementation Pseudocode

```python
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store latest packets
latest_packets = {
    "ATT": None,
    "MOT": None,
    "STA": None,
    "CTL": None,
    "SENS": None,
    "SAFE": None,
    "PERF": None,
    "SAFETY": None,
}

# WebSocket endpoint
@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Simulate or read real data
            att_packet = generate_att_packet()
            await websocket.send_json(att_packet)
            await asyncio.sleep(0.05)  # 20 Hz
    except Exception as e:
        print(f"WebSocket error: {e}")

# REST endpoints
@app.get("/health")
async def health():
    return {"status": "ok", "is_alive": True}

@app.get("/telemetry/latest")
async def get_latest():
    return latest_packets

# ... other endpoints
```

---

## 7. Frontend Integration Notes

### 7.1 Frontend Configuration
The frontend has a settings panel (⚙️ icon) where users can:
- **API Base URL:** Change backend URL (default: `http://localhost:8000`)
- **Simulated Mode:** Toggle between real and simulated data

### 7.2 WebSocket Reconnection
- Frontend automatically reconnects on disconnect
- Maximum 10 reconnection attempts with exponential backoff
- Connection status shown in top-right corner

### 7.3 Data Aggregation
Frontend accumulates individual packets into a unified state:
- Each packet type updates its respective fields
- History is maintained client-side (last 100-200 points)
- Alerts are generated from safety flag changes

---

## 8. Optional Features (Future)

### 8.1 Command & Control API
```
POST /command/arm
POST /command/disarm
POST /command/mode/{mode_id}
POST /command/calibrate
```

### 8.2 Logging & Playback
```
GET /logs/list
GET /logs/{log_id}/download
POST /logs/{log_id}/replay
```

### 8.3 Configuration Management
```
GET /config
PUT /config
POST /config/reset
```

---

## 9. Summary Checklist

Backend implementation must provide:
- [ ] WebSocket server at `/ws/telemetry`
- [ ] Stream 7 packet types at specified frequencies
- [ ] REST API for latest telemetry (`/telemetry/latest`)
- [ ] REST API for packet history (`/telemetry/history/{type}`)
- [ ] Health check endpoint (`/health`)
- [ ] CORS support for frontend
- [ ] Packet buffering for history
- [ ] Handle reconnections gracefully
- [ ] Generate realistic simulated data OR connect to real drone
- [ ] Performance: <50ms latency, 20+ Hz packet rate

---

## 10. Contact & Support

For questions about frontend integration:
- Check frontend code: `/hooks/useTelemetryData.ts` and `/services/droneApi.ts`
- Review WebSocket packet handling logic
- Test with simulated mode first, then switch to real backend

---

**End of Backend Requirements Document**
