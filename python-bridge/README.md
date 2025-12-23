# Python Bridge - ESP32 Telemetry & PARAM Communication

**Clean, modular Python bridge** for ESP32 drone telemetry and parameter management. Receives binary telemetry packets over UART and provides bidirectional PARAM communication.

## Features

- **Unified Bridge** - Single UART connection for bidirectional communication (telemetry + PARAM)
- **Modular Architecture** - Composition pattern with single-responsibility components
- **CLI Interface** - Simple command-line tools for testing and debugging
- **Async I/O** - Full asyncio support for efficient serial communication
- **Type Safety** - Pydantic models for all data structures
- **Well Tested** - 60% test coverage with pytest
- **Code Quality** - Ruff for linting and formatting (replaces black, flake8, isort)

## Architecture

```
Serial Port (UART)
       ↓
SerialConnection (async I/O)
       ↓
TelemetryParser (binary parsing + CRC-16/X.25)
       ↓
PacketRouter (route by type)
       ↓
    ┌──────────────┬──────────────┐
    ↓              ↓              ↓
TelemetryStore  ParamHandler  HealthMonitor
  (cache)      (req/resp)     (statistics)
    ↓
Callback → Your application
```

### Component Overview

**Core Modules (`app/core/`):**
- `serial_connection.py` - UART I/O management (~195 lines)
- `packet_router.py` - Type-based packet routing (~90 lines)
- `telemetry_store.py` - Thread-safe telemetry storage (~210 lines)
- `param_handler.py` - PARAM request/response handling (~423 lines)
- `health_monitor.py` - Statistics and health tracking (~106 lines)

**Utilities (`app/utils/`):**
- `crc.py` - CRC-16/X.25 implementation (~68 lines)
- `protocol.py` - Protocol constants and helpers (~119 lines)

**Services (`app/services/`):**
- `telemetry_parser.py` - Binary packet parser (~646 lines)
- `unified_bridge.py` - Main coordinator (~460 lines)

**UnifiedBridge** orchestrates all components and provides a simple API.

## Quick Start

### Installation

Using `uv` (recommended):
```bash
cd python-bridge
uv sync
```

Or using pip:
```bash
cd python-bridge
pip install -e .
```

### Configuration

Create `.env` file (optional, defaults work for most cases):
```bash
TELEMETRY_PORT=COM3  # or /dev/ttyUSB0 on Linux
BAUDRATE=115200
PARAM_TIMEOUT=2.0
HISTORY_SIZE=1000
```

### CLI Usage

**List available serial ports:**
```bash
uv run python cli.py ports
```

**Listen to telemetry stream:**
```bash
uv run python cli.py listen --port COM3
# Press Ctrl+C to stop
```

**PARAM commands:**
```bash
# List all parameters
uv run python cli.py params list --port COM3

# Get parameter value
uv run python cli.py params get 0 --port COM3

# Set parameter value
uv run python cli.py params set 0 300.5 --port COM3
```

## Python API

### Basic Usage

```python
import asyncio
from app.services.unified_bridge import UnifiedBridge

async def main():
    # Create bridge
    bridge = UnifiedBridge('COM3', 115200)

    # Set callback for telemetry packets
    async def on_telemetry(packet):
        print(f"{packet['type']} seq={packet['seq']}")

    bridge.set_telemetry_callback(on_telemetry)

    # Start bridge
    await bridge.start()

    # Query latest packets
    attitude = await bridge.get_latest_attitude()
    if attitude:
        print(f"Roll: {attitude['roll_deg']:.2f}°")

    # Get history
    history = await bridge.get_packet_history('ATT', max_count=100)

    # PARAM operations
    params = await bridge.list_params()
    value = await bridge.get_param(0)
    await bridge.set_param(0, 300.5)

    # Health check
    if await bridge.is_healthy():
        print("✅ Bridge is healthy")

    # Stop bridge
    await bridge.stop()

asyncio.run(main())
```

### Context Manager

```python
async with UnifiedBridge('COM3', 115200) as bridge:
    bridge.set_telemetry_callback(on_telemetry)

    # Use bridge...
    await asyncio.sleep(10)

    # Automatically stops on exit
```

## Supported Telemetry Packets

| Type | Rate | Description |
|------|------|-------------|
| `ATT` | 20 Hz | Roll, pitch, yaw angles + rates |
| `CTL` | 10 Hz | PID setpoints and outputs |
| `MOT` | 5 Hz | Motor commands and throttle |
| `STA` | 2.5 Hz | Armed state, flags, link quality |
| `SENS` | 1.25 Hz | Raw IMU data (accel, gyro, mag) |
| `SAFE` | 1.25 Hz | Ground confidence, error flags |
| `PERF` | 0.625 Hz | Loop timing, CPU, heap |

### Example Packet (ATTITUDE)

```python
{
    'type': 'ATT',
    'ts_us': 123456789,
    'seq': 42,
    'roll_deg': -8.98,
    'pitch_deg': 9.24,
    'yaw_deg': 0.00,
    'roll_rate_dps': -20.5,
    'pitch_rate_dps': 11.5,
    'yaw_rate_dps': 0.0
}
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run specific test file
uv run pytest tests/test_parser.py -v

# Run specific test
uv run pytest tests/test_parser.py -k "attitude" -v
```

