import { Navigation, ShieldAlert, Loader2, Battery, AlertTriangle, Radio, TrendingUp } from 'lucide-react';

interface SafetyFlagsProps {
  flags: {
    horizonOK: boolean;
    forceDisarm: boolean;
    calibrating: boolean;
    lowBattery: boolean;
    sensorFailure: boolean;
    failsafeActive: boolean;
    angleLimitExceeded: boolean;
  };
}

export function SafetyFlags({ flags }: SafetyFlagsProps) {
  const flagItems = [
    {
      key: 'horizonOK',
      icon: Navigation,
      label: 'Horizon OK',
      active: flags.horizonOK,
      color: flags.horizonOK ? '#00ff88' : '#ff3344',
    },
    {
      key: 'calibrating',
      icon: Loader2,
      label: 'Calibrating',
      active: flags.calibrating,
      color: flags.calibrating ? '#ffaa00' : '#666',
    },
    {
      key: 'forceDisarm',
      icon: ShieldAlert,
      label: 'Force Disarm',
      active: flags.forceDisarm,
      color: flags.forceDisarm ? '#ff3344' : '#666',
    },
    {
      key: 'lowBattery',
      icon: Battery,
      label: 'Low Battery',
      active: flags.lowBattery,
      color: flags.lowBattery ? '#ff3344' : '#666',
    },
    {
      key: 'sensorFailure',
      icon: AlertTriangle,
      label: 'Sensor Failure',
      active: flags.sensorFailure,
      color: flags.sensorFailure ? '#ff3344' : '#666',
    },
    {
      key: 'failsafeActive',
      icon: Radio,
      label: 'Failsafe Active',
      active: flags.failsafeActive,
      color: flags.failsafeActive ? '#ff3344' : '#666',
    },
    {
      key: 'angleLimitExceeded',
      icon: TrendingUp,
      label: 'Angle Limit Exceeded',
      active: flags.angleLimitExceeded,
      color: flags.angleLimitExceeded ? '#ffaa00' : '#666',
    },
  ];

  return (
    <div className="flex items-center gap-3">
      {flagItems.map(({ key, icon: Icon, label, active, color }) => (
        <div key={key} className="group relative">
          <Icon
            size={20}
            style={{ color }}
            className={active && key === 'calibrating' ? 'animate-spin' : ''}
          />
          <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 px-2 py-1 bg-black text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
            {label}
          </div>
        </div>
      ))}
    </div>
  );
}
