import { Timer, Gauge } from 'lucide-react';
import { PlotlySpec } from '../../types';

interface SectorSummaryBarProps {
  chart: PlotlySpec | null;
}

export function SectorSummaryBar({ chart }: SectorSummaryBarProps) {
  if (!chart || chart.chart_type !== 'full_lap_comparison') {
    return null;
  }

  const meta = chart.metadata || {};
  const metrics = meta.metrics || meta.sector_summary || {};
  const sectors = metrics?.sectors;
  const speedTrap = metrics?.speed_trap;
  const lapTimes = metrics?.lap_times;

  if (!sectors) {
    return null;
  }

  const rawDrivers = Array.isArray(meta.drivers) ? meta.drivers : [];
  const getDriverCode = (drv: any, fallback: string): string => {
    if (!drv) return fallback;
    if (typeof drv === 'string') return drv;
    if (typeof drv === 'object' && drv.code) return String(drv.code);
    return fallback;
  };

  const drvA = getDriverCode(rawDrivers[0], 'DRV1');
  const drvB = getDriverCode(rawDrivers[1], 'DRV2');

  const s1 = sectors.sector_1;
  const s2 = sectors.sector_2;
  const s3 = sectors.sector_3;

  const fmtTime = (val?: number | null): string => {
    if (val === undefined || val === null || isNaN(val)) return '--';
    return `${Number(val).toFixed(3)}s`;
  };

  const fmtSpeed = (val?: number | null): string => {
    if (val === undefined || val === null || isNaN(val)) return '--';
    return `${Number(val).toFixed(1)} km/h`;
  };

  const renderDeltaBadge = (delta?: number | null, faster?: string) => {
    if (delta === undefined || delta === null || isNaN(delta)) {
      return <span className="text-[#94A3B8]">--</span>;
    }
    const isZero = Math.abs(delta) < 0.001;
    if (isZero) return <span className="text-[#94A3B8]">EVEN</span>;
    return (
      <span className="font-bold text-[#38BDF8]">
        {faster || ''} -{Math.abs(delta).toFixed(3)}s
      </span>
    );
  };

  return (
    <div className="rounded-lg border border-[#1E293B] bg-[#121824] p-3 font-mono text-xs shadow-md">
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-[#1E293B]/70">
        <div className="flex items-center space-x-2">
          <Timer className="h-4 w-4 text-[#38BDF8]" />
          <span className="font-bold uppercase tracking-wider text-white">
            Official Sector Splits & Speed Trap Summary
          </span>
        </div>
        {lapTimes && lapTimes.delta_s != null && (
          <div className="text-[11px] text-[#94A3B8]">
            Finish Delta:{' '}
            <span className="font-bold text-emerald-400">
              {lapTimes.faster || ''} -{Math.abs(lapTimes.delta_s).toFixed(3)}s
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {/* Sector 1 */}
        {s1 && (
          <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
            <div className="flex items-center justify-between text-[10px] text-[#94A3B8] mb-1">
              <span>SECTOR 1</span>
              {renderDeltaBadge(s1.delta_s, s1.faster)}
            </div>
            <div className="flex items-center justify-between text-[11px] text-[#E2E8F0]">
              <span>{drvA}: {fmtTime(s1.driver_a)}</span>
              <span>{drvB}: {fmtTime(s1.driver_b)}</span>
            </div>
          </div>
        )}

        {/* Sector 2 */}
        {s2 && (
          <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
            <div className="flex items-center justify-between text-[10px] text-[#94A3B8] mb-1">
              <span>SECTOR 2</span>
              {renderDeltaBadge(s2.delta_s, s2.faster)}
            </div>
            <div className="flex items-center justify-between text-[11px] text-[#E2E8F0]">
              <span>{drvA}: {fmtTime(s2.driver_a)}</span>
              <span>{drvB}: {fmtTime(s2.driver_b)}</span>
            </div>
          </div>
        )}

        {/* Sector 3 */}
        {s3 && (
          <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
            <div className="flex items-center justify-between text-[10px] text-[#94A3B8] mb-1">
              <span>SECTOR 3</span>
              {renderDeltaBadge(s3.delta_s, s3.faster)}
            </div>
            <div className="flex items-center justify-between text-[11px] text-[#E2E8F0]">
              <span>{drvA}: {fmtTime(s3.driver_a)}</span>
              <span>{drvB}: {fmtTime(s3.driver_b)}</span>
            </div>
          </div>
        )}

        {/* Speed Trap */}
        {speedTrap && (
          <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
            <div className="flex items-center justify-between text-[10px] text-[#94A3B8] mb-1">
              <span className="flex items-center space-x-1">
                <Gauge className="h-3 w-3 text-amber-400" />
                <span>SPEED TRAP</span>
              </span>
              <span className="font-bold text-amber-400">
                {speedTrap.delta_kph != null
                  ? `${speedTrap.delta_kph > 0 ? `+${speedTrap.delta_kph.toFixed(1)}` : speedTrap.delta_kph.toFixed(1)} km/h`
                  : '--'}
              </span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-[#E2E8F0]">
              <span>{drvA}: {fmtSpeed(speedTrap.driver_a)}</span>
              <span>{drvB}: {fmtSpeed(speedTrap.driver_b)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
