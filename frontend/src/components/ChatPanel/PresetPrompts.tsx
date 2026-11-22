import { Zap, Gauge } from 'lucide-react';

interface PresetPromptsProps {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
}

const HISTORICAL_PRESETS = [
  'Who won the 2023 Bahrain Grand Prix?',
  'Show me Lewis Hamilton podium finishes per season',
  'Monza highest win percentage with >=5 starts',
  '2023 Drivers Championship standings top 10',
];

const TELEMETRY_PRESETS = [
  'Compare Verstappen and Norris through Copse at 2024 British GP Qualifying',
  'Compare Leclerc and Hamilton through Eau Rouge at 2023 Belgian GP Qualifying',
  'Compare Alonso and Piastri through 130R at 2024 Japanese GP Qualifying',
];

export function PresetPrompts({ onSelect, disabled }: PresetPromptsProps) {
  return (
    <div className="space-y-2 p-3 bg-[#0B0F17]/80 border-t border-[#1E293B]">
      {/* Corner Telemetry Presets */}
      <div>
        <div className="flex items-center space-x-1 text-[10px] font-mono uppercase tracking-wider text-[#38BDF8] mb-1">
          <Gauge className="h-3 w-3 text-[#38BDF8]" />
          <span>Corner Telemetry Comparisons (2018+)</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {TELEMETRY_PRESETS.map((query) => (
            <button
              key={query}
              disabled={disabled}
              onClick={() => onSelect(query)}
              className="rounded border border-[#1E293B] bg-[#121824] px-2.5 py-1 text-left text-xs font-mono text-[#E2E8F0] transition-colors hover:border-[#38BDF8] hover:text-white disabled:opacity-50"
            >
              {query}
            </button>
          ))}
        </div>
      </div>

      {/* Historical Presets */}
      <div>
        <div className="flex items-center space-x-1 text-[10px] font-mono uppercase tracking-wider text-[#94A3B8] mb-1">
          <Zap className="h-3 w-3 text-[#E10600]" />
          <span>Historical F1 Analytics (1950–2024+)</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {HISTORICAL_PRESETS.map((query) => (
            <button
              key={query}
              disabled={disabled}
              onClick={() => onSelect(query)}
              className="rounded border border-[#1E293B] bg-[#121824] px-2.5 py-1 text-left text-xs font-mono text-[#94A3B8] transition-colors hover:border-[#E10600] hover:text-white disabled:opacity-50"
            >
              {query}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
