import { Zap } from 'lucide-react';

interface PresetPromptsProps {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
}

const PRESET_QUERIES = [
  'Who won the 2023 Bahrain Grand Prix?',
  'Show me Lewis Hamilton podium finishes per season',
  '2023 Drivers Championship standings top 10',
  'Max Verstappen wins per season',
];

export function PresetPrompts({ onSelect, disabled }: PresetPromptsProps) {
  return (
    <div className="space-y-1.5 p-3 bg-[#0B0F17]/60 border-t border-[#1E293B]">
      <div className="flex items-center space-x-1 text-[10px] font-mono uppercase tracking-wider text-[#94A3B8]">
        <Zap className="h-3 w-3 text-[#E10600]" />
        <span>Quick Engineering Telemetry & Stats</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {PRESET_QUERIES.map((query) => (
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
  );
}
