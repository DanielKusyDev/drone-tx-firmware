# Performance Diagnostics Guide

## 🔍 Problem: Slowness When Throttle is High

When the drone throttle increases, the dashboard may feel sluggish or laggy. This guide helps identify whether the issue is **UI rendering** or **API delays**.

---

## 🛠️ Diagnostic Tools Added

### 1. Performance Monitor (Bottom-Left Corner)

A real-time performance monitor now appears in the bottom-left corner showing:

- **FPS** (Frames Per Second): Target is 60 FPS
  - 🟢 Green (55-60): Good performance
  - 🟧 Orange (30-54): Fair performance  
  - 🔴 Red (<30): Poor performance

- **Render Time**: Time to render each frame
  - Target: <16ms for 60 FPS
  - 🟢 Green (<16ms): Good
  - 🟧 Orange (>16ms): Slow renders

- **Updates/sec**: State updates per second
  - Expected: 10-30 updates/sec depending on packet rates
  - 🟧 Orange (>30): High update rate - potential performance issue

- **Memory**: JavaScript heap usage (if available)
  - Monitor for memory leaks over time

### 2. API Timing Diagnostics (Console)

The WebSocket client now logs average packet timing every 100 packets:

```
Average packet timing: 45.2ms
```

This tells you the time between packets arriving from the API.

---

## 📊 How to Diagnose

### Step 1: Open the Performance Monitor

1. Look in the **bottom-left corner** of the screen
2. Click the Activity icon to expand the monitor
3. Let it run for 10-20 seconds to collect data

### Step 2: Test Different Throttle Levels

**Low Throttle (Armed, ~20% throttle):**
- Record: FPS, Render Time, Updates/sec

**Medium Throttle (~50% throttle):**
- Record: FPS, Render Time, Updates/sec

**High Throttle (~80% throttle):**
- Record: FPS, Render Time, Updates/sec
- This is where you're experiencing slowness

### Step 3: Check Browser Console

Open DevTools (F12) → Console tab

Look for:
```
Average packet timing: XX.Xms
```

Expected values:
- **ATT packets**: ~50ms (20 Hz)
- **MOT packets**: ~200ms (5 Hz)
- **Combined**: ~40-50ms average

### Step 4: Identify the Bottleneck

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| FPS drops, but packet timing normal | **UI Rendering** | Optimize React components (see below) |
| Packet timing increases with throttle | **API Delays** | Check backend performance |
| Updates/sec > 30 | **Too many state updates** | Throttle/debounce updates |
| Render time > 16ms | **Slow component rendering** | Profile components |
| Memory increases over time | **Memory leak** | Check for unbounded arrays |

---

## 🔧 Performance Issues & Solutions

### Issue 1: UI Rendering Bottleneck

**Symptoms:**
- FPS drops to 30-40
- Render time > 16ms
- Updates/sec is high (>30)

**Root Cause:**
Every WebSocket packet triggers a full React re-render of the entire component tree.

**Solution:** Add React.memo to components

```typescript
// Example: Memoize ArtificialHorizon
import { memo } from 'react';

export const ArtificialHorizon = memo(function ArtificialHorizon({ roll, pitch }) {
  // Component code...
}, (prevProps, nextProps) => {
  // Only re-render if roll or pitch changed significantly
  return Math.abs(prevProps.roll - nextProps.roll) < 0.1 &&
         Math.abs(prevProps.pitch - nextProps.pitch) < 0.1;
});
```

### Issue 2: Too Many State Updates

**Symptoms:**
- Updates/sec > 30
- All components re-render frequently

**Root Cause:**
WebSocket sends individual packets at combined rate of 20-30 Hz, each triggering a state update.

**Solution:** Throttle state updates

```typescript
// In useTelemetryData.ts
import { useRef } from 'react';

const lastUpdateRef = useRef(0);
const THROTTLE_MS = 50; // Max 20 updates/sec

const handleTelemetryMessage = (latest: any) => {
  const now = Date.now();
  if (now - lastUpdateRef.current < THROTTLE_MS) {
    return; // Skip this update
  }
  lastUpdateRef.current = now;
  
  // Existing state update logic...
};
```

### Issue 3: API Latency

**Symptoms:**
- Packet timing increases from ~50ms to >200ms when throttle is high
- FPS stays good but data feels delayed

**Root Cause:**
Backend is struggling to keep up with packet processing.

**Solution:** Backend optimization
- Check serial port buffer size
- Reduce packet processing overhead
- Use async/await properly in Python
- Profile backend with `cProfile`

### Issue 4: Chart Re-rendering

**Symptoms:**
- Render time spikes when charts are visible
- Performance is fine on instrument-only view

**Root Cause:**
Recharts re-renders on every data point change, which is expensive.

