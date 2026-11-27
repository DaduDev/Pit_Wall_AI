import { Zap, Gauge, Layers, Timer, X } from 'lucide-react';

interface PresetPromptsProps {
  onSelect: (prompt: string) => void;
  onClose?: () => void;
  disabled?: boolean;
}

const PRESET_GROUPS = [
  {
    label: 'Tyre Degradation & Strategy (2023+)',
    icon: Timer,
    iconColor: 'text-amber-400',
    hoverBorder: 'hover:border-amber-400',
    queries: [
      'Compare Leclerc vs Piastri tyre degradation and stint strategy at 2024 Italian GP',
      'Show tyre degradation and race pace for Leclerc at Monza 2024',
    ],
  },
  {
    label: 'Full-Lap Telemetry Overlays (2023+)',
    icon: Layers,
    iconColor: 'text-emerald-400',
    hoverBorder: 'hover:border-emerald-500',
    queries: [
      'Overlay Verstappen vs Norris full lap at 2024 Italian GP Qualifying',
      'Overlay Verstappen vs Leclerc full lap at 2024 Belgian GP Qualifying',
    ],
  },
  {
    label: 'Corner Telemetry Comparisons (2023+)',
    icon: Gauge,
    iconColor: 'text-[#38BDF8]',
    hoverBorder: 'hover:border-[#38BDF8]',
    queries: [
      'Compare Verstappen and Norris through Copse at 2024 British GP Qualifying',
      'Compare Leclerc and Hamilton through Eau Rouge at 2023 Belgian GP Qualifying',
      'Compare Alonso and Piastri through 130R at 2024 Japanese GP Qualifying',
    ],
  },
  {
    label: 'Historical F1 Analytics (1950–2024+)',
    icon: Zap,
    iconColor: 'text-[#E10600]',
    hoverBorder: 'hover:border-[#E10600]',
    queries: [
      'Who won the 2023 Bahrain Grand Prix?',
      'Show me Lewis Hamilton podium finishes per season',
      'Monza highest win percentage with >=5 starts',
      '2023 Drivers Championship standings top 10',
    ],
  },
];

export function PresetPrompts({ onSelect, onClose, disabled }: PresetPromptsProps) {
  return (
    <div className="w-full max-h-[60vh] overflow-y-auto rounded-xl border border-[#1E293B] bg-[#0E1420]/98 p-4 shadow-2xl backdrop-blur-md space-y-3">
      <div className="flex items-center justify-between border-b border-[#1E293B] pb-2">
        <div className="flex items-center space-x-2">
          <Zap className="h-3.5 w-3.5 text-[#E10600]" />
          <span className="font-mono text-xs font-semibold uppercase tracking-wider text-white">
            Quick Engineering Prompts
          </span>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close prompts menu"
            className="rounded p-1 text-[#94A3B8] hover:bg-[#1E293B] hover:text-white transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {PRESET_GROUPS.map((group) => {
        const Icon = group.icon;
        return (
          <div key={group.label}>
            <div className="flex items-center space-x-1.5 text-[10px] font-mono uppercase tracking-wider text-[#94A3B8] mb-1.5">
              <Icon className={`h-3 w-3 ${group.iconColor}`} />
              <span>{group.label}</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {group.queries.map((query) => (
                <button
                  key={query}
                  type="button"
                  disabled={disabled}
                  onClick={() => {
                    onSelect(query);
                    onClose?.();
                  }}
                  className={`rounded-md border border-[#1E293B] bg-[#121824] px-2.5 py-1.5 text-left text-xs font-mono text-[#E2E8F0] transition-colors ${group.hoverBorder} hover:text-white disabled:opacity-50`}
                >
                  {query}
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
