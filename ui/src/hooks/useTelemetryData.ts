import { useState, useEffect } from 'react';
import { droneApi } from '../services/droneApi';

export interface TelemetryData {
  armed: boolean;
  flightMode: string;
  safetyFlags: {
    horizonOK: boolean;        // HRZ - Horizon check passed
    forceDisarm: boolean;       // DISARM - Force disarm active
    calibrating: boolean;       // CALIB - Currently calibrating
    lowBattery: boolean;        // LOBAT - Low battery detected
    sensorFailure: boolean;     // SENS - Sensor failure (NaN/Inf/extreme values)
    failsafeActive: boolean;    // FS - Failsafe active (RC loss or emergency)
    angleLimitExceeded: boolean; // ANG - Angle limit exceeded (>22°)
  };
  battery: number;
  uptime: number;
  linkQuality: number;
  attitude: {
    roll: number;
    pitch: number;
    yaw: number;
  };
  rates: {
    roll: number;
    pitch: number;
    yaw: number;
  };
  motors: Array<{
    id: number;
    commanded: number;
    actual: number;
  }>;
  baseThrottle: number;
  mixerId: string;
  history: {
    attitude: Array<{ time: number; roll: number; pitch: number; yaw: number }>;
    motors: Array<{ time: number; m1: number; m2: number; m3: number; m4: number }>;
    pid: Array<{ time: number; setpoint: number; actual: number; error: number }>;
  };
  alerts: Array<{
    id: string;
    severity: 'critical' | 'warning' | 'info';
    timestamp: string;
    message: string;
    acknowledged: boolean;
  }>;
  connected: boolean;
  lastUpdate: number | null;
}

const FLIGHT_MODES: { [key: number]: string } = {
  0: 'STABILIZE',
  1: 'ACRO',
  2: 'ALT_HOLD',
  3: 'AUTO',
  4: 'GUIDED',
  5: 'LOITER',
  6: 'RTL',
  7: 'LAND',
};

const MIXER_NAMES: { [key: number]: string } = {
  0: 'QUAD_X',
  1: 'QUAD_PLUS',
  2: 'HEX_X',
  3: 'HEX_PLUS',
};

