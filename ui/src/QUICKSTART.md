# Quick Start Guide

Get the drone telemetry dashboard connected to your API in 3 minutes.

## Prerequisites

- Drone telemetry API server running
- WebSocket endpoint available at `/ws/telemetry`
- CORS configured (see below)

## Step 1: Start Your API Server

```bash
# Example with FastAPI
python main.py

# Should see:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     WebSocket route /ws/telemetry is active
```

## Step 2: Open the Dashboard

Open the dashboard in your browser (or start the dev server):

```bash
# If running locally
npm install
npm run dev

# Then open http://localhost:5173
```

## Step 3: Configure Connection

1. **Click the Settings icon** (⚙️) in the top-right corner
2. **Select "REAL API"** as the data source
3. **Enter your API URL**: `http://localhost:8000`
4. **Click "APPLY"**

## Step 4: Verify Connection

Look at the **top-left corner** of the dashboard:

- ✅ **Green "CONNECTED"** = Success! You're receiving data
- ❌ **Red "DISCONNECTED"** = See troubleshooting below
- 🟧 **Orange "SIMULATED"** = Still in demo mode

## Troubleshooting

### "DISCONNECTED" Status

**Check 1: Is the API server running?**
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy","is_alive":true,...}
```

**Check 2: Is WebSocket endpoint available?**
```bash
# Using websocat (install: cargo install websocat)
websocat ws://localhost:8000/ws/telemetry

# Or check browser console for WebSocket errors
```

**Check 3: CORS configured?**
```python
# FastAPI CORS configuration
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specific origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Check 4: Firewall/Proxy issues?**
- WebSocket uses port 8000 (same as HTTP)
- Some proxies block WebSocket upgrades
- Try direct connection (no proxy)

### Still Not Working?

1. **Open browser DevTools** (F12)
2. **Go to Console tab**
3. Look for error messages:
   - "WebSocket connection failed"
   - "CORS policy blocked"
   - "Failed to parse message"
4. **Go to Network tab**
5. Filter by "WS"
6. Check WebSocket status

### Test with Simulated Data

To verify the dashboard works:

1. Click Settings
2. Select "SIMULATED"
3. Click "ARMED" in top bar
4. You should see simulated flight data

## API Requirements

Your API server must:

### 1. WebSocket Endpoint
```python
@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = {
            "ATT": {...},  # Latest attitude packet
            "MOT": {...},  # Latest motors packet
            "STA": {...},  # Latest status packet
            # ... other packet types
        }
        await websocket.send_json(data)
        await asyncio.sleep(0.1)  # 10Hz
```

### 2. Message Format
Send `LatestTelemetryResponse` format:
```json
{
  "ATT": {
    "type": "ATT",
    "ts_us": 123456789,
    "seq": 42,
    "roll_deg": -8.98,
    "pitch_deg": 9.24,
    "yaw_deg": 0.0,
    "roll_rate_dps": -20.5,
    "pitch_rate_dps": 11.5,
    "yaw_rate_dps": 0.0
  },
  "MOT": {
    "type": "MOT",
    "ts_us": 123456789,
    "seq": 10,
    "motors": [450, 460, 440, 455],
    "motors_actual": [450, 460, 440, 455],
    "throttle": 450,
    "mixer_id": 0
  },
  "STA": {
    "type": "STA",
    "ts_us": 123456789,
    "seq": 5,
    "armed": true,
    "mode": 0,
    "ground_state": 0,
    "link_quality": 95,
    "battery_pct": 0,
    "uptime_s": 120,
    "loop_rate_hz": 200.5,
    "flags": {
      "ARM": true,
      "HRZ": true,
      "LINK": true,
      "DISARM": false,
      "CAL": true,
      "CALIB": false,
      "FAIL": false
    }
  },
  "CTL": null,
  "SENS": null,
  "SAFE": null,
  "PERF": null
}
```

### 3. History Endpoints (Optional)
For chart initialization:
```
GET /telemetry/history/ATT?max_count=100
GET /telemetry/history/MOT?max_count=200
```

