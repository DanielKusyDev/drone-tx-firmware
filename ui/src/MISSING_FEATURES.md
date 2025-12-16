# Missing Features & Incomplete Implementations

## 🔴 CRITICAL - UI Elements Without Backend Integration

### 1. ARM/DISARM Button (Status Bar)
**Location:** `/components/StatusBar.tsx` line 30-39  
**Current State:** ✅ UI exists, ❌ Backend integration missing  
**What Works:**
- Button toggles visual state (red ARMED vs gray DISARMED)
- Button animates when armed
- Shield icon changes color

**What's Missing:**
- No API call to actually arm/disarm the real drone
- Only updates local React state (`setArmed()`)
- Changes don't persist or affect real hardware

**Backend Requirements:**
```typescript
// POST /command/arm
// Response: { success: boolean, armed: true, error?: string }

// POST /command/disarm  
// Response: { success: boolean, armed: false, error?: string }
```

**Frontend Fix Needed:**
```typescript
// In useTelemetryData.ts
const setArmed = async (armed: boolean) => {
  try {
    const endpoint = armed ? '/command/arm' : '/command/disarm';
    const response = await fetch(`${apiBaseUrl}${endpoint}`, {
      method: 'POST'
    });
    const result = await response.json();
    if (result.success) {
      setData(prev => ({ ...prev, armed }));
    }
  } catch (error) {
    console.error('Failed to set armed state:', error);
  }
};
```

---

### 2. Battery Display (Status Bar)
**Location:** `/components/StatusBar.tsx` line 52-55  
**Current State:** ❌ Shows "Future Use" placeholder  
**What's Missing:**
- Battery percentage is received from backend (`battery_pct` in STA packet)
- Data exists in `telemetryData.battery` 
- UI displays "Future Use" instead of actual value

**Frontend Fix Needed:**
```typescript
// Replace line 54 in StatusBar.tsx
<span className="font-mono">{data.battery.toFixed(1)}%</span>

// Optional: Add battery color coding
const getBatteryColor = (pct: number) => {
  if (pct > 50) return '#00ff88';
  if (pct > 20) return '#ffaa00';
  return '#ff3344';
};
```

---

### 3. Alert Acknowledgement Persistence
**Location:** `/components/AlertsPanel.tsx` line 100-106  
**Current State:** ✅ UI works, ❌ Local state only  
**What Works:**
- ACK button marks alerts as acknowledged (visual only)
- State stored in component's `useState`

**What's Missing:**
- Acknowledgements lost on page refresh
- No backend persistence
- Other clients/sessions won't see acknowledgements

**Backend Requirements:**
```typescript
// POST /alerts/{alert_id}/acknowledge
// Request: { alert_id: string }
// Response: { success: boolean, alert_id: string }

// GET /alerts/acknowledged (returns list of acknowledged alert IDs)
// Response: { acknowledged_ids: string[] }
```

**Frontend Fix Needed:**
```typescript
const handleAcknowledge = async (alertId: string) => {
  try {
    await fetch(`${apiBaseUrl}/alerts/${alertId}/acknowledge`, {
      method: 'POST'
    });
    setAcknowledgedAlerts(prev => new Set([...prev, alertId]));
  } catch (error) {
    console.error('Failed to acknowledge alert:', error);
  }
};
```

---

## 🟡 MEDIUM PRIORITY - Missing UI Components

### 4. Flight Mode Selector
**Current State:** ❌ Completely missing  
**What Exists:**
- Flight mode is displayed in StatusBar (line 44-46)
- Modes are defined in `useTelemetryData.ts` (lines 51-60)
- Backend sends mode in STA packet

**What's Missing:**
- No UI to change flight mode
- User cannot switch between STABILIZE, ACRO, ALT_HOLD, etc.

**Backend Requirements:**
```typescript
// POST /command/mode
// Request: { mode: number }  // 0-7 for different modes
// Response: { success: boolean, mode: number, mode_name: string }
```

**Frontend Implementation Needed:**
Create a dropdown or button group in StatusBar:
```tsx
<select 
  value={data.flightMode}
  onChange={(e) => handleModeChange(e.target.value)}
  className="bg-[#00aaff] text-white px-4 py-2 rounded-md font-mono"
>
  <option value="STABILIZE">STABILIZE</option>
  <option value="ACRO">ACRO</option>
  <option value="ALT_HOLD">ALT_HOLD</option>
  <option value="AUTO">AUTO</option>
  <option value="GUIDED">GUIDED</option>
  <option value="LOITER">LOITER</option>
  <option value="RTL">RTL (Return to Launch)</option>
  <option value="LAND">LAND</option>
</select>
```

---

### 5. Serial Port Selector (Settings Panel)
**Current State:** ❌ Missing from UI  
**What Exists:**
- Backend has `/ports` endpoint (see droneApi.ts line 345-347)
- Returns list of available serial ports

