// Drone Telemetry API Service
// Based on OpenAPI schema for ESP32 drone telemetry

export interface AttitudePacket {
  type: string;
  ts_us: number;
  seq: number;
  roll_deg: number;
  pitch_deg: number;
  yaw_deg: number;
  roll_rate_dps: number;
  pitch_rate_dps: number;
  yaw_rate_dps: number;
}

export interface MotorsPacket {
  type: string;
  ts_us: number;
  seq: number;
  motors: number[];
  motors_actual: number[];
  throttle: number;
  mixer_id: number;
}

export interface SafetyFlags {
  ARM: boolean;
  HRZ: boolean;
  LINK: boolean;
  DISARM: boolean;
  CAL: boolean;
  CALIB: boolean;
  FAIL: boolean;
}

export interface StatusPacket {
  type: string;
  ts_us: number;
  seq: number;
  armed: boolean;
  mode: number;
  ground_state: number;
  link_quality: number;
  battery_pct: number;
  uptime_s: number;
  loop_rate_hz: number;
  flags: SafetyFlags;
}

export interface ControlPacket {
  type: string;
  ts_us: number;
  seq: number;
  set_roll_deg: number;
  set_pitch_deg: number;
  set_yaw_rate_dps: number;
  rate_set_roll_dps: number;
  rate_set_pitch_dps: number;
  out_roll: number;
  out_pitch: number;
  out_yaw: number;
  pid_gains_scale: number;
  throttle_gain_scale: number;
}

export interface SensorsPacket {
  type: string;
  ts_us: number;
  seq: number;
  accel_mg: number[];
  gyro_mdps: number[];
  mag_mgauss: number[];
  temperature_c: number;
}

export interface PerformancePacket {
  type: string;
  ts_us: number;
  seq: number;
  loop_time_us: number;
  imu_time_us: number;
  control_time_us: number;
  cpu_usage_pct: number;
  free_heap_kb: number;
  stack_usage_pct: number;
}

export interface SafetyPacket {
  type: string;
  ts_us: number;
  seq: number;
  ground_confidence: number;
  safety_gates: number;
  error_flags: number;
  total_flight_time_s: number;
  crash_count: number;
}

export interface LatestTelemetryResponse {
  ATT: AttitudePacket | null;
  MOT: MotorsPacket | null;
  STA: StatusPacket | null;
  CTL: ControlPacket | null;
  SENS: SensorsPacket | null;
  SAFE: any | null;
  PERF: PerformancePacket | null;
  SAFETY: SafetyPacket | null;
}

export interface HealthResponse {
  status: string;
  last_packet_age_s: number | null;
  packets_received: number;
  is_alive: boolean;
}

export interface PacketHistoryResponse {
  packet_type: string;
  count: number;
  packets: any[];
}

// Type for individual WebSocket packets
type WebSocketPacket =
  | AttitudePacket
  | MotorsPacket
  | StatusPacket
  | ControlPacket
  | SensorsPacket
  | SafetyPacket
  | PerformancePacket;

class DroneApiService {
  private baseUrl: string;
  private defaultBaseUrl = 'http://localhost:8000';
  private ws: WebSocket | null = null;
  private wsCallbacks: Set<(data: LatestTelemetryResponse) => void> = new Set();
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 2000;

  // Performance diagnostics
  private packetCount = 0;
  private lastDiagnosticTime = 0;
  private packetTimings: number[] = [];