**Solution:** Reduce chart update rate

```typescript
// Only update charts every 200ms instead of every packet
const [chartData, setChartData] = useState(history);
const lastChartUpdateRef = useRef(0);

useEffect(() => {
  const now = Date.now();
  if (now - lastChartUpdateRef.current > 200) {
    setChartData(history);
    lastChartUpdateRef.current = now;
  }
}, [history]);
```

### Issue 5: History Array Growth

**Symptoms:**
- Memory increases over time
- Performance degrades after 5-10 minutes

**Root Cause:**
History arrays grow unbounded or slice operations are expensive.

**Current Implementation:**
```typescript
.slice(-100)  // Attitude history
.slice(-200)  // Motor history
```

This creates new arrays every update. Consider using circular buffers for better performance.

---

## 🎯 Quick Fixes to Try

### 1. Reduce Update Rate (Quick Win)

In `useTelemetryData.ts`, add throttling:

```typescript
const updateThrottleMs = 50; // 20 FPS max
let lastUpdate = 0;

const handleTelemetryMessage = (latest: any) => {
  const now = Date.now();
  if (now - lastUpdate < updateThrottleMs) return;
  lastUpdate = now;
  
  // ... existing code
};
```

### 2. Memoize Expensive Components

Priority order:
1. `<TelemetryCharts>` - Most expensive (Recharts)
2. `<ArtificialHorizon>` - Updates at 20Hz
3. `<MotorStatus>` - Updates at 5Hz
4. `<StatusBar>` - Updates at 2.5Hz

### 3. Split State by Update Frequency

Create separate state hooks for different update rates:

```typescript
const [attitudeData, setAttitudeData] = useState(...); // 20Hz
const [motorData, setMotorData] = useState(...); // 5Hz
const [statusData, setStatusData] = useState(...); // 2.5Hz
```

This prevents high-frequency updates (attitude) from triggering re-renders of low-frequency components (status).

---

## 📈 Expected Performance After Optimization

| Metric | Before | Target After |
|--------|--------|--------------|
| FPS | 30-40 | 55-60 |
| Render Time | 20-30ms | <16ms |
| Updates/sec | 30-40 | <20 |
| Packet Timing | Same | Same |
| Memory Growth | Unbounded | Stable |

---

## 🧪 Testing Steps

1. **Baseline Test** (Current Performance)
   - ARM drone
   - Set throttle to 80%
   - Record metrics for 60 seconds
   - Note FPS, render time, updates/sec

2. **Apply Quick Fix #1** (Throttle updates)
   - Implement 50ms throttle
   - Retest with same conditions
   - Compare metrics

3. **Apply Quick Fix #2** (Memoize charts)
   - Add React.memo to TelemetryCharts
   - Retest
   - Compare metrics

4. **Full Optimization** (if needed)
   - Split state by frequency
   - Implement circular buffers
   - Add comprehensive memoization
   - Final test

---

## 📝 Diagnostic Checklist

Use this checklist to track your investigation:

- [ ] Performance Monitor installed and visible
- [ ] Baseline metrics recorded (low throttle)
- [ ] High throttle metrics recorded
- [ ] Browser console checked for packet timing
- [ ] Bottleneck identified (UI vs API)
- [ ] Quick fixes attempted
- [ ] Performance improvement verified
- [ ] Long-running test (10+ minutes) completed
- [ ] Memory leak check completed

---

## 🚨 Warning Signs

Watch for these red flags:

- **FPS < 30**: User experience severely degraded
- **Render time > 30ms**: Components are too heavy
- **Updates/sec > 40**: Update storm, need throttling
- **Packet timing > 200ms**: API struggling
- **Memory growth > 50MB/hour**: Memory leak

---

## 💡 Pro Tips

1. **Use React DevTools Profiler**: Shows which components are re-rendering
2. **Chrome Performance Tab**: See detailed frame timing
3. **Network Tab (WS filter)**: Monitor WebSocket message rate
4. **console.time/timeEnd**: Measure specific code sections

---

## 📊 Reporting Performance Issues

When reporting, include:

1. **Performance Monitor screenshot** (expanded view)
2. **Console output** (packet timing logs)
3. **Test conditions**: Armed, throttle %, duration
4. **Browser**: Chrome/Firefox/Safari + version
5. **Operating system**: Windows/Mac/Linux

---

**Next Steps:**

1. Run diagnostic tests with the new Performance Monitor
2. Check console for packet timing
3. Report findings: "FPS drops to X, render time Y ms, packet timing Z ms"
4. We'll apply targeted optimizations based on results

The Performance Monitor will tell us exactly whether the slowness is UI rendering (low FPS, high render time) or API delays (high packet timing).
