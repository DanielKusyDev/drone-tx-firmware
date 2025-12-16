import { memo } from 'react';

interface MotorStatusProps {
  motors: Array<{
    id: number;
    commanded: number;
    actual: number;
  }>;
  baseThrottle: number;
  mixerId: string;
}

export function MotorStatus({ motors, baseThrottle, mixerId }: MotorStatusProps) {
  const maxValue = 65535;

  return (
    <div className="h-full flex flex-col">
      <div className="text-center mb-4">
        <div className="text-xs text-gray-400 mb-1">MOTOR STATUS</div>
        <div className="text-sm font-mono text-[#00aaff]">Mixer: {mixerId}</div>
      </div>

      {/* Drone Diagram with Integrated Motor Bars */}
      <div className="flex-1 flex items-center justify-center">
        <svg viewBox="0 0 400 400" className="w-full h-full max-h-[500px]">
          {/* Center body */}
          <circle cx="200" cy="200" r="40" fill="#2a2a2a" stroke="#444" strokeWidth="3"/>
          
          {/* Arms */}
          <line x1="200" y1="200" x2="300" y2="100" stroke="#444" strokeWidth="4"/>
          <line x1="200" y1="200" x2="300" y2="300" stroke="#444" strokeWidth="4"/>
          <line x1="200" y1="200" x2="100" y2="300" stroke="#444" strokeWidth="4"/>
          <line x1="200" y1="200" x2="100" y2="100" stroke="#444" strokeWidth="4"/>
          
          {/* Front indicator */}
          <path d="M 200 30 L 215 50 L 185 50 Z" fill="#00aaff"/>
          <text x="200" y="25" textAnchor="middle" fill="#00aaff" fontSize="14" fontWeight="bold">FWD</text>

          {/* Motor 1 - Front Right */}
          <g>
            {/* Motor circle */}
            <circle cx="300" cy="100" r="20" fill="#2a2a2a" stroke="#ff3344" strokeWidth="2"/>
            <text x="300" y="106" textAnchor="middle" fill="#ff3344" fontSize="14" fontWeight="bold">M1</text>
            
            {/* Vertical bar background */}
            <rect x="335" y="40" width="30" height="120" fill="#1a1a1a" stroke="#333" strokeWidth="1" rx="4"/>
            
            {/* Grid lines */}
            <line x1="335" y1="70" x2="365" y2="70" stroke="#333" strokeWidth="1"/>
            <line x1="335" y1="100" x2="365" y2="100" stroke="#333" strokeWidth="1"/>
            <line x1="335" y1="130" x2="365" y2="130" stroke="#333" strokeWidth="1"/>
            
            {/* Actual value (background) */}
            <rect 
              x="335" 
              y={160 - (motors[0].actual / maxValue) * 120}
              width="30" 
              height={(motors[0].actual / maxValue) * 120}
              fill="#ff3344" 
              opacity="0.3"
              rx="4"
            />
            
            {/* Commanded value (foreground) */}
            <rect 
              x="335" 
              y={160 - (motors[0].commanded / maxValue) * 120}
              width="30" 
              height={(motors[0].commanded / maxValue) * 120}
              fill="#ff3344" 
              opacity="0.9"
              rx="4"
            />
            
            {/* Value text */}
            <text x="350" y="30" textAnchor="middle" fill="#ff3344" fontSize="11" fontWeight="bold">
              {motors[0].commanded}
            </text>
          </g>

          {/* Motor 2 - Rear Right */}
          <g>
            {/* Motor circle */}
            <circle cx="300" cy="300" r="20" fill="#2a2a2a" stroke="#00aaff" strokeWidth="2"/>
            <text x="300" y="306" textAnchor="middle" fill="#00aaff" fontSize="14" fontWeight="bold">M2</text>
            
            {/* Vertical bar background */}
            <rect x="335" y="240" width="30" height="120" fill="#1a1a1a" stroke="#333" strokeWidth="1" rx="4"/>
            
            {/* Grid lines */}
            <line x1="335" y1="270" x2="365" y2="270" stroke="#333" strokeWidth="1"/>
            <line x1="335" y1="300" x2="365" y2="300" stroke="#333" strokeWidth="1"/>
            <line x1="335" y1="330" x2="365" y2="330" stroke="#333" strokeWidth="1"/>
            
            {/* Actual value (background) */}
            <rect 
              x="335" 
              y={360 - (motors[1].actual / maxValue) * 120}
              width="30" 
              height={(motors[1].actual / maxValue) * 120}
              fill="#00aaff" 
              opacity="0.3"
              rx="4"
            />
            
            {/* Commanded value (foreground) */}
            <rect 
              x="335" 
              y={360 - (motors[1].commanded / maxValue) * 120}
              width="30" 
              height={(motors[1].commanded / maxValue) * 120}
              fill="#00aaff" 
              opacity="0.9"
              rx="4"
            />
            
            {/* Value text */}
            <text x="350" y="375" textAnchor="middle" fill="#00aaff" fontSize="11" fontWeight="bold">
              {motors[1].commanded}
            </text>
          </g>

          {/* Motor 3 - Rear Left */}
          <g>
            {/* Motor circle */}
            <circle cx="100" cy="300" r="20" fill="#2a2a2a" stroke="#00ff88" strokeWidth="2"/>
            <text x="100" y="306" textAnchor="middle" fill="#00ff88" fontSize="14" fontWeight="bold">M3</text>
            
            {/* Vertical bar background */}
            <rect x="35" y="240" width="30" height="120" fill="#1a1a1a" stroke="#333" strokeWidth="1" rx="4"/>
            
            {/* Grid lines */}
            <line x1="35" y1="270" x2="65" y2="270" stroke="#333" strokeWidth="1"/>
            <line x1="35" y1="300" x2="65" y2="300" stroke="#333" strokeWidth="1"/>
            <line x1="35" y1="330" x2="65" y2="330" stroke="#333" strokeWidth="1"/>
            
            {/* Actual value (background) */}
            <rect 
              x="35" 
              y={360 - (motors[2].actual / maxValue) * 120}
              width="30" 
              height={(motors[2].actual / maxValue) * 120}
              fill="#00ff88" 
              opacity="0.3"
              rx="4"
            />
            
            {/* Commanded value (foreground) */}
            <rect 
              x="35" 
              y={360 - (motors[2].commanded / maxValue) * 120}
              width="30" 
              height={(motors[2].commanded / maxValue) * 120}
              fill="#00ff88" 
              opacity="0.9"
              rx="4"
            />
            
            {/* Value text */}
            <text x="50" y="375" textAnchor="middle" fill="#00ff88" fontSize="11" fontWeight="bold">
              {motors[2].commanded}
            </text>
          </g>

          {/* Motor 4 - Front Left */}
          <g>
            {/* Motor circle */}
            <circle cx="100" cy="100" r="20" fill="#2a2a2a" stroke="#ffaa00" strokeWidth="2"/>
            <text x="100" y="106" textAnchor="middle" fill="#ffaa00" fontSize="14" fontWeight="bold">M4</text>
            
            {/* Vertical bar background */}
            <rect x="35" y="40" width="30" height="120" fill="#1a1a1a" stroke="#333" strokeWidth="1" rx="4"/>
            
            {/* Grid lines */}
            <line x1="35" y1="70" x2="65" y2="70" stroke="#333" strokeWidth="1"/>
            <line x1="35" y1="100" x2="65" y2="100" stroke="#333" strokeWidth="1"/>
            <line x1="35" y1="130" x2="65" y2="130" stroke="#333" strokeWidth="1"/>
            
            {/* Actual value (background) */}
            <rect 
              x="35" 
              y={160 - (motors[3].actual / maxValue) * 120}
              width="30" 
              height={(motors[3].actual / maxValue) * 120}
              fill="#ffaa00" 
              opacity="0.3"
              rx="4"
            />
            
            {/* Commanded value (foreground) */}
            <rect 
              x="35" 
              y={160 - (motors[3].commanded / maxValue) * 120}
              width="30" 
              height={(motors[3].commanded / maxValue) * 120}
              fill="#ffaa00" 
              opacity="0.9"
              rx="4"
            />
            
            {/* Value text */}
            <text x="50" y="30" textAnchor="middle" fill="#ffaa00" fontSize="11" fontWeight="bold">
              {motors[3].commanded}
            </text>
          </g>

          {/* Position labels */}
          <text x="335" y="105" textAnchor="start" fill="#666" fontSize="9">FR</text>
          <text x="335" y="305" textAnchor="start" fill="#666" fontSize="9">RR</text>
          <text x="35" y="305" textAnchor="end" fill="#666" fontSize="9">RL</text>
          <text x="35" y="105" textAnchor="end" fill="#666" fontSize="9">FL</text>
        </svg>
      </div>

      {/* Base Throttle */}
      <div className="mt-4 pt-4 border-t border-[#333]">
        <div className="text-xs text-gray-400 text-center mb-2">BASE THROTTLE</div>
        <div className="flex items-center gap-3">
          <div className="flex-1 h-8 bg-[#1a1a1a] rounded-lg overflow-hidden relative">
            <div 
              className="h-full bg-gradient-to-r from-[#00aaff] to-[#00ff88] transition-all duration-100"
              style={{ width: `${baseThrottle}%` }}
            />
            {/* Grid lines */}
            {[0, 25, 50, 75, 100].map(percent => (
              <div 
                key={percent}
                className="absolute top-0 h-full border-l border-[#333]"
                style={{ left: `${percent}%` }}
              />
            ))}
          </div>
          <div className="font-mono text-sm min-w-[4ch]">
            {Math.round(baseThrottle)}%
          </div>
        </div>
      </div>
    </div>
  );
}

export default memo(MotorStatus);