  // Accumulator for individual packets into aggregated state
  private latestPackets: LatestTelemetryResponse = {
    ATT: null,
    MOT: null,
    STA: null,
    CTL: null,
    SENS: null,
    SAFE: null,
    PERF: null,
    SAFETY: null,
  };

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || this.defaultBaseUrl;
  }

  setBaseUrl(url: string) {
    this.baseUrl = url;
    // Reconnect if WebSocket is active
    if (this.ws) {
      this.disconnectWebSocket();
      // Don't auto-reconnect, let the hook handle it
    }
  }

  private getWebSocketUrl(): string {
    // Convert http://localhost:8000 to ws://localhost:8000
    const wsUrl = this.baseUrl.replace(/^http/, 'ws');
    return `${wsUrl}/ws/telemetry`;
  }

  connectWebSocket(onMessage: (data: LatestTelemetryResponse) => void, onStatusChange?: (connected: boolean) => void): () => void {
    // Add callback
    this.wsCallbacks.add(onMessage);

    // Create WebSocket connection if not exists
    if (!this.ws || this.ws.readyState === WebSocket.CLOSED) {
      this.createWebSocketConnection(onStatusChange);
    }

    // Return cleanup function
    return () => {
      this.wsCallbacks.delete(onMessage);
      if (this.wsCallbacks.size === 0) {
        this.disconnectWebSocket();
      }
    };
  }

  private createWebSocketConnection(onStatusChange?: (connected: boolean) => void) {
    try {
      const wsUrl = this.getWebSocketUrl();
      console.log('Connecting to WebSocket:', wsUrl);
      
      // Reset accumulated packets on new connection
      this.latestPackets = {
        ATT: null,
        MOT: null,
        STA: null,
        CTL: null,
        SENS: null,
        SAFE: null,
        PERF: null,
        SAFETY: null,
      };

      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        onStatusChange?.(true);
      };

      this.ws.onmessage = (event) => {
        try {
          const packet: WebSocketPacket = JSON.parse(event.data);
          
          // Update the accumulated state with this packet
          this.latestPackets[packet.type as keyof LatestTelemetryResponse] = packet;
          
          // Broadcast aggregated state to all callbacks
          this.wsCallbacks.forEach(callback => callback(this.latestPackets));
          
          // Performance diagnostics
          const currentTime = Date.now();
          if (this.lastDiagnosticTime === 0) {
            this.lastDiagnosticTime = currentTime;
          }
          this.packetTimings.push(currentTime - this.lastDiagnosticTime);
          this.lastDiagnosticTime = currentTime;
          this.packetCount++;
          if (this.packetCount >= 100) {
            const avgTiming = this.packetTimings.reduce((sum, time) => sum + time, 0) / this.packetTimings.length;
            console.log(`Average packet timing: ${avgTiming}ms`);
            this.packetTimings = [];
            this.packetCount = 0;
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        onStatusChange?.(false);
      };

      this.ws.onclose = () => {
        console.log('WebSocket closed');
        onStatusChange?.(false);
        this.ws = null;

        // Reset accumulated packets on disconnect
        this.latestPackets = {
          ATT: null,
          MOT: null,
          STA: null,
          CTL: null,
          SENS: null,
          SAFE: null,
          PERF: null,
          SAFETY: null,
        };

        // Attempt to reconnect if we have active callbacks
        if (this.wsCallbacks.size > 0 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          const delay = this.reconnectDelay * Math.min(this.reconnectAttempts, 5);
          console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
          
          this.reconnectTimeout = setTimeout(() => {
            this.createWebSocketConnection(onStatusChange);
          }, delay);
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      onStatusChange?.(false);
    }
  }

  disconnectWebSocket() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.reconnectAttempts = 0;
    this.wsCallbacks.clear();
  }

  isWebSocketConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  private async fetch<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`);
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    return response.json();
  }

  async getHealth(): Promise<HealthResponse> {
    return this.fetch<HealthResponse>('/health');
  }

  async getLatestTelemetry(): Promise<LatestTelemetryResponse> {
    return this.fetch<LatestTelemetryResponse>('/telemetry/latest');
  }

  async getLatestAttitude(): Promise<AttitudePacket> {
    return this.fetch<AttitudePacket>('/telemetry/attitude');
  }

  async getLatestMotors(): Promise<MotorsPacket> {
    return this.fetch<MotorsPacket>('/telemetry/motors');
  }

  async getLatestStatus(): Promise<StatusPacket> {
    return this.fetch<StatusPacket>('/telemetry/status');
  }

  async getPacketHistory(packetType: string, maxCount: number = 100): Promise<PacketHistoryResponse> {
    return this.fetch<PacketHistoryResponse>(`/telemetry/history/${packetType}?max_count=${maxCount}`);
  }

  async getStats(): Promise<any> {
    return this.fetch('/stats');
  }

  async getPorts(): Promise<any> {
    return this.fetch('/ports');
  }
}

export const droneApi = new DroneApiService();