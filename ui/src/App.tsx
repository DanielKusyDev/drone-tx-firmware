import { useState } from 'react';
import { StatusBar } from './components/StatusBar';
import { ArtificialHorizon } from './components/ArtificialHorizon';
import { HeadingIndicator } from './components/HeadingIndicator';
import { RateIndicators } from './components/RateIndicators';
import { MotorStatus } from './components/MotorStatus';
import { TelemetryCharts } from './components/TelemetryCharts';
import { AlertsPanel } from './components/AlertsPanel';
import { SettingsPanel } from './components/SettingsPanel';
import { PerformanceMonitor } from './components/PerformanceMonitor';
import { useTelemetryData } from './hooks/useTelemetryData';
import { WifiOff } from 'lucide-react';

export default function App() {
  const [showAlerts, setShowAlerts] = useState(true);
  const { 
    telemetryData, 
    setArmed,
    setApiBaseUrl,
    setUseSimulatedData,
    apiBaseUrl,
    useSimulatedData,
  } = useTelemetryData();

  return (
    <div className="min-h-screen bg-[#1a1a1a] text-white flex flex-col">
      {/* Settings Panel */}
      <SettingsPanel
        apiBaseUrl={apiBaseUrl}
        useSimulatedData={useSimulatedData}
        connected={telemetryData.connected}
        lastUpdate={telemetryData.lastUpdate}
        onApiUrlChange={setApiBaseUrl}
        onSimulatedDataToggle={setUseSimulatedData}
      />

      {/* Top Status Bar */}
      <StatusBar data={telemetryData} onArmToggle={() => setArmed(!telemetryData.armed)} />

      {/* Main Content Area */}
      <div className="flex-1 flex gap-4 p-4 overflow-hidden relative">
        {/* Disconnected Overlay */}
        {!telemetryData.connected && !useSimulatedData && (
          <div className="absolute inset-0 bg-black/70 flex items-center justify-center z-40 backdrop-blur-sm">
            <div className="text-center">
              <WifiOff size={64} className="text-[#ff3344] mx-auto mb-4" />
              <div className="text-2xl font-mono mb-2">NO DATA</div>
              <div className="text-gray-400 mb-4">
                Unable to connect to drone telemetry API
              </div>
              <div className="text-sm text-gray-500 mb-6">
                Check settings and ensure API server is running
              </div>
              <button
                onClick={() => setUseSimulatedData(true)}
                className="px-6 py-3 bg-[#00aaff] hover:bg-[#0099ee] text-white rounded-lg font-mono transition-colors"
              >
                RUN SIMULATION
              </button>
            </div>
          </div>
        )}

        {/* LEFT COLUMN - Primary Flight Display */}
        <div className="w-[35%] flex flex-col gap-4">
          <div className="bg-[#242424] rounded-lg p-6 flex-1 flex flex-col items-center justify-center">
            <ArtificialHorizon 
              roll={telemetryData.attitude.roll} 
              pitch={telemetryData.attitude.pitch}
            />
          </div>
          <div className="bg-[#242424] rounded-lg p-6">
            <HeadingIndicator yaw={telemetryData.attitude.yaw} />
          </div>
          <div className="bg-[#242424] rounded-lg p-4">
            <RateIndicators rates={telemetryData.rates} />
          </div>
        </div>

        {/* MIDDLE COLUMN - Charts & Timeline */}
        <div className="w-[40%] bg-[#242424] rounded-lg p-4 flex flex-col">
          <TelemetryCharts 
            history={telemetryData.history}
            currentTime={telemetryData.uptime}
          />
        </div>

        {/* RIGHT COLUMN - Motor Status */}
        <div className="w-[25%] bg-[#242424] rounded-lg p-6">
          <MotorStatus 
            motors={telemetryData.motors}
            baseThrottle={telemetryData.baseThrottle}
            mixerId={telemetryData.mixerId}
          />
        </div>
      </div>

      {/* Bottom Alerts Panel */}
      {showAlerts && (
        <AlertsPanel 
          alerts={telemetryData.alerts}
          onToggle={() => setShowAlerts(false)}
        />
      )}
      
      {!showAlerts && (
        <button
          onClick={() => setShowAlerts(true)}
          className="fixed bottom-4 right-4 bg-[#242424] px-4 py-2 rounded-lg hover:bg-[#2a2a2a] transition-colors"
        >
          Show Alerts ({telemetryData.alerts.filter(a => !a.acknowledged).length})
        </button>
      )}

      {/* Performance Monitor */}
      <PerformanceMonitor />
    </div>
  );
}