**What's Missing:**
- No UI in SettingsPanel to select serial port
- Users cannot choose which port to connect to
- No way to change port without restarting backend

**Backend Requirements:**
```typescript
// GET /ports (already exists)
// Response: { ports: [{ device: string, description: string, hwid: string }] }

// POST /connect  (NEW - needed)
// Request: { port: string, baudrate: number }
// Response: { success: boolean, connected: boolean, port: string }
```

**Frontend Implementation Needed:**
Add to SettingsPanel:
```tsx
const [availablePorts, setAvailablePorts] = useState([]);
const [selectedPort, setSelectedPort] = useState('');

// Fetch ports
useEffect(() => {
  fetch(`${apiBaseUrl}/ports`)
    .then(res => res.json())
    .then(data => setAvailablePorts(data.ports));
}, [apiBaseUrl]);

// UI
<div className="mb-6">
  <label className="text-sm text-gray-400 mb-2 block">SERIAL PORT</label>
  <select 
    value={selectedPort}
    onChange={(e) => setSelectedPort(e.target.value)}
    className="w-full bg-[#1a1a1a] border border-[#333] rounded-md px-3 py-2"
  >
    {availablePorts.map(port => (
      <option key={port.device} value={port.device}>
        {port.device} - {port.description}
      </option>
    ))}
  </select>
  <button onClick={handleConnect}>CONNECT</button>
</div>
```

---

### 6. Calibration Controls
**Current State:** ❌ Completely missing  
**What Exists:**
- Safety flags show calibration status (CAL, CALIB, FAIL)
- Backend sends calibration state in STA.flags

**What's Missing:**
- No button to START calibration
- No button to RESET calibration
- No visual calibration wizard/progress

**Backend Requirements:**
```typescript
// POST /command/calibrate
// Request: { type: 'accel' | 'gyro' | 'mag' | 'level' }
// Response: { success: boolean, calibrating: boolean }

// POST /command/calibrate/abort
// Response: { success: boolean }
```

**Frontend Implementation Needed:**
Add calibration panel (new component or in settings):
```tsx
<div className="bg-[#242424] p-4 rounded-lg">
  <h3>CALIBRATION</h3>
  <div className="space-y-2">
    <button onClick={() => startCalibration('accel')}>
      Calibrate Accelerometer
    </button>
    <button onClick={() => startCalibration('gyro')}>
      Calibrate Gyroscope
    </button>
    <button onClick={() => startCalibration('mag')}>
      Calibrate Magnetometer
    </button>
    <button onClick={() => startCalibration('level')}>
      Calibrate Level Horizon
    </button>
  </div>
</div>
```

---

## 🟢 LOW PRIORITY - Nice-to-Have Features

### 7. PID Tuning Controls
**Current State:** ❌ Missing  
**What Exists:**
- PID tab shows PID performance (setpoint vs actual)
- Backend sends control data in CTL packet

**What's Missing:**
- No UI to adjust PID gains (P, I, D values)
- No way to tune Roll/Pitch/Yaw PIDs
- No save/load PID profiles

**Backend Requirements:**
```typescript
// GET /config/pid
// Response: {
//   roll: { p: number, i: number, d: number },
//   pitch: { p: number, i: number, d: number },
//   yaw: { p: number, i: number, d: number }
// }

// PUT /config/pid
// Request: { roll: {...}, pitch: {...}, yaw: {...} }
// Response: { success: boolean, applied: boolean }
```

---

### 8. Data Logging & Export
**Current State:** ❌ Missing  
**What's Missing:**
- No way to save telemetry data
- No export to CSV/JSON
- No flight log replay

**Backend Requirements:**
```typescript
// POST /logging/start
// Response: { success: boolean, log_id: string }

// POST /logging/stop  
// Response: { success: boolean, log_id: string, file_path: string }

// GET /logs
// Response: { logs: [{ id: string, timestamp: string, duration_s: number }] }

// GET /logs/{log_id}/download
// Response: Binary file (CSV or JSON)
```

---

### 9. Emergency Stop / Kill Switch
**Current State:** ❌ Missing  
**What's Missing:**
- No big red emergency stop button
- No immediate motor cutoff option

**Backend Requirements:**
```typescript
// POST /command/emergency_stop
// Response: { success: boolean, motors_stopped: boolean }
```

**Frontend Implementation:**
Large red button in top-right corner:
```tsx
<button 
  onClick={handleEmergencyStop}
  className="fixed top-20 left-4 bg-[#ff3344] text-white px-6 py-3 rounded-lg font-mono text-lg hover:bg-[#ff4455] animate-pulse"
>
  ⚠️ EMERGENCY STOP
</button>
```

---

### 10. Waypoint / Mission Planning
**Current State:** ❌ Missing  
**What's Missing:**
- No map view
- No waypoint creation
- No mission upload

