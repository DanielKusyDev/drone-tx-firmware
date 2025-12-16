import { memo } from 'react';
import { Shield, Battery, Clock, Signal } from 'lucide-react';
import { TelemetryData } from '../hooks/useTelemetryData';
import { SafetyFlags } from './SafetyFlags';

interface StatusBarProps {
  data: TelemetryData;
  onArmToggle: () => void;
}

export function StatusBar({ data, onArmToggle }: StatusBarProps) {
  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const getLinkQualityColor = (quality: number) => {
    if (quality > 80) return '#00ff88';
    if (quality > 50) return '#ffaa00';
    return '#ff3344';
  };

  return (
    <div className="h-[60px] bg-[#242424] border-b border-[#333] flex items-center px-6 gap-8">
      {/* Left - ARM Status */}
      <div className="flex items-center gap-3">
        <Shield className={data.armed ? 'text-[#ff3344]' : 'text-gray-500'} size={28} />
        <button
          onClick={onArmToggle}
          className={`px-6 py-2 rounded-md font-mono transition-all ${
            data.armed 
              ? 'bg-[#ff3344] text-white animate-pulse hover:bg-[#ff4455]' 
              : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
          }`}
        >
          {data.armed ? 'ARMED' : 'DISARMED'}
        </button>
      </div>

      {/* Center - Flight Mode and Safety Flags */}
      <div className="flex-1 flex items-center justify-center gap-6">
        <div className="bg-[#00aaff] text-white px-4 py-2 rounded-md font-mono">
          {data.flightMode}
        </div>
        <SafetyFlags flags={data.safetyFlags} />
      </div>

      {/* Right - Battery, Uptime, Link Quality */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <Battery className="text-[#00ff88]" size={20} />
          <span className="font-mono">{data.battery.toFixed(1)}%</span>
        </div>

        <div className="flex items-center gap-2">
          <Clock className="text-[#00aaff]" size={20} />
          <span className="font-mono">{formatUptime(data.uptime)}</span>
        </div>

        <div className="flex items-center gap-2">
          <Signal className="text-[#00ff88]" size={20} />
          <div className="flex flex-col gap-1">
            <span className="font-mono text-sm">{Math.round(data.linkQuality)}%</span>
            <div className="w-24 h-2 bg-[#333] rounded-full overflow-hidden">
              <div 
                className="h-full transition-all duration-300"
                style={{ 
                  width: `${data.linkQuality}%`,
                  backgroundColor: getLinkQualityColor(data.linkQuality)
                }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default memo(StatusBar);