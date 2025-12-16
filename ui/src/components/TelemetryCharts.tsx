import { useState } from 'react';
import { memo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Grid3x3, ZoomIn, ZoomOut } from 'lucide-react';

interface TelemetryChartsProps {
  history: {
    attitude: Array<{ time: number; roll: number; pitch: number; yaw: number }>;
    motors: Array<{ time: number; m1: number; m2: number; m3: number; m4: number }>;
    pid: Array<{ time: number; setpoint: number; actual: number; error: number }>;
  };
  currentTime: number;
}

type TabType = 'FLIGHT' | 'MOTORS' | 'PID' | 'DIAGNOSTICS';

export function TelemetryCharts({ history, currentTime }: TelemetryChartsProps) {
  const [activeTab, setActiveTab] = useState<TabType>('FLIGHT');
  const [timeRange, setTimeRange] = useState(10);
  const [showGrid, setShowGrid] = useState(true);

  const tabs: TabType[] = ['FLIGHT', 'MOTORS', 'PID', 'DIAGNOSTICS'];
  const timeRanges = [10, 30, 60];

  const getFilteredData = (data: any[]) => {
    return data.filter(d => d.time >= currentTime - timeRange);
  };

  const renderChart = () => {
    switch (activeTab) {
      case 'FLIGHT':
        return (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={getFilteredData(history.attitude)}>
              {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#333" />}
              <XAxis 
                dataKey="time" 
                stroke="#666"
                tick={{ fill: '#666' }}
                tickFormatter={(value) => `${(currentTime - value).toFixed(1)}s`}
              />
              <YAxis 
                stroke="#666"
                tick={{ fill: '#666' }}
                label={{ value: 'Angle (°)', angle: -90, position: 'insideLeft', fill: '#666' }}
              />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
                labelFormatter={(value) => `Time: ${value.toFixed(2)}s`}
              />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="roll" 
                stroke="#ff3344" 
                strokeWidth={2}
                dot={false}
                name="Roll"
              />
              <Line 
                type="monotone" 
                dataKey="pitch" 
                stroke="#00aaff" 
                strokeWidth={2}
                dot={false}
                name="Pitch"
              />
              <Line 
                type="monotone" 
                dataKey="yaw" 
                stroke="#00ff88" 
                strokeWidth={2}
                dot={false}
                name="Yaw"
              />
            </LineChart>
          </ResponsiveContainer>
        );

      case 'MOTORS':
        return (
          <div className="h-full flex gap-4">
            {/* Drone Diagram */}
            <div className="w-48 flex flex-col justify-center items-center bg-[#1a1a1a] rounded-lg p-4">
              <div className="text-xs text-gray-400 mb-4">MOTOR LAYOUT</div>
              <svg viewBox="0 0 200 200" className="w-full h-auto">
                {/* Center body */}
                <circle cx="100" cy="100" r="30" fill="#2a2a2a" stroke="#444" strokeWidth="2"/>
                
                {/* Arms */}
                <line x1="100" y1="100" x2="150" y2="50" stroke="#444" strokeWidth="3"/>
                <line x1="100" y1="100" x2="150" y2="150" stroke="#444" strokeWidth="3"/>
                <line x1="100" y1="100" x2="50" y2="150" stroke="#444" strokeWidth="3"/>
                <line x1="100" y1="100" x2="50" y2="50" stroke="#444" strokeWidth="3"/>
                
                {/* Front indicator (arrow) */}
                <path d="M 100 20 L 110 35 L 90 35 Z" fill="#00aaff"/>
                <text x="100" y="15" textAnchor="middle" fill="#00aaff" fontSize="10" fontWeight="bold">FWD</text>
                
                {/* Motor 1 - Front Right */}
                <circle cx="150" cy="50" r="15" fill="#ff3344" opacity="0.8"/>
                <text x="150" y="55" textAnchor="middle" fill="white" fontSize="12" fontWeight="bold">M1</text>
                <text x="150" y="30" textAnchor="middle" fill="#ff3344" fontSize="9">FR</text>
                
                {/* Motor 2 - Rear Right */}
                <circle cx="150" cy="150" r="15" fill="#00aaff" opacity="0.8"/>
                <text x="150" y="155" textAnchor="middle" fill="white" fontSize="12" fontWeight="bold">M2</text>
                <text x="150" y="175" textAnchor="middle" fill="#00aaff" fontSize="9">RR</text>
                
                {/* Motor 3 - Rear Left */}
                <circle cx="50" cy="150" r="15" fill="#00ff88" opacity="0.8"/>
                <text x="50" y="155" textAnchor="middle" fill="white" fontSize="12" fontWeight="bold">M3</text>
                <text x="50" y="175" textAnchor="middle" fill="#00ff88" fontSize="9">RL</text>
                
                {/* Motor 4 - Front Left */}
                <circle cx="50" cy="50" r="15" fill="#ffaa00" opacity="0.8"/>
                <text x="50" y="55" textAnchor="middle" fill="white" fontSize="12" fontWeight="bold">M4</text>
                <text x="50" y="30" textAnchor="middle" fill="#ffaa00" fontSize="9">FL</text>
                
                {/* Rotation direction indicators (propellers) */}
                <path d="M 150 50 m -8,-8 l 16,16 M 150 50 m -8,8 l 16,-16" stroke="white" strokeWidth="1" opacity="0.3"/> {/* CW */}
                <path d="M 150 150 m -8,-8 l 16,16 M 150 150 m -8,8 l 16,-16" stroke="white" strokeWidth="1" opacity="0.3"/> {/* CW */}
                <path d="M 50 150 m -8,-8 l 16,16 M 50 150 m -8,8 l 16,-16" stroke="white" strokeWidth="1" opacity="0.3"/> {/* CW */}
                <path d="M 50 50 m -8,-8 l 16,16 M 50 50 m -8,8 l 16,-16" stroke="white" strokeWidth="1" opacity="0.3"/> {/* CW */}
              </svg>
              <div className="mt-4 space-y-1 text-xs w-full">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{backgroundColor: '#ff3344'}}></div>
                  <span className="text-gray-400">M1: Front Right</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{backgroundColor: '#00aaff'}}></div>
                  <span className="text-gray-400">M2: Rear Right</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{backgroundColor: '#00ff88'}}></div>
                  <span className="text-gray-400">M3: Rear Left</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{backgroundColor: '#ffaa00'}}></div>
                  <span className="text-gray-400">M4: Front Left</span>
                </div>
              </div>
            </div>
            
            {/* Chart */}
            <div className="flex-1">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={getFilteredData(history.motors)}>
                  {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#333" />}
                  <XAxis 
                    dataKey="time" 
                    stroke="#666"
                    tick={{ fill: '#666' }}
                    tickFormatter={(value) => `${(currentTime - value).toFixed(1)}s`}
                  />
                  <YAxis 
                    stroke="#666"
                    tick={{ fill: '#666' }}
                    domain={[0, 65535]}
                    label={{ value: 'Command', angle: -90, position: 'insideLeft', fill: '#666' }}
                  />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
                    labelFormatter={(value) => `Time: ${value.toFixed(2)}s`}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="m1" stroke="#ff3344" strokeWidth={2} dot={false} name="Motor 1 (FR)" />
                  <Line type="monotone" dataKey="m2" stroke="#00aaff" strokeWidth={2} dot={false} name="Motor 2 (RR)" />
                  <Line type="monotone" dataKey="m3" stroke="#00ff88" strokeWidth={2} dot={false} name="Motor 3 (RL)" />
                  <Line type="monotone" dataKey="m4" stroke="#ffaa00" strokeWidth={2} dot={false} name="Motor 4 (FL)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        );

      case 'PID':
        return (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={getFilteredData(history.pid)}>
              {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#333" />}
              <XAxis 
                dataKey="time" 
                stroke="#666"
                tick={{ fill: '#666' }}
                tickFormatter={(value) => `${(currentTime - value).toFixed(1)}s`}
              />
              <YAxis 
                stroke="#666"
                tick={{ fill: '#666' }}
                label={{ value: 'Angle (°)', angle: -90, position: 'insideLeft', fill: '#666' }}
              />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
                labelFormatter={(value) => `Time: ${value.toFixed(2)}s`}
              />
              <Legend />
              <Line type="monotone" dataKey="setpoint" stroke="#ffaa00" strokeWidth={2} dot={false} name="Setpoint" />
              <Line type="monotone" dataKey="actual" stroke="#00aaff" strokeWidth={2} dot={false} name="Actual" />
              <Line type="monotone" dataKey="error" stroke="#ff3344" strokeWidth={1} dot={false} name="Error" strokeDasharray="5 5" />
            </LineChart>
          </ResponsiveContainer>
        );

      case 'DIAGNOSTICS':
        return (
          <div className="h-full overflow-auto p-4 space-y-4">
            <div className="bg-[#1a1a1a] rounded-lg p-4">
              <h3 className="text-sm text-gray-400 mb-3">Performance Metrics</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-gray-500">Loop Time</div>
                  <div className="font-mono text-[#00ff88]">2.5 ms</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">CPU Load</div>
                  <div className="font-mono text-[#00aaff]">23%</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">IMU Time</div>
                  <div className="font-mono text-[#00ff88]">0.8 ms</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Control Time</div>
                  <div className="font-mono text-[#00aaff]">1.2 ms</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Free Heap</div>
                  <div className="font-mono text-[#00ff88]">245 KB</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Stack Usage</div>
                  <div className="font-mono text-[#ffaa00]">45%</div>
                </div>
              </div>
            </div>

            <div className="bg-[#1a1a1a] rounded-lg p-4">
              <h3 className="text-sm text-gray-400 mb-3">Sensor Raw Data</h3>
              <div className="space-y-2 text-xs font-mono">
                <div className="flex justify-between">
                  <span className="text-gray-500">Gyro X/Y/Z:</span>
                  <span className="text-white">0.12 / -0.34 / 0.05 °/s</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Accel X/Y/Z:</span>
                  <span className="text-white">0.01 / 0.02 / 9.81 m/s²</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Mag X/Y/Z:</span>
                  <span className="text-white">234 / -123 / 456 mG</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Temperature:</span>
                  <span className="text-white">24.5 °C</span>
                </div>
              </div>
            </div>

            <div className="bg-[#1a1a1a] rounded-lg p-4">
              <h3 className="text-sm text-gray-400 mb-3">System Info</h3>
              <div className="space-y-2 text-xs font-mono">
                <div className="flex justify-between">
                  <span className="text-gray-500">Loop Rate:</span>
                  <span className="text-white">200.5 Hz</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Packets Received:</span>
                  <span className="text-white">1,234</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">CRC Errors:</span>
                  <span className="text-[#00ff88]">0</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Parser Errors:</span>
                  <span className="text-[#00ff88]">0</span>
                </div>
              </div>
            </div>
          </div>
        );
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header with tabs and controls */}
      <div className="flex items-center justify-between mb-4 pb-4 border-b border-[#333]">
        {/* Tabs */}
        <div className="flex gap-2">
          {tabs.map(tab => (
            <button
              key={tab}
              onClick={() => tab !== 'DIAGNOSTICS' && setActiveTab(tab)}
              disabled={tab === 'DIAGNOSTICS'}
              className={`px-4 py-2 rounded-md font-mono text-sm transition-colors relative ${
                activeTab === tab
                  ? 'bg-[#00aaff] text-white'
                  : tab === 'DIAGNOSTICS'
                  ? 'bg-[#1a1a1a] text-gray-600 cursor-not-allowed opacity-50'
                  : 'bg-[#1a1a1a] text-gray-400 hover:bg-[#2a2a2a]'
              }`}
            >
              {tab}
              {tab === 'DIAGNOSTICS' && (
                <span className="absolute -top-1 -right-1 bg-[#ffaa00] text-[#1a1a1a] text-[9px] px-1.5 py-0.5 rounded-full font-mono">
                  SOON
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Controls */}
        {activeTab !== 'DIAGNOSTICS' && (
          <div className="flex items-center gap-2">
            {/* Time range selector */}
            <div className="flex gap-1">
              {timeRanges.map(range => (
                <button
                  key={range}
                  onClick={() => setTimeRange(range)}
                  className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                    timeRange === range
                      ? 'bg-[#00aaff] text-white'
                      : 'bg-[#1a1a1a] text-gray-400 hover:bg-[#2a2a2a]'
                  }`}
                >
                  {range}s
                </button>
              ))}
            </div>

            {/* Grid toggle */}
            <button
              onClick={() => setShowGrid(!showGrid)}
              className={`p-2 rounded transition-colors ${
                showGrid
                  ? 'bg-[#00aaff] text-white'
                  : 'bg-[#1a1a1a] text-gray-400 hover:bg-[#2a2a2a]'
              }`}
            >
              <Grid3x3 size={16} />
            </button>
          </div>
        )}
      </div>

      {/* Chart area */}
      <div className="flex-1 min-h-0">
        {renderChart()}
      </div>
    </div>
  );
}

export default memo(TelemetryCharts);