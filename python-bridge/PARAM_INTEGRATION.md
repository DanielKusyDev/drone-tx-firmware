# PARAM System Integration Guide

## Overview

The PARAM system enables real-time parameter management for the drone via binary protocol over UART. This document describes the complete integration between the drone firmware, ESP32-C3 controller (transmitter), Python bridge, and React UI.

## Architecture

```
┌─────────────┐    WebSocket     ┌──────────────┐    UART      ┌─────────────┐    ESP-NOW    ┌────────────┐
│  React UI   │ ←─────────────→ │ FastAPI      │ ←──────────→ │ Controller  │ ←───────────→ │ Drone      │
│  Dashboard  │   JSON messages  │ Backend      │   Binary     │ ESP32-C3    │   Binary      │ ESP32-S3   │
└─────────────┘                  └──────────────┘   Telemetry  └─────────────┘   Telemetry   └────────────┘
                                        ↕
                                 ┌──────────────┐
                                 │ Python       │
                                 │ UART Bridge  │
                                 └──────────────┘
```

**Key Point:** There is NO direct USB connection to the drone. All communication goes through the controller (transmitter).

## Binary Protocol Specification

### UART Connection

- **Port:** Configured in `.env` file (default: `/dev/ttyACM0`)
- **Baud rate:** 115200
- **Data bits:** 8
- **Parity:** None
- **Stop bits:** 1
- **Protocol:** Binary (NOT text!)

### Packet Structure

#### Constants

```python
MAGIC_BYTE = 0x5B
PROTOCOL_VERSION = 2
TELEM_PARAM_REQUEST = 0x10
TELEM_PARAM_RESPONSE = 0x11
```

#### Request Packet (Computer → Drone) - 20 bytes

```c
struct TelemetryParamRequest {
    // Header (12 bytes with padding)
    uint8_t  magic;         // 0x5B
    uint8_t  version;       // 2
    uint8_t  type;          // 0x10 (TELEM_TYPE_PARAM_REQUEST)
    uint8_t  flags;         // 0
    uint16_t seq;           // Sequence number (little-endian)
    uint8_t  _padding[2];   // 2-byte padding for alignment
    uint32_t timestamp_us;  // Timestamp in microseconds (little-endian)

    // Payload (6 bytes)
    uint8_t  command;       // PARAM_CMD_LIST / GET / SET
    uint8_t  param_index;   // Parameter index (0-255)
    float    value;         // New value (for SET command only)

    // Footer (2 bytes)
    uint16_t crc;           // CRC-16/X.25 (all bytes except CRC)
};
// Total: 20 bytes
```

**Python struct format:** `<BBBBHxxIBBf` + CRC

#### Response Packet (Drone → Computer) - 57 bytes

```c
struct TelemetryParamResponse {
    // Header (12 bytes with padding)
    uint8_t  magic;          // 0x5B
    uint8_t  version;        // 2
    uint8_t  type;           // 0x11 (TELEM_TYPE_PARAM_RESPONSE)
    uint8_t  flags;          // 0
    uint16_t seq;            // Sequence number (matches request)
    uint8_t  _padding[2];    // 2-byte padding
    uint32_t timestamp_us;   // Timestamp

    // Payload (43 bytes with padding)
    uint8_t  command;        // PARAM_CMD_LIST_RESP / GET_RESP / SET_RESP / ERROR
    uint8_t  param_index;    // Parameter index
    uint8_t  param_type;     // 0x06 = float
    uint8_t  param_access;   // 0x00 = readonly, 0x01 = readwrite
    float    value;          // Current parameter value
    uint8_t  _padding2;      // 1-byte padding after float
    char     group[16];      // Parameter group name (null-terminated)
    char     name[16];       // Parameter name (null-terminated)
    uint8_t  total_params;   // Total number of parameters (for LIST)
    uint8_t  error_code;     // 0 = success, >0 = error

    // Footer (2 bytes)
    uint16_t crc;            // CRC-16/X.25
};
// Total: 57 bytes
```

**Python struct format:** `<BBBBHxxI` (header) + `<BBBBfx16s16sBB` (payload) + CRC

### Commands