### Code Quality (Ruff)

```bash
# Lint code
uv run ruff check .

# Lint + autofix
uv run ruff check --fix .

# Format code
uv run ruff format .

# All at once
uv run ruff check --fix . && uv run ruff format .
```

**Configuration:** See `[tool.ruff]` in `pyproject.toml`
- Line length: 120
- Replaces: black, flake8, isort
- Auto-fixes most issues

### Project Structure

```
python-bridge/
├── app/
│   ├── core/                    # Core components (NEW)
│   │   ├── serial_connection.py     # UART I/O
│   │   ├── packet_router.py         # Packet routing
│   │   ├── telemetry_store.py       # Telemetry storage
│   │   ├── param_handler.py         # PARAM handling
│   │   └── health_monitor.py        # Statistics
│   ├── utils/                   # Utilities (NEW)
│   │   ├── crc.py                   # CRC-16/X.25
│   │   └── protocol.py              # Protocol constants
│   ├── services/
│   │   ├── telemetry_parser.py      # Binary parser
│   │   └── unified_bridge.py        # Main coordinator
│   ├── config.py                # Pydantic settings
│   └── models.py                # Pydantic models
├── tests/                       # Test suite
│   ├── test_parser.py               # Parser tests (645 lines)
│   ├── test_crc.py                  # CRC tests (NEW)
│   ├── test_packet_router.py        # Router tests (NEW)
│   ├── test_telemetry_store.py      # Store tests (NEW)
│   └── test_health_monitor.py       # Monitor tests (NEW)
├── cli.py                       # CLI interface (NEW)
├── pyproject.toml               # Dependencies + config
└── README.md
```

## Troubleshooting

### Problem: No packets received

**Checklist:**
1. Is the transmitter sending packets?
   - Check serial monitor on TX (115200 baud)
   - Send `F` command to see forwarder stats
   - Send `U` command to toggle UART mode to TELEMETRY_BINARY
2. Is the COM port correct?
   ```bash
   uv run python cli.py ports
   ```
3. Is baud rate = 115200?
4. Check cable connection

### Problem: CRC errors

**Possible causes:**
- Weak UART signal (check cable quality)
- Interference (keep away from motors/WiFi)
- Baud rate mismatch

**Debug:**
```python
stats = await bridge.get_stats()
parser_stats = stats['parser']
ratio = parser_stats['crc_errors'] / max(parser_stats['packets_parsed'], 1)
print(f"CRC error rate: {ratio*100:.2f}%")
```

Good: < 1% error rate
Bad: > 5% error rate (check hardware)

### Problem: PARAM timeout

**Possible causes:**
- Drone not responding (not running PARAM firmware)
- UART not in correct mode (check with `U` command on TX)
- Cable disconnected

**Debug:**
```bash
# Try increasing timeout
export PARAM_TIMEOUT=5.0
uv run python cli.py params list
```

## Performance

**Bandwidth:**
- Default config (7 packet types): ~1 kB/s
- UART 115200 baud = ~11 kB/s theoretical
- Margin: >90% free bandwidth

**Latency:**
- Serial read: ~1-10 ms
- Parse: <1 ms per packet
- Total: <20 ms end-to-end

**CPU:**
- Read loop: ~1-2% CPU
- Parser: <1% CPU
- Total: <5% CPU on Raspberry Pi 4

## Technical Details

### Protocol

**Magic Byte:** `0x5B`
**Version:** `2`
**CRC:** CRC-16/X.25 (polynomial 0x8408)

**Packet Structure:**
```
[Header: 10 bytes] [Payload: variable] [CRC: 2 bytes]

Header:
- magic: uint8 (0x5B)
- version: uint8 (2)
- type: uint8 (0x01-0x07, 0x10-0x11)
- flags: uint8
- seq: uint16
- timestamp_us: uint32
```

See `docs/transmitter/telemetry.md` in parent directory for detailed packet specifications.

### Architecture Benefits

**Before refactoring:**
- 805 lines monolithic bridge
- Duplicated CRC code (2x)
- 18% test coverage
- FastAPI overhead

**After refactoring:**
- ~460 lines coordinator + modular components
- Single CRC implementation
- 60% test coverage
- Lightweight CLI

**Key improvements:**
- Single Responsibility Principle per module
- Easy to test components independently
- Clear dependency graph
- Faster development iteration

## Future Enhancements

### Ready to add:
- [ ] FastAPI integration (models already compatible)
- [ ] WebSocket streaming
- [ ] Data persistence (SQLite/TimescaleDB)
- [ ] Prometheus metrics export

### Needs design:
- [ ] Command & control (send commands to drone)
- [ ] Multi-drone support
- [ ] Data compression (binary → JSON is verbose)

## License

MIT

## Authors

- Claude (Anthropic) - Refactoring & architecture
- Daniel - System design & integration

---

**Status:** ✅ Production Ready (refactored 2025-12-23)
**Version:** 0.2.0
**Python:** ≥3.11
**Dependencies:** pyserial-asyncio, pydantic-settings, aiorwlock, click
