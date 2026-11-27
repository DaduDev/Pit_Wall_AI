import { Trophy, Database, CheckCircle2 } from 'lucide-react';
import { KpiCardData } from '../../types';

interface KpiCardProps {
  title?: string;
  card?: KpiCardData | null;
}

export function KpiCard({ title, card }: KpiCardProps) {
  if (!card) {
    return null;
  }

  const metrics = Array.isArray(card.metrics) ? card.metrics : [];

  return (
    <div className="rounded-lg border border-[#1E293B] bg-[#0E1420] p-6 shadow-xl space-y-6">
      {/* Header strip */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#1E293B] pb-4">
        <div className="flex items-center space-x-3">
          <div className="rounded-md border border-[#E10600]/30 bg-[#E10600]/10 p-2.5 text-[#E10600]">
            <Trophy className="h-5 w-5" />
          </div>
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#38BDF8] block">
              OFFICIAL TIMING • RESULT KPI CARD
            </span>
            <h2 className="text-lg font-bold text-white tracking-wide">
              {title || card.subtitle || 'Race Result Summary'}
            </h2>
            {card.subtitle && (
              <p className="text-xs font-mono text-[#94A3B8] mt-0.5">{card.subtitle}</p>
            )}
          </div>
        </div>

        <div className="flex items-center space-x-1.5 rounded-full border border-emerald-500/30 bg-emerald-950/40 px-3 py-1 text-xs font-mono text-emerald-400 self-start sm:self-auto">
          <Database className="h-3 w-3" />
          <span>DuckDB Verified</span>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
        {metrics.map((m, idx) => {
          const isPrimary =
            m.label.toLowerCase() === 'winner' ||
            m.label.toLowerCase().includes('margin') ||
            idx === 0;
          return (
            <div
              key={`${m.label}_${idx}`}
              className={`rounded-lg border p-4 transition-colors ${
                isPrimary
                  ? 'border-[#E10600]/40 bg-[#0B0F17]'
                  : 'border-[#1E293B] bg-[#0B0F17]/90'
              }`}
            >
              <span className="text-[10px] font-mono uppercase tracking-wider text-[#94A3B8] block mb-1.5">
                {m.label}
              </span>
              <span
                className={`text-lg font-bold font-mono tracking-tight block ${
                  isPrimary ? 'text-white' : 'text-[#E2E8F0]'
                }`}
              >
                {m.value}
              </span>
            </div>
          );
        })}
      </div>

      {/* Footer note */}
      <div className="flex items-center space-x-2 border-t border-[#1E293B] pt-3 text-[11px] font-mono text-[#64748B]">
        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
        <span>Deterministic single-record lookup • Inspect SQL provenance in Engineering Trace below.</span>
      </div>
    </div>
  );
}
