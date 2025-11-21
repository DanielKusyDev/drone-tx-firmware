# Transmitter Log Format Documentation

## Overview

The transmitter firmware produces structured logs showing telemetry reception, radio transmission status, and user input events. Logs are output over serial (115200 baud) and categorized by subsystem prefix.

---

## Log Categories

### 1. **TEL (Telemetry)** - Received from Drone

Telemetry packets are received from the drone via ESP-NOW and decoded based on packet type. The enhanced telemetry system uses different packet types transmitted at varying rates.

#### **TEL: ATT** - Attitude Data (20 Hz)
Flight orientation and angular rates.

```
TEL: ATT: R=6.45 P=3.80 Y Rate=97.90 seq=402
```

**Fields:**
- `R` - Roll angle (degrees, ×0.01 resolution)
- `P` - Pitch angle (degrees, ×0.01 resolution)
- `Y Rate` - Yaw rate (degrees/second, ×0.1 resolution)
- `seq` - Sequence number (monotonic, per packet type)

**Update Rate:** ~20 Hz (50ms intervals)

---

#### **TEL: CTL** - PID Control Data (10 Hz)
Control system setpoints and outputs.

```
TEL: CTL: setR=0.00 setP=0.00 setYR=0.0 rateSetR=0.0 rateSetP=0.0 outR=0.0 outP=0.0 outY=0.0 thrScale=1.00 seq=200
```

**Fields:**
- `setR`, `setP` - Angle setpoints for roll/pitch from RC input (degrees, ×0.01)
- `setYR` - Yaw rate setpoint from RC input (deg/s, ×0.1)
- `rateSetR`, `rateSetP` - Rate setpoints from angle PID (deg/s, ×0.1)
- `outR`, `outP`, `outY` - PID outputs for roll/pitch/yaw (×10 scaling)
- `thrScale` - Throttle-dependent gain scaling factor

**Update Rate:** ~10 Hz (100ms intervals)

---

#### **TEL: MOT** - Motor and Mixer Data (5 Hz)
Motor commands and actual outputs.

```
TEL: MOT: cmd=[0 0 0 0] act=[0 0 0 0] seq=99 THR=0
TEL: MOT: cmd=[2048 2048 4096 1792] act=[2048 2048 4096 1792] seq=141 THR=2162
```

**Fields:**
- `cmd=[M1 M2 M3 M4]` - Motor commands (0-65535 range)
- `act=[M1 M2 M3 M4]` - Actual motor outputs (may differ if feedback available)
- `THR` - Base throttle value from RC input
- `seq` - Sequence number

**Update Rate:** ~5 Hz (200ms intervals)

**Motor Mapping:** Platform-dependent (see mixer configuration)

---

#### **TEL: STA** - System Status (2.5 Hz)
Overall system state and safety flags.

```
TEL: STA: armed=0 mode=0 link=0% uptime=18s seq=49 [ARM:0 HRZ:1 CAL:1 CALIB:0 FAIL:0 FD:0]
TEL: STA: armed=1 mode=0 link=100% uptime=23s seq=65 [ARM:1 HRZ:1 CAL:1 CALIB:0 FAIL:0 FD:0]
```

**Fields:**
- `armed` - Arming state (0=disarmed, 1=armed)
- `mode` - Flight mode identifier
- `link` - RC link quality percentage (0-100%)
- `uptime` - Drone uptime in seconds
- `seq` - Sequence number

**Safety Flags (bitfield):**
- `ARM` - Armed state (bit 0 of `armed` field)
- `HRZ` - Horizon/level OK (accelerometer within safe limits)
- `CAL` - Accelerometer calibration valid
- `CALIB` - Calibration in progress
- `FAIL` - Calibration failed
- `FD` - Force disarm triggered

**Update Rate:** ~2.5 Hz (400ms intervals)

---

### 2. **RAD (Radio)** - ESP-NOW Transmission Status

Radio transmission success/failure tracking logged every 1 second.

```
RAD: RC: queued seq=1699, 50 ACK (last 1s)
RAD: RC: queued seq=1749, 50 ACK (last 1s)
```

**Fields:**
- `queued seq` - Last RC packet sequence number sent
- `ACK` - Number of successfully acknowledged packets in last 1 second
- `FAIL` - Number of failed transmissions (shown if > 0)

**RC Packet Rate:** 50 Hz (20ms intervals)

**Example with failures:**
```
RAD: RC: queued seq=1699, 48 ACK, 2 FAIL (last 1s)
```

---

### 3. **INP (Input)** - User Input Events

Button press detection and arm state changes.

```
INP: Press duration: 139 ms
INP: Short press - ARM toggle
```

**Event Types:**
- **Short press** (< 500ms) - ARM/DISARM toggle
- **Long press** (≥ 500ms) - Calibration trigger
- **Press duration** - Measured button hold time

**Behavior:**
- Short press toggles armed state when safe (horizon OK, calibration valid)
- Long press initiates accelerometer calibration sequence

---

## Log Reading Examples

### Example 1: Normal Flight Sequence