## What You Should See

### Status Bar (Top)
- ARM/DISARM status (red/green)
- Flight mode badge (e.g., "STABILIZE")
- Safety flags indicators
- Link quality bar (0-100%)
- Battery percentage
- Uptime counter

### Left Column
- **Artificial Horizon**: Bank/pitch visualization
- **Heading Indicator**: Compass with rotating ring
- **Rate Indicators**: Roll/pitch/yaw rates

### Middle Column
- **FLIGHT Tab**: Roll/pitch/yaw angles chart
- **MOTORS Tab**: Motor commands over time
- **PID Tab**: Setpoint vs actual tracking
- **DIAGNOSTICS Tab**: System metrics

### Right Column
- **Motor Status**: 4 vertical bars showing motor output
- **Base Throttle**: Current throttle setting
- **Mixer**: Active mixer configuration

### Bottom Panel
- **Alerts**: Critical warnings and info messages
- **Acknowledgment**: Click to dismiss alerts

## Next Steps

### Customize the Display
- Adjust chart time ranges (10s/30s/60s)
- Toggle grid display on charts
- Switch between tabs

### Monitor Performance
- Check connection latency ("ms ago" indicator)
- Watch packet sequence numbers
- Monitor alert panel for issues

### Integration Testing
1. Arm the drone (if safe)
2. Verify status changes in dashboard
3. Move drone and watch attitude update
4. Check motor bars respond to throttle
5. Generate alerts by triggering safety flags

## Common Issues

### Data Appears Frozen
- Check connection status (top-left)
- Look at "ms ago" counter
- Click RECONNECT if disconnected

### Charts Show Gaps
- History endpoints may not be working
- Check browser console for fetch errors
- Try refreshing the page

### Wrong Flight Mode Displayed
- Check mode mapping (0=STABILIZE, 1=ACRO, etc.)
- Verify mode value in API response

### Motor Bars Not Moving
- Ensure armed status is true
- Check MOT packet has valid data
- Verify motors array [0-1000] range

## Advanced Configuration

### Change Update Rate
Modify dashboard behavior in `/hooks/useTelemetryData.ts`:
```typescript
// Simulated mode interval (default: 100ms = 10Hz)
const interval = setInterval(() => { ... }, 100);
```

### Adjust History Buffer Sizes
```typescript
// In useTelemetryData hook
.slice(-100)  // Attitude: last 100 points
.slice(-200)  // Motors: last 200 points
.slice(-100)  // PID: last 100 points
```

### Add Custom Alerts
```typescript
// In handleTelemetryMessage
if (battery < 20) {
  newAlerts.push({
    id: `alert-${alertIdCounter++}`,
    severity: 'warning',
    timestamp: formatTime(uptime),
    message: 'Low battery warning',
    acknowledged: false,
  });
}
```

## Support

For more information:
- See `API_INTEGRATION.md` for detailed API documentation
- See `WEBSOCKET_IMPLEMENTATION.md` for technical details
- Check browser console for debug information
- Review OpenAPI schema for packet formats

## Tips

✅ **Do:**
- Start with simulated mode to verify dashboard works
- Check browser console for errors
- Use DevTools Network tab to debug WebSocket
- Test API endpoints with curl first

❌ **Don't:**
- Don't use untrusted API servers (no auth implemented)
- Don't expect sub-millisecond latency
- Don't send data faster than 100Hz (overkill)
- Don't forget CORS configuration

## Quick Command Reference

```bash
# Check API health
curl http://localhost:8000/health

# Test WebSocket (with websocat)
websocat ws://localhost:8000/ws/telemetry

# Test history endpoint
curl http://localhost:8000/telemetry/history/ATT?max_count=10

# Check available ports
curl http://localhost:8000/ports

# Get statistics
curl http://localhost:8000/stats
```

---

**Ready to fly!** 🚁 If you see green "CONNECTED" status, your dashboard is live!
