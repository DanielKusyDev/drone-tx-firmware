import { useState } from 'react';
import { AlertCircle, AlertTriangle, Info, Check, ChevronDown, ChevronUp } from 'lucide-react';

interface Alert {
  id: string;
  severity: 'critical' | 'warning' | 'info';
  timestamp: string;
  message: string;
  acknowledged: boolean;
}

interface AlertsPanelProps {
  alerts: Alert[];
  onToggle: () => void;
}

export function AlertsPanel({ alerts, onToggle }: AlertsPanelProps) {
  const [acknowledgedAlerts, setAcknowledgedAlerts] = useState<Set<string>>(new Set());

  const handleAcknowledge = (alertId: string) => {
    setAcknowledgedAlerts(prev => new Set([...prev, alertId]));
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return AlertCircle;
      case 'warning':
        return AlertTriangle;
      default:
        return Info;
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return '#ff3344';
      case 'warning':
        return '#ffaa00';
      default:
        return '#00aaff';
    }
  };

  return (
    <div className="h-[200px] bg-[#242424] border-t border-[#333] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-[#333]">
        <div className="flex items-center gap-3">
          <h3 className="font-mono">ALERTS & WARNINGS</h3>
          <div className="flex gap-2">
            <span className="text-xs text-gray-400">
              Total: {alerts.length}
            </span>
            <span className="text-xs text-[#ff3344]">
              Unacknowledged: {alerts.filter(a => !acknowledgedAlerts.has(a.id)).length}
            </span>
          </div>
        </div>
        <button
          onClick={onToggle}
          className="p-2 hover:bg-[#2a2a2a] rounded transition-colors"
        >
          <ChevronDown size={20} />
        </button>
      </div>

      {/* Alerts list */}
      <div className="flex-1 overflow-auto p-4 space-y-2">
        {alerts.slice().reverse().map(alert => {
          const Icon = getSeverityIcon(alert.severity);
          const color = getSeverityColor(alert.severity);
          const isAcknowledged = acknowledgedAlerts.has(alert.id);

          return (
            <div
              key={alert.id}
              className={`flex items-center gap-3 p-3 rounded-lg transition-all ${
                isAcknowledged
                  ? 'bg-[#1a1a1a] opacity-50'
                  : 'bg-[#2a2a2a]'
              }`}
            >
              <Icon size={20} style={{ color }} />
              
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-gray-400">
                    {alert.timestamp}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: color + '30', color }}>
                    {alert.severity.toUpperCase()}
                  </span>
                </div>
                <div className="text-sm mt-1">{alert.message}</div>
              </div>

              {!isAcknowledged && (
                <button
                  onClick={() => handleAcknowledge(alert.id)}
                  className="flex items-center gap-1 px-3 py-1 bg-[#1a1a1a] hover:bg-[#333] rounded text-xs transition-colors"
                >
                  <Check size={14} />
                  ACK
                </button>
              )}

              {isAcknowledged && (
                <div className="flex items-center gap-1 text-xs text-gray-500">
                  <Check size={14} />
                  Acknowledged
                </div>
              )}
            </div>
          );
        })}

        {alerts.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-500">
            <Info size={20} className="mr-2" />
            No alerts
          </div>
        )}
      </div>
    </div>
  );
}