```
TEL: STA: armed=0 mode=0 link=100% uptime=18s seq=49 [ARM:0 HRZ:1 CAL:1 CALIB:0 FAIL:0 FD:0]
INP: Press duration: 149 ms
INP: Short press - ARM toggle
TEL: STA: armed=1 mode=0 link=100% uptime=23s seq=65 [ARM:1 HRZ:1 CAL:1 CALIB:0 FAIL:0 FD:0]
TEL: MOT: cmd=[0 2304 4608 1536] act=[0 2304 4608 1536] seq=142 THR=2162
```

**Interpretation:**
1. Drone disarmed, link good, horizon OK, calibration valid
2. User short-presses arm button
3. Drone arms successfully
4. Motors spin up with throttle input

---

### Example 2: Link Quality Monitoring

```
TEL: STA: armed=0 mode=0 link=0% uptime=18s seq=49 [ARM:0 HRZ:1 CAL:1 CALIB:0 FAIL:0 FD:0]
TEL: STA: armed=0 mode=0 link=100% uptime=18s seq=50 [ARM:0 HRZ:1 CAL:1 CALIB:0 FAIL:0 FD:0]
RAD: RC: queued seq=1699, 50 ACK (last 1s)
```

**Interpretation:**
1. Link quality starts at 0% (initial packets)
2. Link quality reaches 100% (stable reception)
3. All 50 RC packets acknowledged in 1-second window (perfect transmission)

---

### Example 3: High-Rate Attitude During Flight

```
TEL: ATT: R=7.45 P=0.40 Y Rate=52.40 seq=590
TEL: ATT: R=7.64 P=0.94 Y Rate=192.30 seq=593
TEL: ATT: R=8.43 P=-1.80 Y Rate=678.40 seq=627
TEL: ATT: R=8.78 P=-1.22 Y Rate=870.70 seq=629
```

**Interpretation:**
- Roll/pitch angles increasing (7.45° → 8.78°)
- Yaw rate escalating rapidly (52° → 870°/s)
- Likely aggressive yaw input or loss of control
- Attitude updates every ~50ms (20 Hz rate)

---

## Timing and Synchronization

### Telemetry Packet Rates (from Drone to Transmitter)

| Packet Type | Rate (Hz) | Interval (ms) | Purpose |
|-------------|-----------|---------------|---------|
| ATTITUDE    | 20        | 50            | Real-time orientation feedback |
| CONTROL     | 10        | 100           | PID performance monitoring |
| MOTORS      | 5         | 200           | Motor state verification |
| STATUS      | 2.5       | 400           | System health checks |
| SENSORS     | 1.25      | 800           | Raw IMU data (if enabled) |
| SAFETY      | 1.25      | 800           | Diagnostics and flight time |
| PERFORMANCE | 0.625     | 1600          | CPU/memory metrics |

### RC Packet Transmission (Transmitter to Drone)

- **Rate:** 50 Hz (20ms intervals)
- **Structure:** 16-byte RcPacket
- **CRC:** CRC-16/X.25 validation
- **Acknowledgment:** ESP-NOW delivery confirmation

---

## Sequence Number Behavior

Each telemetry packet type maintains its own monotonic sequence counter:

```
TEL: ATT: ... seq=402
TEL: CTL: ... seq=200    ← Different counter
TEL: MOT: ... seq=99     ← Different counter
TEL: STA: ... seq=49     ← Different counter
```

**Purpose:**
- Detect packet loss per telemetry type
- Verify correct packet ordering
- Counters wrap at 65535 (uint16_t)

**RC Packet Sequence:**
```
RAD: RC: queued seq=1699
RAD: RC: queued seq=1749  ← Incremented by 50 (1 second @ 50 Hz)
```

---

## Safety Flag Interpretation

### Horizon Safety (HRZ)

```
[ARM:0 HRZ:1 CAL:1 CALIB:0 FAIL:0 FD:0]  ← Safe to arm
[ARM:0 HRZ:0 CAL:1 CALIB:0 FAIL:0 FD:0]  ← UNSAFE - drone tilted beyond threshold
```

**HRZ=0 indicates:**
- Roll or pitch angle exceeds safe threshold (typically ±45°)
- Arming is blocked
- Prevents arming when drone is not level

### Calibration Status

```
[ARM:0 HRZ:1 CAL:1 CALIB:0 FAIL:0 FD:0]  ← Calibration valid
[ARM:0 HRZ:1 CAL:0 CALIB:1 FAIL:0 FD:0]  ← Calibration in progress
[ARM:0 HRZ:1 CAL:0 CALIB:0 FAIL:1 FD:0]  ← Calibration failed
```

**States:**
- `CAL=1` - Valid calibration loaded
- `CALIB=1` - Calibration procedure running (keep drone still)
- `FAIL=1` - Calibration attempt failed (excessive movement detected)

### Force Disarm (FD)

```
[ARM:1 HRZ:1 CAL:1 CALIB:0 FAIL:0 FD:1]  ← Force disarm activated
```

**Trigger Conditions:**
- Extreme attitude angles during flight
- Safety system emergency cutoff
- Crash detection

---

## Motor Command Ranges