export function useTelemetryData() {
  const [data, setData] = useState<TelemetryData>({
    armed: false,
    flightMode: 'STABILIZE',
    safetyFlags: {
      horizonOK: true,
      forceDisarm: false,
      calibrating: false,
      lowBattery: false,
      sensorFailure: false,
      failsafeActive: false,
      angleLimitExceeded: false,
    },
    battery: 0,
    uptime: 0,
    linkQuality: 0,
    attitude: {
      roll: 0,
      pitch: 0,
      yaw: 0,
    },
    rates: {
      roll: 0,
      pitch: 0,
      yaw: 0,
    },
    motors: [
      { id: 1, commanded: 0, actual: 0 },
      { id: 2, commanded: 0, actual: 0 },
      { id: 3, commanded: 0, actual: 0 },
      { id: 4, commanded: 0, actual: 0 },
    ],
    baseThrottle: 0,
    mixerId: 'QUAD_X',
    history: {
      attitude: [],
      motors: [],
      pid: [],
    },
    alerts: [],
    connected: false, // Start disconnected - will connect via WebSocket or simulation
    lastUpdate: Date.now() / 1000,
  });

  const [apiBaseUrl, setApiBaseUrl] = useState('http://localhost:8000');
  const [useSimulatedData, setUseSimulatedData] = useState(false); // Default to Real API mode

  // Update API base URL
  useEffect(() => {
    droneApi.setBaseUrl(apiBaseUrl);
  }, [apiBaseUrl]);

  // Fetch real telemetry data via WebSocket
  useEffect(() => {
    if (useSimulatedData) {
      return; // Skip if using simulated data
    }

    let isMounted = true;
    let alertIdCounter = 0;
    let historyFetched = false;

    // Fetch historical data on initial load
    const fetchHistory = async () => {
      try {
        const [attHistory, motHistory] = await Promise.all([
          droneApi.getPacketHistory('ATT', 100),
          droneApi.getPacketHistory('MOT', 200),
        ]);

        if (!isMounted) return;

        const now = Date.now() / 1000;

        // Process attitude history
        const attitudeHistory = attHistory.packets.map((pkt: any) => ({
          time: now - (attHistory.packets.length - attHistory.packets.indexOf(pkt)) * 0.05,
          roll: pkt.roll_deg,
          pitch: pkt.pitch_deg,
          yaw: pkt.yaw_deg,
        }));

        // Process motor history
        const motorHistory = motHistory.packets.map((pkt: any) => ({
          time: now - (motHistory.packets.length - motHistory.packets.indexOf(pkt)) * 0.2,
          m1: pkt.motors[0] || 0,
          m2: pkt.motors[1] || 0,
          m3: pkt.motors[2] || 0,
          m4: pkt.motors[3] || 0,
        }));

        setData(prev => ({
          ...prev,
          history: {
            ...prev.history,
            attitude: attitudeHistory,
            motors: motorHistory,
          },
        }));

        historyFetched = true;
      } catch (error) {
        console.error('Failed to fetch history:', error);
      }
    };

    // Fetch history on mount
    fetchHistory();

    // Connect to WebSocket for real-time updates
    const handleTelemetryMessage = (latest: any) => {
      if (!isMounted) return;

      const now = Date.now() / 1000;

      // Use functional state update to avoid stale closures
      setData(prev => {
        // Process attitude data
        const attitude = latest.ATT ? {
          roll: latest.ATT.roll_deg,
          pitch: latest.ATT.pitch_deg,
          yaw: latest.ATT.yaw_deg,
        } : prev.attitude;

        const rates = latest.ATT ? {
          roll: latest.ATT.roll_rate_dps,
          pitch: latest.ATT.pitch_rate_dps,
          yaw: latest.ATT.yaw_rate_dps,
        } : prev.rates;

        // Process motor data
        const motors = latest.MOT ? [
          { 
            id: 1, 
            commanded: latest.MOT.motors[0] || 0, 
            actual: latest.MOT.motors_actual[0] || 0 
          },
          { 
            id: 2, 
            commanded: latest.MOT.motors[1] || 0, 
            actual: latest.MOT.motors_actual[1] || 0 
          },
          { 
            id: 3, 
            commanded: latest.MOT.motors[2] || 0, 
            actual: latest.MOT.motors_actual[2] || 0 
          },
          { 
            id: 4, 
            commanded: latest.MOT.motors[3] || 0, 
            actual: latest.MOT.motors_actual[3] || 0 
          },
        ] : prev.motors;

        const baseThrottle = latest.MOT ? ((latest.MOT.throttle / 65535) * 100) : prev.baseThrottle;
        const mixerId = latest.MOT ? (MIXER_NAMES[latest.MOT.mixer_id] || 'UNKNOWN') : prev.mixerId;

        // Process status data
        const armed = latest.STA ? latest.STA.armed : prev.armed;
        const flightMode = latest.STA ? (FLIGHT_MODES[latest.STA.mode] || 'UNKNOWN') : prev.flightMode;
        const linkQuality = latest.STA ? latest.STA.link_quality : prev.linkQuality;
        const uptime = latest.STA ? latest.STA.uptime_s : prev.uptime;
        const battery = latest.STA ? latest.STA.battery_pct : prev.battery;

        const safetyFlags = latest.STA?.flags ? {
          horizonOK: latest.STA.flags.HRZ,
          forceDisarm: latest.STA.flags.DISARM,
          calibrating: latest.STA.flags.CALIB,
          lowBattery: latest.STA.flags.LOBAT,
          sensorFailure: latest.STA.flags.SENS,
          failsafeActive: latest.STA.flags.FS,
          angleLimitExceeded: latest.STA.flags.ANG,
        } : prev.safetyFlags;

        // Update history with new data points
        const newAttitudeHistory = latest.ATT ? [
          ...prev.history.attitude,
          { 
            time: now, 
            roll: latest.ATT.roll_deg, 
            pitch: latest.ATT.pitch_deg, 
            yaw: latest.ATT.yaw_deg 
          }
        ].slice(-100) : prev.history.attitude;

        const newMotorHistory = latest.MOT ? [
          ...prev.history.motors,
          { 
            time: now, 
            m1: latest.MOT.motors[0] || 0, 
            m2: latest.MOT.motors[1] || 0, 
            m3: latest.MOT.motors[2] || 0, 
            m4: latest.MOT.motors[3] || 0 
          }
        ].slice(-200) : prev.history.motors;

        const newPidHistory = (latest.CTL && latest.ATT) ? [
          ...prev.history.pid,
          { 
            time: now, 
            setpoint: latest.CTL.set_roll_deg, 
            actual: latest.ATT.roll_deg,
            error: latest.CTL.set_roll_deg - latest.ATT.roll_deg
          }
        ].slice(-100) : prev.history.pid;

        // Generate alerts based on telemetry data
        const newAlerts = [...prev.alerts];

        if (latest.STA?.flags.DISARM && !prev.safetyFlags.forceDisarm) {
          newAlerts.push({
            id: `alert-${alertIdCounter++}`,
            severity: 'critical',
            timestamp: formatTime(uptime),
            message: 'Force disarm activated!',
            acknowledged: false,
          });
        }

        if (latest.STA?.flags.LOBAT && !prev.safetyFlags.lowBattery) {
          newAlerts.push({
            id: `alert-${alertIdCounter++}`,
            severity: 'warning',
            timestamp: formatTime(uptime),
            message: 'Low battery detected',
            acknowledged: false,
          });
        }

        if (latest.STA?.flags.SENS && !prev.safetyFlags.sensorFailure) {
          newAlerts.push({
            id: `alert-${alertIdCounter++}`,
            severity: 'critical',
            timestamp: formatTime(uptime),
            message: 'Sensor failure detected',
            acknowledged: false,
          });
        }

        if (latest.STA?.flags.FS && !prev.safetyFlags.failsafeActive) {
          newAlerts.push({
            id: `alert-${alertIdCounter++}`,
            severity: 'critical',
            timestamp: formatTime(uptime),
            message: 'Failsafe activated',
            acknowledged: false,
          });
        }

        if (latest.STA?.flags.ANG && !prev.safetyFlags.angleLimitExceeded) {
          newAlerts.push({
            id: `alert-${alertIdCounter++}`,
            severity: 'warning',
            timestamp: formatTime(uptime),
            message: 'Angle limit exceeded',
            acknowledged: false,
          });
        }

        if (linkQuality < 50 && prev.linkQuality >= 50) {
          newAlerts.push({
            id: `alert-${alertIdCounter++}`,
            severity: 'warning',
            timestamp: formatTime(uptime),
            message: 'Link quality degraded',
            acknowledged: false,
          });
        }

        return {
          armed,
          flightMode,
          safetyFlags,
          battery,
          uptime,
          linkQuality,
          attitude,
          rates,
          motors,
          baseThrottle,
          mixerId,
          history: {
            attitude: newAttitudeHistory,
            motors: newMotorHistory,
            pid: newPidHistory,
          },
          alerts: newAlerts.slice(-20),
          connected: true,
          lastUpdate: now,
        };
      });
    };

    const handleConnectionStatus = (connected: boolean) => {
      if (!isMounted) return;
      setData(prev => ({
        ...prev,
        connected,
      }));
    };

    // Connect to WebSocket
    const cleanup = droneApi.connectWebSocket(handleTelemetryMessage, handleConnectionStatus);

    return () => {
      isMounted = false;
      cleanup();
    };
  }, [useSimulatedData, apiBaseUrl]);

  // Simulated data mode (fallback)
  useEffect(() => {
    if (!useSimulatedData) {
      return;
    }

    const interval = setInterval(() => {
      setData(prev => {
        const newUptime = prev.uptime + 0.1;
        const time = newUptime;

        // Simulate flight dynamics
        const rollNoise = (Math.sin(time * 0.5) * 15) + (Math.random() - 0.5) * 5;
        const pitchNoise = (Math.cos(time * 0.3) * 10) + (Math.random() - 0.5) * 3;
        const yawNoise = ((time * 10) % 360) + (Math.random() - 0.5) * 2;

        const rollRate = Math.sin(time * 0.5) * 50 + (Math.random() - 0.5) * 20;
        const pitchRate = Math.cos(time * 0.3) * 30 + (Math.random() - 0.5) * 15;
        const yawRate = Math.sin(time * 0.2) * 40 + (Math.random() - 0.5) * 10;

        const baseThrottle = prev.armed ? 40 + Math.sin(time * 0.4) * 20 : 0;
        const motorVariation = prev.armed ? 100 : 0;

        const m1 = Math.max(0, Math.min(1000, baseThrottle * 10 + motorVariation + Math.random() * 50));
        const m2 = Math.max(0, Math.min(1000, baseThrottle * 10 + motorVariation + Math.random() * 50));
        const m3 = Math.max(0, Math.min(1000, baseThrottle * 10 + motorVariation + Math.random() * 50));
        const m4 = Math.max(0, Math.min(1000, baseThrottle * 10 + motorVariation + Math.random() * 50));

        const newAttitudeHistory = [
          ...prev.history.attitude,
          { time, roll: rollNoise, pitch: pitchNoise, yaw: yawNoise % 360 }
        ].slice(-100);

        const newMotorHistory = [
          ...prev.history.motors,
          { time, m1, m2, m3, m4 }
        ].slice(-200);

        const newPidHistory = [
          ...prev.history.pid,
          { 
            time, 
            setpoint: Math.sin(time * 0.3) * 20, 
            actual: rollNoise,
            error: Math.sin(time * 0.3) * 20 - rollNoise
          }
        ].slice(-100);

        const linkQuality = Math.max(50, Math.min(100, 95 + (Math.random() - 0.5) * 20));

        return {
          ...prev,
          uptime: newUptime,
          linkQuality,
          attitude: {
            roll: rollNoise,
            pitch: pitchNoise,
            yaw: yawNoise % 360,
          },
          rates: {
            roll: rollRate,
            pitch: pitchRate,
            yaw: yawRate,
          },
          motors: [
            { id: 1, commanded: Math.round(m1), actual: Math.round(m1 + (Math.random() - 0.5) * 20) },
            { id: 2, commanded: Math.round(m2), actual: Math.round(m2 + (Math.random() - 0.5) * 20) },
            { id: 3, commanded: Math.round(m3), actual: Math.round(m3 + (Math.random() - 0.5) * 20) },
            { id: 4, commanded: Math.round(m4), actual: Math.round(m4 + (Math.random() - 0.5) * 20) },
          ],
          baseThrottle,
          history: {
            attitude: newAttitudeHistory,
            motors: newMotorHistory,
            pid: newPidHistory,
          },
          connected: true,
          lastUpdate: Date.now() / 1000,
        };
      });
    }, 100);

    return () => clearInterval(interval);
  }, [useSimulatedData]);

  const setArmed = (armed: boolean) => {
    setData(prev => ({ ...prev, armed }));
  };

  return { 
    telemetryData: data, 
    setArmed,
    setApiBaseUrl,
    setUseSimulatedData,
    apiBaseUrl,
    useSimulatedData,
  };
}

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}