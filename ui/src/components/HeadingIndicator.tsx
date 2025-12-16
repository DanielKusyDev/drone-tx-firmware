import { memo } from 'react';

interface HeadingIndicatorProps {
  yaw: number;
}

export function HeadingIndicator({ yaw }: HeadingIndicatorProps) {
  const size = 200;
  const radius = size / 2;
  const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="text-xs text-gray-400">HEADING</div>
      <div className="relative" style={{ width: size, height: size }}>
        {/* Compass Rose */}
        <svg 
          className="absolute inset-0"
          viewBox={`0 0 ${size} ${size}`}
          style={{
            transform: `rotate(${-yaw}deg)`,
            transition: 'transform 0.1s linear',
          }}
        >
          {/* Outer circle */}
          <circle
            cx={radius}
            cy={radius}
            r={radius - 10}
            fill="none"
            stroke="#333"
            strokeWidth={2}
          />

          {/* Degree marks */}
          {Array.from({ length: 36 }, (_, i) => i * 10).map(angle => {
            const rad = (angle - 90) * Math.PI / 180;
            const innerRadius = radius - 25;
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
                stroke="#666"
                strokeWidth={angle % 90 === 0 ? 3 : angle % 30 === 0 ? 2 : 1}
              />
            );
          })}

          {/* Cardinal directions */}
          {directions.map((dir, i) => {
            const angle = i * 45;
            const rad = (angle - 90) * Math.PI / 180;
            const textRadius = radius - 40;
            const x = radius + textRadius * Math.cos(rad);
            const y = radius + textRadius * Math.sin(rad);
            
            return (
              <text
                key={dir}
                x={x}
                y={y}
                textAnchor="middle"
                dominantBaseline="middle"
                className="text-sm font-mono"
                fill={dir === 'N' ? '#ff3344' : '#00aaff'}
                transform={`rotate(${yaw} ${x} ${y})`}
              >
                {dir}
              </text>
            );
          })}
        </svg>

        {/* Fixed aircraft indicator at top */}
        <svg 
          className="absolute inset-0 pointer-events-none"
          viewBox={`0 0 ${size} ${size}`}
        >
          <polygon
            points={`${radius},${15} ${radius - 6},${25} ${radius + 6},${25}`}
            fill="#ffaa00"
          />
        </svg>
      </div>

      {/* Numerical display */}
      <div className="font-mono text-xl">{yaw.toFixed(2)}°</div>
    </div>
  );
}

export default memo(HeadingIndicator);