Motor commands use 16-bit unsigned integers (0-65535):

```
cmd=[0 0 0 0]                          ← Motors off
cmd=[2048 2048 2048 2048]              ← Low throttle, balanced
cmd=[15104 15104 15104 15104]          ← Medium throttle, balanced
cmd=[0 24064 36352 0]                  ← Asymmetric (active control)
cmd=[65535 65535 65535 65535]          ← Maximum throttle (rare)
```

**Typical Ranges:**
- **0** - Motor off (disarmed or zero throttle)
- **1000-5000** - Idle/hover range
- **10000-30000** - Active flight
- **40000-65535** - High power (emergency recovery)

---

## Debugging Workflow

### 1. Verify Radio Link

```bash
# Look for consistent 50 ACK counts
grep "RAD:" logs.txt
```

**Expected:** `50 ACK (last 1s)` continuously
**Problem:** `ACK < 50` or `FAIL > 0` indicates radio issues

### 2. Check Telemetry Reception

```bash
# Count telemetry packets per type
grep "TEL: ATT:" logs.txt | wc -l
grep "TEL: STA:" logs.txt | wc -l
```

**Expected rates over 10 seconds:**
- ATT: ~200 packets (20 Hz)
- STA: ~25 packets (2.5 Hz)

### 3. Monitor Safety Flags

```bash
# Extract safety flag changes
grep "TEL: STA:" logs.txt | grep -E "HRZ:0|FAIL:1|FD:1"
```

**No output** = All safety checks passing

### 4. Analyze Flight Behavior

```bash
# Track motor activity
grep "TEL: MOT:" logs.txt | grep -v "cmd=\[0 0 0 0\]"
```

**Shows when motors were active** (non-zero commands)

---

## Common Log Patterns

### Normal Idle (Disarmed)

```
TEL: ATT: R=6.45 P=3.80 Y Rate=97.90 seq=402
TEL: CTL: setR=0.00 setP=0.00 setYR=0.0 ... seq=200
TEL: MOT: cmd=[0 0 0 0] act=[0 0 0 0] seq=99 THR=0
TEL: STA: armed=0 mode=0 link=100% uptime=18s seq=49 [ARM:0 HRZ:1 CAL:1 CALIB:0 FAIL:0 FD:0]
RAD: RC: queued seq=1699, 50 ACK (last 1s)
```

**Characteristics:**
- Motors off (`cmd=[0 0 0 0]`)
- No RC setpoints (`setR=0.00`)
- Link quality 100%
- All safety flags OK

### Armed Hover

```
TEL: ATT: R=7.05 P=2.48 Y Rate=101.40 seq=520
TEL: CTL: setR=0.00 setP=0.00 setYR=0.0 rateSetR=0.0 rateSetP=0.0 ... seq=259
TEL: MOT: cmd=[2048 2048 2048 2048] act=[2048 2048 2048 2048] seq=129 THR=2162
TEL: STA: armed=1 mode=0 link=100% uptime=23s seq=64 [ARM:1 HRZ:1 CAL:1 CALIB:0 FAIL:0 FD:0]
```

**Characteristics:**
- Armed (`armed=1`)
- Balanced motor commands
- Low throttle (~2000)
- Minimal control inputs

### Active Flight with Control

```
TEL: ATT: R=8.43 P=-1.80 Y Rate=678.40 seq=627
TEL: CTL: setR=0.00 setP=0.00 setYR=0.0 rateSetR=0.0 rateSetP=0.0 ... seq=313
TEL: MOT: cmd=[10240 10240 21504 1280] act=[10240 10240 21504 1280] seq=156 THR=10420
```

**Characteristics:**
- High yaw rate (678°/s)
- Asymmetric motor commands (active stabilization)
- Motor 3 at 21504 (high), Motor 4 at 1280 (low)
- Compensating for rotation

### Loss of Control / Crash

```
TEL: ATT: R=8.78 P=-1.22 Y Rate=870.70 seq=629
TEL: ATT: R=9.01 P=-2.68 Y Rate=1342.80 seq=632
TEL: ATT: R=11.44 P=-3.77 Y Rate=2657.70 seq=634
TEL: ATT: R=17.71 P=13.32 Y Rate=3130.00 seq=639
TEL: MOT: cmd=[0 0 0 0] act=[0 0 0 0] seq=170 THR=34274
TEL: STA: armed=1 mode=0 link=100% uptime=29s seq=84 [ARM:1 HRZ:1 CAL:1 CALIB:0 FAIL:0 FD:0]
```

**Characteristics:**
- Escalating yaw rate (870° → 3130°/s)
- Large attitude changes (R: 8.78° → 17.71°)
- Motors cut to zero despite high throttle value
- Likely force disarm or crash detection

---

## Notes

- **Timestamps:** Not included in current log format (sequence numbers provide ordering)
- **Binary Logs:** Not implemented (all output is human-readable ASCII)
- **Log Verbosity:** Controlled by serial commands (`verbose`, `quiet`)
- **Buffering:** Logs are unbuffered for real-time monitoring

---

*Generated from transmitter firmware logs dated 2025-11-18*
