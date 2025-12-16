import { useState } from 'react';
import { Settings, X, Wifi, WifiOff, RefreshCw } from 'lucide-react';

interface SettingsPanelProps {
  apiBaseUrl: string;
  useSimulatedData: boolean;
  connected: boolean;
  lastUpdate: number | null;
  onApiUrlChange: (url: string) => void;
  onSimulatedDataToggle: (enabled: boolean) => void;
}

export function SettingsPanel({
  apiBaseUrl,
  useSimulatedData,
  connected,
  lastUpdate,
  onApiUrlChange,
  onSimulatedDataToggle,
}: SettingsPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [urlInput, setUrlInput] = useState(apiBaseUrl);

  const handleUrlSubmit = () => {
    onApiUrlChange(urlInput);
  };

  const getConnectionStatus = () => {
    if (useSimulatedData) {
      return { text: 'SIMULATED', color: '#ffaa00', icon: WifiOff };
    }
    if (connected && lastUpdate) {
      const age = Date.now() / 1000 - lastUpdate;
      if (age < 2) {
        return { text: 'CONNECTED', color: '#00ff88', icon: Wifi };
      }
    }
    return { text: 'DISCONNECTED', color: '#ff3344', icon: WifiOff };
  };

  const status = getConnectionStatus();
  const StatusIcon = status.icon;

  return (
    <>
      {/* Settings Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed top-20 right-4 bg-[#242424] p-3 rounded-lg hover:bg-[#2a2a2a] transition-colors border border-[#333] z-50"
      >
        <Settings size={20} />
      </button>

      {/* Connection Status Indicator */}
      <div 
        className="fixed top-20 left-4 bg-[#242424] px-4 py-2 rounded-lg border border-[#333] flex items-center gap-2"
        style={{ borderColor: status.color }}
      >
        <StatusIcon size={16} style={{ color: status.color }} />
        <span className="font-mono text-sm" style={{ color: status.color }}>
          {status.text}
        </span>
        {!useSimulatedData && lastUpdate && (
          <span className="text-xs text-gray-500">
            ({Math.round((Date.now() / 1000 - lastUpdate) * 1000)}ms ago)
          </span>
        )}
      </div>

      {/* Settings Panel */}
      {isOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[#242424] rounded-lg border border-[#333] w-full max-w-md p-6">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-mono">SETTINGS</h2>
              <button
                onClick={() => setIsOpen(false)}
                className="p-2 hover:bg-[#2a2a2a] rounded transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            {/* Data Source Toggle */}
            <div className="mb-6">
              <label className="text-sm text-gray-400 mb-2 block">DATA SOURCE</label>
              <div className="flex gap-2">
                <button
                  onClick={() => onSimulatedDataToggle(false)}
                  className={`flex-1 px-4 py-2 rounded-md font-mono text-sm transition-colors ${
                    !useSimulatedData
                      ? 'bg-[#00aaff] text-white'
                      : 'bg-[#1a1a1a] text-gray-400 hover:bg-[#2a2a2a]'
                  }`}
                >
                  REAL API
                </button>
                <button
                  onClick={() => onSimulatedDataToggle(true)}
                  className={`flex-1 px-4 py-2 rounded-md font-mono text-sm transition-colors ${
                    useSimulatedData
                      ? 'bg-[#00aaff] text-white'
                      : 'bg-[#1a1a1a] text-gray-400 hover:bg-[#2a2a2a]'
                  }`}
                >
                  SIMULATED
                </button>
              </div>
            </div>

            {/* API URL Configuration */}
            {!useSimulatedData && (
              <div className="mb-6">
                <label className="text-sm text-gray-400 mb-2 block">API BASE URL</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    placeholder="http://localhost:8000"
                    className="flex-1 bg-[#1a1a1a] border border-[#333] rounded-md px-3 py-2 font-mono text-sm focus:outline-none focus:border-[#00aaff]"
                  />
                  <button
                    onClick={handleUrlSubmit}
                    className="px-4 py-2 bg-[#00aaff] hover:bg-[#0099ee] text-white rounded-md font-mono text-sm transition-colors"
                  >
                    APPLY
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  Enter the base URL of your drone telemetry API server
                </p>
              </div>
            )}

            {/* Connection Info */}
            <div className="bg-[#1a1a1a] rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs text-gray-400">CONNECTION STATUS</div>
                {!useSimulatedData && !connected && (
                  <button
                    onClick={handleUrlSubmit}
                    className="flex items-center gap-1 px-2 py-1 bg-[#00aaff] hover:bg-[#0099ee] text-white rounded text-xs transition-colors"
                  >
                    <RefreshCw size={12} />
                    RECONNECT
                  </button>
                )}
              </div>
              <div className="flex items-center gap-2 mb-2">
                <div 
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: status.color }}
                />
                <span className="font-mono text-sm" style={{ color: status.color }}>
                  {status.text}
                </span>
              </div>
              {!useSimulatedData && (
                <>
                  <div className="text-xs text-gray-500">
                    WebSocket: {apiBaseUrl.replace(/^http/, 'ws')}/ws/telemetry
                  </div>
                  {lastUpdate && (
                    <div className="text-xs text-gray-500 mt-1">
                      Last update: {new Date(lastUpdate * 1000).toLocaleTimeString()}
                    </div>
                  )}
                </>
              )}
              {useSimulatedData && (
                <div className="text-xs text-gray-500">
                  Using simulated flight data for demonstration
                </div>
              )}
            </div>

            {/* Help Text */}
            <div className="mt-4 text-xs text-gray-500">
              <p className="mb-1">To use real telemetry data:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>Start your drone telemetry API server</li>
                <li>Set the correct API base URL above</li>
                <li>Select "REAL API" as the data source</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </>
  );
}