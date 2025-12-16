import { useEffect, useRef, useState } from 'react';
import { Activity } from 'lucide-react';

interface PerformanceMetrics {
  fps: number;
  renderTime: number;
  updateRate: number;
  memoryMB: number | null;
}

export function PerformanceMonitor() {
  const [metrics, setMetrics] = useState<PerformanceMetrics>({
    fps: 60,
    renderTime: 0,
    updateRate: 0,
    memoryMB: null,
  });
  const [expanded, setExpanded] = useState(false);
  
  const frameCountRef = useRef(0);
  const lastTimeRef = useRef(performance.now());
  const updateCountRef = useRef(0);

  // Track state updates (increment when component re-renders)
  useEffect(() => {
    updateCountRef.current++;
  });

  // Track FPS and update rate
  useEffect(() => {
    let animationFrameId: number;

    const measureFPS = () => {
      frameCountRef.current++;
      const now = performance.now();
      const elapsed = now - lastTimeRef.current;

      if (elapsed >= 1000) {
        const fps = Math.round((frameCountRef.current * 1000) / elapsed);
        const updateRate = updateCountRef.current;

        // Get memory if available
        let memoryMB = null;
        if ('memory' in performance && (performance as any).memory) {
          memoryMB = Math.round((performance as any).memory.usedJSHeapSize / 1048576);
        }

        setMetrics({
          fps,
          renderTime: 0, // Removed render time tracking to avoid infinite loop
          updateRate,
          memoryMB,
        });

        frameCountRef.current = 0;
        updateCountRef.current = 0;
        lastTimeRef.current = now;
      }

      animationFrameId = requestAnimationFrame(measureFPS);
    };

    animationFrameId = requestAnimationFrame(measureFPS);

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  const getStatusColor = (fps: number) => {
    if (fps >= 55) return '#00ff88'; // Green - good
    if (fps >= 30) return '#ffaa00'; // Orange - warning
    return '#ff3344'; // Red - critical
  };

  const getStatusText = (fps: number) => {
    if (fps >= 55) return 'GOOD';
    if (fps >= 30) return 'FAIR';
    return 'POOR';
  };

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="fixed bottom-4 left-4 bg-[#242424] p-2 rounded-lg hover:bg-[#2a2a2a] transition-colors border border-[#333] z-50"
        title="Show Performance Monitor"
      >
        <Activity size={20} style={{ color: getStatusColor(metrics.fps) }} />
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 left-4 bg-[#242424] rounded-lg border border-[#333] p-4 font-mono text-xs z-50 min-w-[240px]">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity size={16} style={{ color: getStatusColor(metrics.fps) }} />
          <span className="text-sm">Performance Monitor</span>
        </div>
        <button
          onClick={() => setExpanded(false)}
          className="text-gray-500 hover:text-white transition-colors"
        >
          ✕
        </button>
      </div>

      <div className="space-y-2">
        {/* FPS */}
        <div className="flex justify-between items-center">
          <span className="text-gray-400">FPS:</span>
          <span style={{ color: getStatusColor(metrics.fps) }}>
            {metrics.fps} <span className="text-xs">({getStatusText(metrics.fps)})</span>
          </span>
        </div>

        {/* Render Time */}
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Render:</span>
          <span className={metrics.renderTime > 16 ? 'text-[#ffaa00]' : 'text-[#00ff88]'}>
            {metrics.renderTime.toFixed(2)}ms
          </span>
        </div>

        {/* Update Rate */}
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Updates/sec:</span>
          <span className={metrics.updateRate > 30 ? 'text-[#ffaa00]' : 'text-[#00aaff]'}>
            {metrics.updateRate}
          </span>
        </div>

        {/* Memory */}
        {metrics.memoryMB !== null && (
          <div className="flex justify-between items-center">
            <span className="text-gray-400">Memory:</span>
            <span className="text-[#00aaff]">
              {metrics.memoryMB}MB
            </span>
          </div>
        )}

        <div className="pt-2 mt-2 border-t border-[#333] text-[10px] text-gray-500">
          <div>Target: 60 FPS / &lt;16ms</div>
          <div className="mt-1">
            {metrics.updateRate > 30 && (
              <div className="text-[#ffaa00]">⚠ High update rate detected</div>
            )}
            {metrics.renderTime > 16 && (
              <div className="text-[#ffaa00]">⚠ Slow renders detected</div>
            )}
            {metrics.fps < 30 && (
              <div className="text-[#ff3344]">🔴 Performance issue detected</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}