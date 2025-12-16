# Drone Telemetry Dashboard - API Integration

This dashboard is now integrated with the ESP32 Drone Telemetry API using **WebSocket** for real-time streaming.

## Features

### Data Sources
The dashboard supports two data modes:
- **Real API**: Connects to your drone telemetry API server via WebSocket
- **Simulated**: Uses mock data for demonstration (default)

### Real-time Updates
- **WebSocket Connection** to `/ws/telemetry` endpoint
- Server pushes telemetry data as it becomes available
- No polling overhead - true real-time streaming
- Automatic reconnection with exponential backoff
- Maintains historical data for charts

### API Endpoints Used

#### `/ws/telemetry` (WebSocket)
Real-time telemetry stream
- **Protocol**: WebSocket
- **Message Format**: `LatestTelemetryResponse` JSON
- **Updates**: Server-pushed (as data arrives)
- **Purpose**: Real-time display updates

#### `/telemetry/history/{packet_type}` (HTTP)
Fetches historical packet data
- **ATT**: Attitude history (100 packets)
- **MOT**: Motor history (200 packets)
- **Purpose**: Populates charts on initial connection

#### `/health` (HTTP)
Health check endpoint
- **Purpose**: Monitor API connectivity (fallback)

## Configuration

### Setting the API URL

1. Click the **Settings** icon (⚙️) in the top-right corner
2. Select **REAL API** as the data source
3. Enter your API base URL (e.g., `http://localhost:8000`)
4. Click **APPLY**

The dashboard will automatically:
- Convert `http://` to `ws://` for WebSocket connection
- Convert `https://` to `wss://` for secure WebSocket
- Connect to `/ws/telemetry` endpoint
- Fetch historical data from HTTP endpoints

### Default Configuration
```typescript
Default API URL: http://localhost:8000
WebSocket URL: ws://localhost:8000/ws/telemetry
Default Mode: Simulated Data
```

### WebSocket Connection Management
- **Automatic Reconnection**: Retries up to 10 times with exponential backoff
- **Reconnect Delays**: 2s, 4s, 6s, 8s, 10s... (capped at 10s)
- **Connection Status**: Real-time indicator in top-left corner
- **Graceful Disconnection**: Cleans up resources when switching modes

## Data Mapping

### Attitude (ATT Packet)
```typescript
API Field           → Dashboard Display
-----------------------------------------
roll_deg            → Artificial Horizon (roll)
pitch_deg           → Artificial Horizon (pitch)
yaw_deg             → Heading Indicator
roll_rate_dps       → Rate Indicators (roll rate)
pitch_rate_dps      → Rate Indicators (pitch rate)
yaw_rate_dps        → Rate Indicators (yaw rate)
```

### Motors (MOT Packet)
```typescript
API Field           → Dashboard Display
-----------------------------------------
motors[0-3]         → Motor bars (commanded)
motors_actual[0-3]  → Motor bars (actual overlay)
throttle            → Base throttle bar
mixer_id            → Mixer display (QUAD_X, etc.)
```

### Status (STA Packet)
```typescript
API Field           → Dashboard Display
-----------------------------------------
armed               → ARM/DISARM indicator
mode                → Flight mode badge
link_quality        → Link quality bar
uptime_s            → Uptime counter
battery_pct         → Battery display
flags.HRZ           → Horizon OK flag
flags.LINK          → Link Alive flag
flags.DISARM        → Force Disarm flag
flags.CAL           → Calibration OK flag
flags.CALIB         → Calibrating flag
flags.FAIL          → Calibration Failed flag
```

### Control (CTL Packet)
```typescript
API Field           → Dashboard Display
-----------------------------------------
set_roll_deg        → PID chart (setpoint)
(combined with ATT) → PID chart (actual vs setpoint)
```

## Connection States

### Connected
- Green "CONNECTED" badge in top-left
- All displays updating in real-time
- No overlay

### Disconnected
- Red "DISCONNECTED" badge in top-left
- "NO DATA" overlay on dashboard
- Last known values displayed (frozen)

### Simulated
- Orange "SIMULATED" badge in top-left
- Mock data for demonstration
- No API calls made

## Error Handling

The dashboard gracefully handles:
- Network errors (displays disconnected state)
- Missing packets (uses last known values)
- Invalid data (falls back to defaults)
- CORS issues (configure your API server)

## CORS Configuration

Your API server must allow CORS from the dashboard origin. Example:

```python
# FastAPI example
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify your dashboard URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Testing

### With Real API
1. Start your drone telemetry API server
2. Open the dashboard
3. Click Settings
4. Select "REAL API"
5. Enter your API URL
6. Click "APPLY"
7. Check connection status in top-left

### With Simulated Data
1. Open the dashboard (already in simulated mode by default)
2. Click "ARMED" to start motor simulation
3. Observe simulated flight dynamics

## Performance Notes

- **Update Rate**: 10Hz (100ms intervals)
- **History Buffer**: 
  - Attitude: 100 packets (5 seconds at 20Hz)
  - Motors: 200 packets (40 seconds at 5Hz)
  - PID: 100 packets
- **Chart Time Ranges**: 10s / 30s / 60s
- **Memory Usage**: ~2-5MB for telemetry data

## Troubleshooting

### "NO DATA" overlay appears
1. Check that your API server is running
2. Verify the API URL is correct
3. Check browser console for errors
4. Ensure CORS is configured on API server
5. Test WebSocket endpoint: Use a WebSocket client or browser DevTools
6. Test fallback HTTP endpoint: `curl http://localhost:8000/telemetry/latest`

### WebSocket connection fails
1. **Check the WebSocket URL**: Browser console will show connection attempts
2. **Verify server supports WebSocket**: Look for upgrade headers
3. **Check for proxy/firewall issues**: Some proxies block WebSocket connections
4. **Try different protocol**: If using `https://`, ensure server supports `wss://`
5. **Check server logs**: Look for WebSocket connection errors

### WebSocket disconnects frequently
1. **Check network stability**: Unstable connections cause reconnects
2. **Review server keepalive settings**: Server may timeout idle connections
3. **Monitor reconnection attempts**: Console logs show reconnect count
4. **Check server resource limits**: Server may be dropping connections under load

### Data appears stale or frozen
1. **Check connection status**: Top-left indicator should be green
2. **Look at "ms ago" counter**: Shows time since last message
3. **Verify server is sending data**: Check server logs for WebSocket sends
4. **Check for JavaScript errors**: Browser console may show parsing errors

### Charts not showing history
1. Ensure `/telemetry/history/{packet_type}` endpoints work
2. Check that packets exist in history buffer
3. Verify packet format matches schema
4. Check browser console for fetch errors

### Performance issues
1. **Reduce chart time ranges**: Use 10s instead of 60s
2. **Monitor memory usage**: Browser DevTools → Performance
3. **Check message rate**: Server may be sending too frequently
4. **Disable grid on charts**: Reduces rendering overhead

## API Schema Reference

The dashboard expects data conforming to the OpenAPI schema:
- `AttitudePacket` (ATT)
- `MotorsPacket` (MOT)
- `StatusPacket` (STA)
- `ControlPacket` (CTL)
- `SensorsPacket` (SENS)
- `PerformancePacket` (PERF)

See the OpenAPI schema document for detailed field definitions.