**Out of Scope** - Would require significant additional work

---

### 11. Video Feed Integration
**Current State:** ❌ Missing  
**What's Missing:**
- No video stream from drone camera
- No FPV view

**Out of Scope** - Would require WebRTC or MJPEG stream

---

### 12. Multi-Drone Support
**Current State:** ❌ Single drone only  
**What's Missing:**
- Cannot connect to multiple drones simultaneously
- No drone selection UI

**Out of Scope** - Architectural change required

---

## 📊 Summary Table

| Feature | UI Exists | Backend API Exists | Priority | Complexity |
|---------|-----------|-------------------|----------|------------|
| ARM/DISARM API Call | ✅ | ❌ | 🔴 Critical | Low |
| Battery Display | ✅ | ✅ | 🔴 Critical | Trivial |
| Alert Acknowledgement Persistence | ✅ | ❌ | 🟡 Medium | Low |
| Flight Mode Selector | ❌ | ❌ | 🟡 Medium | Medium |
| Serial Port Selector | ❌ | Partial (GET only) | 🟡 Medium | Medium |
| Calibration Controls | ❌ | ❌ | 🟡 Medium | Medium |
| PID Tuning | ❌ | ❌ | 🟢 Low | High |
| Data Logging/Export | ❌ | ❌ | 🟢 Low | Medium |
| Emergency Stop | ❌ | ❌ | 🔴 Critical | Low |
| Waypoint Planning | ❌ | ❌ | 🟢 Low | Very High |
| Video Feed | ❌ | ❌ | 🟢 Low | Very High |

---

## 🚀 Quick Win Fixes (Can Implement Now)

### Fix #1: Enable Battery Display (2 minutes)
```typescript
// In StatusBar.tsx, replace line 54:
<span className="font-mono">{data.battery.toFixed(1)}%</span>
```

### Fix #2: Add Emergency Stop Button (5 minutes)
```typescript
// Add to StatusBar.tsx or App.tsx
<button 
  onClick={() => {
    if (confirm('EMERGENCY STOP - Cut all motors immediately?')) {
      setArmed(false);
      // TODO: Add API call when backend ready
    }
  }}
  className="bg-[#ff3344] px-4 py-2 rounded font-mono hover:bg-[#ff4455]"
>
  EMERGENCY STOP
</button>
```

### Fix #3: Add Flight Mode Info Tooltip (10 minutes)
Add helpful information about what each mode does

---

## 📝 LLM-Friendly Backend Requirements (Additional Endpoints)

### Command & Control API
```yaml
POST /command/arm:
  summary: Arm the drone motors
  response:
    success: boolean
    armed: boolean
    error: string (optional)

POST /command/disarm:
  summary: Disarm the drone motors
  response:
    success: boolean
    armed: boolean

POST /command/mode:
  summary: Change flight mode
  request:
    mode: integer (0-7)
  response:
    success: boolean
    mode: integer
    mode_name: string

POST /command/calibrate:
  summary: Start calibration sequence
  request:
    type: enum ['accel', 'gyro', 'mag', 'level']
  response:
    success: boolean
    calibrating: boolean

POST /command/emergency_stop:
  summary: Immediately cut all motors
  response:
    success: boolean
    motors_stopped: boolean

POST /connect:
  summary: Connect to serial port
  request:
    port: string (e.g., "/dev/ttyUSB0")
    baudrate: integer (default: 115200)
  response:
    success: boolean
    connected: boolean
    port: string
```

### Configuration API
```yaml
GET /config/pid:
  summary: Get PID tuning parameters
  response:
    roll: { p: float, i: float, d: float }
    pitch: { p: float, i: float, d: float }
    yaw: { p: float, i: float, d: float }

PUT /config/pid:
  summary: Update PID parameters
  request:
    roll: { p: float, i: float, d: float }
    pitch: { p: float, i: float, d: float }
    yaw: { p: float, i: float, d: float }
  response:
    success: boolean
    applied: boolean
```

### Alerts API
```yaml
POST /alerts/{alert_id}/acknowledge:
  summary: Acknowledge an alert
  parameters:
    alert_id: string (path)
  response:
    success: boolean
    alert_id: string

GET /alerts/acknowledged:
  summary: Get list of acknowledged alert IDs
  response:
    acknowledged_ids: array[string]
```

### Logging API
```yaml
POST /logging/start:
  summary: Start recording telemetry to log file
  response:
    success: boolean
    log_id: string
    file_path: string

POST /logging/stop:
  summary: Stop current logging session
  response:
    success: boolean
    log_id: string
    file_path: string

GET /logs:
  summary: List all saved logs
  response:
    logs: array[{
      id: string,
      timestamp: string,
      duration_s: float,
      file_size_kb: integer
    }]

GET /logs/{log_id}/download:
  summary: Download log file as CSV/JSON
  response: Binary file
```

---

**End of Missing Features Document**