```python
# Request commands
PARAM_CMD_LIST = 0x01  # List parameters
PARAM_CMD_GET = 0x02   # Get parameter value
PARAM_CMD_SET = 0x03   # Set parameter value

# Response commands
PARAM_CMD_LIST_RESP = 0x81
PARAM_CMD_GET_RESP = 0x82
PARAM_CMD_SET_RESP = 0x83
PARAM_CMD_ERROR = 0xFF

# Error codes
ERROR_INDEX_OUT_OF_RANGE = 1
ERROR_PARAM_NOT_FOUND = 2
ERROR_READ_FAILED = 3
ERROR_WRITE_FAILED = 4
ERROR_UNKNOWN_COMMAND = 5
```

### CRC-16/X.25

```python
def crc16_x25(data: bytes) -> int:
    """CRC-16/X.25 (init=0xFFFF, poly=0x8408 reflected, final=~)"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return (~crc) & 0xFFFF
```

## Available Parameters (Drone Firmware)

Total: 6 parameters (all in `pid_attitude` group, type=float, access=readwrite)

| Index | Group | Name | Default Value | Description |
|-------|-------|------|---------------|-------------|
| 0 | pid_attitude | roll_rate_kp | 250.0 | Roll rate P gain |
| 1 | pid_attitude | roll_rate_ki | 500.0 | Roll rate I gain |
| 2 | pid_attitude | pitch_rate_kp | 250.0 | Pitch rate P gain |
| 3 | pid_attitude | pitch_rate_ki | 500.0 | Pitch rate I gain |
| 4 | pid_attitude | yaw_rate_kp | 120.0 | Yaw rate P gain |
| 5 | pid_attitude | yaw_rate_ki | 16.7 | Yaw rate I gain |

**Note:** Changes are NOT persisted to NVS in Phase 1.5 - they reset on drone reboot.

## Python Bridge Usage

### Installation

```bash
cd /home/daniel/drone/transmitter-firmware/python-bridge
source .venv/bin/activate  # or use uv
pip install -r requirements.txt
```

### Configuration (.env)

```env
TELEMETRY_PORT=/dev/ttyACM0
PARAM_UART_PORT=/dev/ttyACM0  # Same as telemetry
PARAM_UART_BAUDRATE=115200
PARAM_UART_TIMEOUT=2.0
PARAM_UART_RECONNECT_INTERVAL=5.0
```

### Running the Bridge

```bash
# Start FastAPI server
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Or with python
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

### Python API Examples

```python
import asyncio
from app.services.param_uart_bridge import ParamUARTBridge

async def example():
    bridge = ParamUARTBridge(timeout=2.0)
    await bridge.connect("/dev/ttyACM0", 115200)

    # List all parameters
    params = await bridge.list_params()
    for p in params:
        print(f"[{p['index']}] {p['group']}.{p['name']} = {p['value']}")

    # Get single parameter
    value = await bridge.get_param(0)
    print(f"Current value: {value}")

    # Set parameter
    await bridge.set_param(0, 300.5)
    print("Parameter updated!")

    await bridge.disconnect()

asyncio.run(example())
```

## REST API Endpoints

### GET /params

Get list of all parameters with current values.

**Response:**
```json
{
  "type": "list_response",
  "params": [
    {
      "index": 0,
      "group": "pid_attitude",
      "name": "roll_rate_kp",
      "type": 6,
      "access": 1,
      "value": 250.0
    },
    ...
  ]
}
```

### GET /params/{index}

Get single parameter value.

**Response:**
```json
{
  "type": "get_response",
  "index": 0,
  "value": 250.0,
  "status": "success"
}
```

### PUT /params/{index}

Set parameter value.

**Request body:**
```json
{
  "value": 300.5
}
```

**Response:**
```json
{
  "status": "success",
  "value": 300.5
}
```

### GET /params/connection-status

Get PARAM connection status.

**Response:**
```json
{
  "uart_connected": true,
  "last_update": "2025-12-20T12:34:56.789Z"
}
```

## WebSocket API (/params/live)

Real-time bidirectional parameter management.

### Client → Server Messages

#### LIST
```json
{"action": "list"}
```

#### GET
```json
{"action": "get", "index": 0}
```

#### SET
```json
{"action": "set", "index": 0, "value": 300.5}
```

### Server → Client Messages

#### LIST Response
```json
{
  "type": "list_response",
  "params": [...]
}
```

#### GET Response
```json
{
  "type": "get_response",
  "index": 0,
  "value": 250.0,
  "status": "success"
}
```

#### SET Response
```json
{
  "type": "set_response",
  "index": 0,
  "value": 300.5,
  "status": "success"
}
```

#### Connection Status (broadcast)
```json
{
  "type": "connection_status",
  "uart_connected": true,
  "controller_connected": true,
  "timestamp": "2025-12-20T12:34:56.789Z"
}
```

#### Parameter Changed (broadcast to all clients)
```json
{
  "type": "param_changed",
  "index": 0,
  "value": 300.5,
  "changed_by": "client_123"
}
```

#### Error Response
```json
{
  "type": "error",
  "code": "PARAM_NOT_FOUND",
  "message": "Parameter index 99 not found",
  "index": 99
}
```

## JavaScript/React Example

```javascript
const ws = new WebSocket('ws://localhost:8000/params/live');

