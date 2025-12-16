import { memo } from 'react';

interface ArtificialHorizonProps {
  roll: number;
  pitch: number;
}

export function ArtificialHorizon({ roll, pitch }: ArtificialHorizonProps) {
  const size = 280;
  const radius = size / 2;
  const pitchScale = 3; // pixels per degree

  return (
    <div className="flex flex-col items-center gap-4">
      <div 
        className="relative rounded-full overflow-hidden border-4 border-[#333]"
        style={{ width: size, height: size }}
      >
        {/* Sky and Ground */}
        <div 
          className="absolute inset-0"
          style={{
            transform: `rotate(${roll}deg)`,
            transformOrigin: 'center center',
          }}
        >
          {/* Sky */}
          <div 
            className="absolute w-full bg-gradient-to-b from-[#0066cc] to-[#0088ff]"
            style={{
              height: '50%',
              top: 0,
              transform: `translateY(${pitch * pitchScale}px)`,
            }}
          />
          
          {/* Ground */}
          <div 
            className="absolute w-full bg-gradient-to-b from-[#4a3520] to-[#2a1a10]"
            style={{
              height: '50%',
              bottom: 0,
              transform: `translateY(${pitch * pitchScale}px)`,
            }}
          />

          {/* Horizon Line */}
          <div 
            className="absolute w-full h-[2px] bg-white left-0"
            style={{
              top: '50%',
              transform: `translateY(${pitch * pitchScale}px)`,
            }}
          />

          {/* Pitch Ladder */}
          {[-30, -20, -10, 10, 20, 30].map(pitchLine => (
            <div
              key={pitchLine}
              className="absolute left-1/2 flex items-center justify-center"
              style={{
                top: '50%',
                transform: `translate(-50%, ${(pitch - pitchLine) * pitchScale}px)`,
              }}
            >
              <div className="flex items-center gap-2">
                <div className={`h-[1px] ${pitchLine > 0 ? 'w-8' : 'w-12'} bg-white`} />
                <span className="text-white text-xs font-mono">{Math.abs(pitchLine)}</span>
                <div className={`h-[1px] ${pitchLine > 0 ? 'w-8' : 'w-12'} bg-white`} />
              </div>
            </div>
          ))}
        </div>

        {/* Roll Indicator on outer ring */}
        <svg 
          className="absolute inset-0 pointer-events-none"
          viewBox={`0 0 ${size} ${size}`}
        >
          {/* Roll marks */}
          {[-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60].map(angle => {
            const rad = (angle - 90) * Math.PI / 180;
            const innerRadius = radius - 20;
            const outerRadius = radius - 10;
            const x1 = radius + innerRadius * Math.cos(rad);
            const y1 = radius + innerRadius * Math.sin(rad);
            const x2 = radius + outerRadius * Math.cos(rad);
            const y2 = radius + outerRadius * Math.sin(rad);
            
            return (
              <line
                key={angle}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke="white"
                strokeWidth={angle % 30 === 0 ? 2 : 1}
              />
            );
          })}
          
          {/* Current roll indicator */}
          <g transform={`rotate(${roll} ${radius} ${radius})`}>
            <polygon
              points={`${radius},${25} ${radius - 8},${10} ${radius + 8},${10}`}
              fill="#ffaa00"
            />
          </g>
        </svg>

        {/* Center aircraft symbol */}
        <svg 
          className="absolute inset-0 pointer-events-none"
          viewBox={`0 0 ${size} ${size}`}
        >
          <line
            x1={radius - 60}
            y1={radius}
            x2={radius - 10}
            y2={radius}
            stroke="#ffaa00"
            strokeWidth={3}
          />
          <line
            x1={radius + 10}
            y1={radius}
            x2={radius + 60}
            y2={radius}
            stroke="#ffaa00"
            strokeWidth={3}
          />
          <circle
            cx={radius}
            cy={radius}
            r={4}
            fill="#ffaa00"
          />
        </svg>
      </div>

      {/* Numerical display */}
      <div className="flex gap-8">
        <div className="text-center">
          <div className="text-xs text-gray-400">ROLL</div>
          <div className="font-mono text-xl">{roll.toFixed(2)}°</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-400">PITCH</div>
          <div className="font-mono text-xl">{pitch.toFixed(2)}°</div>
        </div>
      </div>
    </div>
  );
}

export default memo(ArtificialHorizon);