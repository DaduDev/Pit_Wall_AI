import { Gauge, Layers, Timer, Trophy, ArrowUpRight } from 'lucide-react';

interface WelcomeHeroProps {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
}

const STARTER_CARDS = [
  {
    category: 'Corner Telemetry',
    title: 'Copse Entry & Exit Delta',
    prompt: 'Compare Verstappen and Norris through Copse at 2024 British GP Qualifying',
    icon: Gauge,
    accent: 'text-[#38BDF8] border-[#38BDF8]/30 bg-[#38BDF8]/10',
    hoverBorder: 'hover:border-[#38BDF8]/60',
  },
  {
    category: 'Full-Lap Overlay',
    title: 'Monza Qualifying Pace Map',
    prompt: 'Overlay Verstappen vs Norris full lap at 2024 Italian GP Qualifying',
    icon: Layers,
    accent: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
    hoverBorder: 'hover:border-emerald-500/60',
  },
  {
    category: 'Tyre Stints',
    title: 'Monza One-Stop vs Two-Stop',
    prompt: 'Compare Leclerc vs Piastri tyre degradation and stint strategy at 2024 Italian GP',
    icon: Timer,
    accent: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
    hoverBorder: 'hover:border-amber-500/60',
  },
  {
    category: 'Historical & Research',
    title: 'Race Results & Records',
    prompt: 'Who won the 2023 Bahrain Grand Prix?',
    icon: Trophy,
    accent: 'text-[#E10600] border-[#E10600]/30 bg-[#E10600]/10',
    hoverBorder: 'hover:border-[#E10600]/60',
  },
];

export function WelcomeHero({ onSelect, disabled }: WelcomeHeroProps) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-4 py-12">
      {/* PitWall Hero Identity */}
      <div className="mb-8 flex flex-col items-center text-center">
        <div className="mb-4 flex items-center space-x-2.5 rounded-full border border-[#1E293B] bg-[#121824] px-3.5 py-1.5 shadow-sm">
          <span className="flex h-5 w-5 items-center justify-center rounded bg-[#E10600] font-mono text-[10px] font-black text-white">
            F1
          </span>
          <span className="font-mono text-xs font-semibold tracking-wider text-[#E2E8F0]">
            PITWALL AI RACE ENGINEER
          </span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
          What are we analyzing on track today?
        </h1>
        <p className="mt-2.5 max-w-xl text-sm text-[#94A3B8] leading-relaxed">
          Deterministic Formula 1 analytics spanning 1950–2024+ DuckDB records, 2023+ OpenF1 car
          telemetry, tyre stint degradation, and grounded web intelligence.
        </p>
      </div>

      {/* 2x2 Starter Prompt Cards */}
      <div className="grid w-full grid-cols-1 sm:grid-cols-2 gap-3">
        {STARTER_CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <button
              key={card.prompt}
              type="button"
              disabled={disabled}
              onClick={() => onSelect(card.prompt)}
              className={`group flex flex-col justify-between rounded-xl border border-[#1E293B] bg-[#121824]/85 p-4 text-left transition-all hover:bg-[#161F30] ${card.hoverBorder} disabled:opacity-50`}
            >
              <div className="flex items-center justify-between mb-2.5">
                <div className="flex items-center space-x-2">
                  <span className={`rounded-md border p-1.5 ${card.accent}`}>
                    <Icon className="h-3.5 w-3.5" />
                  </span>
                  <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-[#CBD5E1]">
                    {card.category}
                  </span>
                </div>
                <ArrowUpRight className="h-3.5 w-3.5 text-[#64748B] transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-white" />
              </div>

              <div>
                <div className="text-xs font-semibold text-white mb-1">{card.title}</div>
                <p className="text-xs text-[#94A3B8] leading-relaxed line-clamp-2">
                  {card.prompt}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