ws.onopen = () => {
  // List all params
  ws.send(JSON.stringify({action: "list"}));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);

  if (data.type === 'list_response') {
    console.log('Parameters:', data.params);

    // Get first param
    ws.send(JSON.stringify({action: "get", index: 0}));
  }

  if (data.type === 'get_response') {
    console.log(`Param ${data.index} = ${data.value}`);

    // Set new value
    ws.send(JSON.stringify({action: "set", index: 0, value: 300.5}));
  }

  if (data.type === 'param_changed') {
    console.log(`Param ${data.index} changed to ${data.value} by ${data.changed_by}`);
    // Update UI
  }
};
```

## Testing

### Run Unit Tests

```bash
pytest tests/test_param_uart_bridge.py -v
```

All 16 tests should pass:
- CRC calculation tests
- Packet building tests
- Packet parsing tests
- Bridge initialization tests
- Connect/disconnect tests
- GET/SET parameter tests
- Error handling tests
- Statistics tests

### Manual Testing

```bash
# Test Python bridge directly
python3 -m app.services.param_uart_bridge /dev/ttyACM0

# Test via REST API
curl http://localhost:8000/params
curl http://localhost:8000/params/0
curl -X PUT http://localhost:8000/params/0 -H 'Content-Type: application/json' -d '{"value": 300.5}'

# Test connection status
curl http://localhost:8000/params/connection-status
```

## Troubleshooting

### No UART Connection

1. Check port: `ls -la /dev/ttyACM*` or `ls -la /dev/ttyUSB*`
2. Check permissions: `sudo usermod -a -G dialout $USER` (logout/login required)
3. Verify controller is connected and powered
4. Check `.env` has correct port

### Timeout Errors

1. Verify controller is running transmitter firmware
2. Check that drone is powered and within ESP-NOW range
3. Verify MAC addresses match between controller and drone
4. Increase timeout in config: `PARAM_UART_TIMEOUT=5.0`

### CRC Errors

1. Check UART baud rate matches (115200)
2. Verify binary mode (not text mode)
3. Check for electromagnetic interference
4. Try shorter/better shielded USB cable

### No Drone Response

1. Check drone is powered and running
2. Verify ESP-NOW connection (check telemetry packets)
3. Ensure controller sees drone via ESP-NOW
4. Check drone firmware has PARAM system implemented

## Success Criteria

✅ Bridge connects to UART
✅ LIST command returns all 6 PID parameters
✅ GET command reads parameter value
✅ SET command changes value and drone confirms
✅ WebSocket endpoint `/params/live` works
✅ Broadcast changes to all connected clients
✅ CRC validation works (rejects invalid packets)
✅ Timeout handling works (doesn't hang when drone offline)
✅ Auto-reconnect works after disconnection
✅ All 16 unit tests pass

## Next Steps

1. **Firmware Integration:** Implement PARAM system in drone firmware (ESP32-S3)
2. **UI Dashboard:** Build React UI for parameter tuning
3. **Persistence:** Add NVS storage in drone firmware for parameter persistence
4. **Advanced Features:** Parameter validation, range limits, profiles

## References

- Binary Protocol: See user specification in task description
- CRC-16/X.25: Standard polynomial 0x8408 (reflected)
- ESP-NOW: [Espressif Documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/network/esp_now.html)
- FastAPI: [Official Docs](https://fastapi.tiangolo.com/)
- WebSockets: [MDN Web Docs](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
