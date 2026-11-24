import { Flag, CloudSun, Compass } from 'lucide-react';
import { PlotlySpec } from '../../types';

interface MetadataBarProps {
  chart: PlotlySpec | null;
  minimap: PlotlySpec | null;
}

export function MetadataBar({ chart, minimap }: MetadataBarProps) {
  if (!chart || (!chart.data && !chart.layout)) return null;

  // Extract metadata from chart layout or spec
  const meta = chart.metadata || {};
  const isTelemetry =
    chart.chart_type === 'corner_comparison' ||
    chart.chart_type === 'full_lap_comparison' ||
    Boolean(minimap);

  if (!isTelemetry) return null;

  const isFullLap = chart.chart_type === 'full_lap_comparison';
  const titleText = chart.layout?.title?.text || '';
  const isCopse = titleText.toLowerCase().includes('copse');
  const isEauRouge = titleText.toLowerCase().includes('eau rouge');
  const is130R = titleText.toLowerCase().includes('130r');

  let cornerName = isFullLap ? 'Full-Lap Overlay • All Sectors' : 'Corner Comparison';
  if (isCopse) cornerName = 'Copse • Turn 9';
  else if (isEauRouge) cornerName = 'Eau Rouge • Turn 2';
  else if (is130R) cornerName = '130R • Turn 15';

  const year = meta.year || 2024;
  const gpName = meta.event_name || (isCopse ? 'British Grand Prix' : isEauRouge ? 'Belgian Grand Prix' : 'Grand Prix');
  const sessionType = meta.session_type || 'Qualifying (Q3)';
  const drivers = meta.drivers && meta.drivers.length >= 2 ? meta.drivers : ['VER', 'NOR'];
  const compounds = meta.compounds && meta.compounds.length >= 2 ? meta.compounds : ['SOFT', 'SOFT'];

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-[#1E293B] bg-[#121824]/90 px-3.5 py-2 font-mono text-xs shadow-sm">
      {/* Event and Session */}
      <div className="flex items-center space-x-2">
        <Flag className="h-3.5 w-3.5 text-[#E10600]" />
        <span className="font-bold tracking-wider text-white">
          {year} {gpName.toUpperCase()}
        </span>
        <span className="rounded bg-[#1E293B] px-1.5 py-0.5 text-[10px] text-[#38BDF8]">
          {sessionType}
        </span>
      </div>

      {/* Corner / Lap Reference */}
      <div className="flex items-center space-x-1.5 text-[#94A3B8]">
        <Compass className="h-3.5 w-3.5 text-[#38BDF8]" />
        <span className="font-semibold text-[#F8FAFC]">{cornerName}</span>
      </div>

      {/* Driver Chips */}
      <div className="flex items-center space-x-2">
        <div className="flex items-center space-x-1 rounded bg-[#0B0F17] px-2 py-0.5 border border-[#3671C6]/40">
          <span className="h-2 w-2 rounded-full bg-[#3671C6]"></span>
          <span className="font-bold text-white">{drivers[0]}</span>
          <span className="rounded bg-[#EF4444]/20 px-1 text-[9px] font-bold text-[#EF4444]">
            {compounds[0]}
          </span>
        </div>
        <span className="text-[#64748B] font-bold">vs</span>
        <div className="flex items-center space-x-1 rounded bg-[#0B0F17] px-2 py-0.5 border border-[#FF8000]/40">
          <span className="h-2 w-2 rounded-full bg-[#FF8000]"></span>
          <span className="font-bold text-white">{drivers[1]}</span>
          <span className="rounded bg-[#EF4444]/20 px-1 text-[9px] font-bold text-[#EF4444]">
            {compounds[1]}
          </span>
        </div>
      </div>

      {/* Conditions */}
      <div className="flex items-center space-x-1 text-[#94A3B8]">
        <CloudSun className="h-3.5 w-3.5 text-amber-400" />
        <span className="text-[11px]">Track: DRY</span>
      </div>
    </div>
  );
}
