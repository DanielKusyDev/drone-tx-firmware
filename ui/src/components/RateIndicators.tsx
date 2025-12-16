import { memo } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface RateIndicatorsProps {
  rates: {
    roll: number;
    pitch: number;
    yaw: number;
  };
}

export function RateIndicators({ rates }: RateIndicatorsProps) {
  const getTrendIcon = (rate: number) => {
    if (Math.abs(rate) < 5) return Minus;
    return rate > 0 ? TrendingUp : TrendingDown;
  };

  const getTrendColor = (rate: number) => {
    if (Math.abs(rate) < 10) return '#00ff88';
    if (Math.abs(rate) < 30) return '#ffaa00';
    return '#ff3344';
  };

  const rateItems = [
    { label: 'ROLL RATE', value: rates.roll },
    { label: 'PITCH RATE', value: rates.pitch },
    { label: 'YAW RATE', value: rates.yaw },
  ];

  return (
    <div className="space-y-3">
      <div className="text-xs text-gray-400 text-center">ANGULAR RATES</div>
      {rateItems.map(({ label, value }) => {
        const TrendIcon = getTrendIcon(value);
        const color = getTrendColor(value);

        return (
          <div key={label} className="flex items-center justify-between">
            <div className="text-xs text-gray-400">{label}</div>
            <div className="flex items-center gap-2">
              <span 
                className="font-mono"
                style={{ color }}
              >
                {value.toFixed(1)}°/s
              </span>
              <TrendIcon size={16} style={{ color }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default memo(RateIndicators);