import { Flag, CloudSun, Compass, Database } from 'lucide-react';
import { PlotlySpec, StandardizedDriverMeta } from '../../types';

interface MetadataBarProps {
  chart: PlotlySpec | null;
  minimap?: PlotlySpec | null;
}

export function MetadataBar({ chart, minimap }: MetadataBarProps) {
  if (!chart || (!chart.data && !chart.layout)) return null;

  const meta = chart.metadata || {};
  const isHistorical = meta.domain === 'historical';

  // 1. Event & Session
  const year = meta.year;
  const gpName = meta.grand_prix || meta.event_name;
  const sessionName = meta.session_name || meta.session_type;

  // 2. Mode / Concept Label
  let modeLabel = meta.mode_label;
  if (!modeLabel) {
    if (chart.chart_type === 'tyre_degradation') {
      modeLabel = 'Tyre Stint Degradation & Strategy';
    } else if (chart.chart_type === 'full_lap_comparison') {
      modeLabel = 'Full-Lap Overlay • All Sectors';
    } else if (chart.chart_type === 'corner_comparison' || Boolean(minimap)) {
      const corner = meta.corner_nickname || (meta.turn_number ? `Turn ${meta.turn_number}` : 'Corner Comparison');
      modeLabel = corner;
    } else if (isHistorical) {
      modeLabel = 'Historical Analytics • DuckDB';
    }
  }

  // 3. Normalize Drivers: support both StandardizedDriverMeta and legacy string array
  const rawDrivers = meta.drivers || [];
  const normalizedDrivers: StandardizedDriverMeta[] = rawDrivers.map((d, idx) => {
    if (typeof d === 'string') {
      const fallbackCompounds = meta.compounds || [];
      return {
        code: d,
        color: idx === 0 ? '#3671C6' : '#FF8000',
        compound: fallbackCompounds[idx],
      };
    }
    return d;
  });

  const hasDrivers = normalizedDrivers.length > 0;
  const trackStatus = meta.track_status;

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-[#1E293B] bg-[#121824]/90 px-3.5 py-2 font-mono text-xs shadow-sm">
      {/* Event and Session */}
      <div className="flex items-center space-x-2">
        <Flag className="h-3.5 w-3.5 text-[#E10600]" />
        {(year || gpName) && (
          <span className="font-bold tracking-wider text-white">
            {[year, gpName ? gpName.toUpperCase() : null].filter(Boolean).join(' ')}
          </span>
        )}
        {sessionName && (
          <span className="rounded bg-[#1E293B] px-1.5 py-0.5 text-[10px] text-[#38BDF8]">
            {sessionName}
          </span>
        )}
      </div>

      {/* Mode / Corner / Scope Reference */}
      {modeLabel && (
        <div className="flex items-center space-x-1.5 text-[#94A3B8]">
          {isHistorical ? (
            <Database className="h-3.5 w-3.5 text-[#38BDF8]" />
          ) : (
            <Compass className="h-3.5 w-3.5 text-[#38BDF8]" />
          )}
          <span className="font-semibold text-[#F8FAFC]">{modeLabel}</span>
        </div>
      )}

      {/* Driver Badges or Historical Scope Badge */}
      {hasDrivers ? (
        <div className="flex items-center space-x-2">
          {normalizedDrivers.map((drv, idx) => (
            <div key={`${drv.code}-${idx}`} className="flex items-center space-x-2">
              {idx > 0 && <span className="text-[#64748B] font-bold">vs</span>}
              <div
                className="flex items-center space-x-1 rounded bg-[#0B0F17] px-2 py-0.5 border"
                style={{ borderColor: drv.color ? `${drv.color}60` : '#38BDF860' }}
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: drv.color || '#38BDF8' }}
                />
                <span className="font-bold text-white">{drv.code}</span>
                {drv.compound && (
                  <span className="rounded bg-white/10 px-1 text-[9px] font-bold text-white">
                    {drv.compound}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : isHistorical ? (
        <div className="flex items-center space-x-1 rounded bg-[#0B0F17] px-2.5 py-0.5 border border-[#38BDF8]/30 text-[10px] text-[#38BDF8]">
          <span className="h-1.5 w-1.5 rounded-full bg-[#38BDF8]"></span>
          <span className="font-semibold tracking-wider">HISTORICAL SQL • DUCKDB</span>
        </div>
      ) : null}

      {/* Optional Track Conditions */}
      {trackStatus && (
        <div className="flex items-center space-x-1 text-[#94A3B8]">
          <CloudSun className="h-3.5 w-3.5 text-amber-400" />
          <span className="text-[11px]">Track: {trackStatus}</span>
        </div>
      )}
    </div>
  );
}
