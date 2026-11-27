import { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Terminal,
  Clock,
  ArrowRight,
  Layers,
  ExternalLink,
} from 'lucide-react';
import { EngineeringTrace } from '../../types';

interface TraceDrawerProps {
  trace?: EngineeringTrace | null;
}

export function TraceDrawer({ trace }: TraceDrawerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!trace) {
    return null;
  }

  const hops = trace.a2a_hops || [];
  const groundingSources = trace.grounding_sources || [];

  const isTelemetry =
    trace.data_domain === 'telemetry' ||
    !!trace.telemetry_params ||
    !!(trace as any).strategy_params;
  const isResearch = trace.data_domain === 'research' || groundingSources.length > 0;
  const params = trace.telemetry_params || (trace as any).strategy_params;

  const handleCopy = () => {
    const textToCopy = trace.query || (params ? JSON.stringify(params, null, 2) : '');
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const getProviderShortTag = () => {
    if (trace.provider) return trace.provider;
    if (isResearch) return 'gemini';
    if (isTelemetry) return 'openf1';
    return 'duckdb';
  };

  const getProviderLabel = () => {
    if (trace.provider === 'ollama_fallback') return 'Ollama Fallback (qwen3.5)';
    if (trace.provider === 'cache') return isResearch ? 'Research Disk Cache' : 'Persistent Cache';
    if (trace.provider === 'gemini') {
      if (isResearch) return 'Gemini Search Grounding';
      if (isTelemetry) return 'OpenF1 + Gemini';
      return 'DuckDB + Gemini';
    }
    if (isResearch) return 'Gemini Search Grounding';
    if (isTelemetry) return 'OpenF1 REST API';
    return 'DuckDB Read-Only';
  };

  const providerTag = getProviderShortTag();
  const providerColorClass =
    providerTag === 'ollama_fallback'
      ? 'border-amber-500/30 bg-amber-950/30 text-amber-400'
      : providerTag === 'cache'
      ? 'border-cyan-500/30 bg-cyan-950/30 text-cyan-400'
      : 'border-emerald-500/30 bg-emerald-950/30 text-emerald-400';

  return (
    <div className="rounded-lg border border-[#1E293B] bg-[#121824]/90 shadow-sm">
      {/* Compact single-line toggle bar */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full items-center justify-between gap-2 px-3.5 py-2 text-xs font-mono text-[#94A3B8] hover:bg-[#1A2234] transition-colors rounded-lg"
      >
        <div className="flex flex-wrap items-center gap-2 min-w-0">
          <Terminal className="h-3.5 w-3.5 text-[#E10600] shrink-0" />
          <span className="font-semibold text-[#E2E8F0] uppercase tracking-wider text-[11px]">
            Engineering Trace
          </span>
          <span className="rounded bg-[#1E293B] px-1.5 py-0.5 text-[10px] text-emerald-400">
            {trace.data_domain.toUpperCase()}
          </span>
          {hops.length > 0 && (
            <span className="inline-flex items-center space-x-1 rounded border border-[#1E293B] bg-[#0B0F17] px-1.5 py-0.5 text-[10px] text-[#CBD5E1]">
              <Layers className="h-2.5 w-2.5 text-cyan-400" />
              <span>
                {hops.length} {hops.length === 1 ? 'hop' : 'hops'}
              </span>
            </span>
          )}
          <span className={`rounded border px-1.5 py-0.5 text-[10px] ${providerColorClass}`}>
            {providerTag}
          </span>
        </div>

        <div className="flex items-center space-x-2.5 shrink-0">
          {trace.execution_time_ms !== undefined && (
            <span className="flex items-center space-x-1 text-[11px] text-[#94A3B8]">
              <Clock className="h-3 w-3" />
              <span>{trace.execution_time_ms} ms</span>
            </span>
          )}
          {isOpen ? (
            <ChevronUp className="h-4 w-4 text-[#94A3B8]" />
          ) : (
            <ChevronDown className="h-4 w-4 text-[#94A3B8]" />
          )}
        </div>
      </button>

      {isOpen && (
        <div className="border-t border-[#1E293B] p-4 space-y-3 font-mono text-xs">
          {/* Metadata badges */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
              <span className="text-[10px] text-[#64748B] block">DATA DOMAIN</span>
              <span className="text-white font-medium">{trace.data_domain}</span>
            </div>
            <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
              <span className="text-[10px] text-[#64748B] block">
                {isResearch ? 'SOURCES' : isTelemetry ? 'SAMPLES / ROWS' : 'ROW COUNT'}
              </span>
              <span className="text-white font-medium">
                {isResearch
                  ? groundingSources.length
                  : trace.row_count !== undefined
                  ? trace.row_count
                  : params?.clean_lap_counts
                  ? (Object.values(params.clean_lap_counts) as number[]).reduce(
                      (a: number, b: number) => a + b,
                      0
                    )
                  : trace.interpolated_points !== undefined
                  ? trace.interpolated_points
                  : 'N/A'}
              </span>
            </div>
            <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
              <span className="text-[10px] text-[#64748B] block">CONFIDENCE</span>
              <span className="text-emerald-400 font-medium">
                {(trace.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
              <span className="text-[10px] text-[#64748B] block">PROVIDER</span>
              <span
                className={`font-medium ${
                  trace.provider === 'ollama_fallback'
                    ? 'text-amber-400'
                    : trace.provider === 'cache'
                    ? 'text-cyan-400'
                    : 'text-white'
                }`}
              >
                {getProviderLabel()}
              </span>
            </div>
          </div>

          {/* A2A Multi-Agent Hop Trace */}
          {hops.length > 0 && (
            <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-3 space-y-2">
              <div className="flex items-center justify-between border-b border-[#1E293B] pb-1.5">
                <div className="flex items-center space-x-2 text-cyan-400">
                  <Layers className="h-3.5 w-3.5" />
                  <span className="font-semibold text-white uppercase tracking-wider text-[11px]">
                    A2A Specialist Hop Trace ({hops.length} hops)
                  </span>
                </div>
                <span className="text-[10px] text-[#64748B]">Google ADK + A2A Routing</span>
              </div>

              {/* Hop Sequence Breadcrumbs */}
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className="rounded bg-[#1E293B] px-2 py-1 text-[11px] font-semibold text-white">
                  PitWallEngineer
                </span>
                {hops.map((hop, idx) => (
                  <div key={idx} className="flex items-center space-x-1.5">
                    <ArrowRight className="h-3 w-3 text-[#64748B]" />
                    <div
                      className={`flex items-center space-x-1.5 rounded border px-2 py-1 text-[11px] ${
                        hop.status === 'success'
                          ? 'border-emerald-500/30 bg-[#121824] text-emerald-400'
                          : 'border-rose-500/30 bg-rose-950/30 text-rose-400'
                      }`}
                    >
                      <span className="font-semibold">{hop.agent_name}</span>
                      <span className="text-[10px] text-[#64748B]">({hop.duration_ms}ms)</span>
                      {hop.dataset_id && (
                        <span className="rounded bg-[#0B0F17] px-1 py-0.2 text-[9px] text-cyan-300 font-mono">
                          {hop.dataset_id.slice(0, 8)}…
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Dataset ID if present */}
              {trace.dataset_id && (
                <div className="flex items-center justify-between pt-1 text-[10px] text-[#64748B] border-t border-[#1E293B]/40">
                  <span>ARTIFACT DATASET ID:</span>
                  <span className="font-mono text-cyan-400">{trace.dataset_id}</span>
                </div>
              )}
            </div>
          )}

          {/* Telemetry provenance badges */}
          {params && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 border-t border-[#1E293B]/60">
              {params.session_key && (
                <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
                  <span className="text-[10px] text-[#64748B] block">SESSION KEY</span>
                  <span className="text-cyan-400 font-medium">#{params.session_key}</span>
                </div>
              )}
              {params.interpolation_method && (
                <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
                  <span className="text-[10px] text-[#64748B] block">INTERPOLATION</span>
                  <span className="text-[#E2E8F0] font-medium">{params.interpolation_method}</span>
                </div>
              )}
              {params.lap_numbers && (
                <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
                  <span className="text-[10px] text-[#64748B] block">DRIVER LAPS</span>
                  <span className="text-emerald-400 font-medium">
                    {Array.isArray(params.lap_numbers)
                      ? params.lap_numbers.join(' | ')
                      : Object.entries(params.lap_numbers)
                          .map(([d, l]) => `${d}: L${l}`)
                          .join(' | ')}
                  </span>
                </div>
              )}
              {params.sector_boundaries_m && (
                <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
                  <span className="text-[10px] text-[#64748B] block">SECTORS</span>
                  <span className="text-amber-400 font-medium">
                    S1: {Math.round(params.sector_boundaries_m[0])}m | S2:{' '}
                    {Math.round(params.sector_boundaries_m[1])}m
                  </span>
                </div>
              )}
              {params.stint_counts && (
                <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
                  <span className="text-[10px] text-[#64748B] block">STINTS</span>
                  <span className="text-emerald-400 font-medium">
                    {Object.entries(params.stint_counts)
                      .map(([d, s]) => `${d}: ${s}S`)
                      .join(' | ')}
                  </span>
                </div>
              )}
              {params.clean_lap_counts && (
                <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
                  <span className="text-[10px] text-[#64748B] block">CLEAN LAPS</span>
                  <span className="text-amber-400 font-medium">
                    {Object.entries(params.clean_lap_counts)
                      .map(([d, c]) => {
                        const out = params.excluded_lap_counts
                          ? params.excluded_lap_counts[d]
                          : undefined;
                        return out !== undefined ? `${d}: ${c}L (${out} filtered)` : `${d}: ${c}L`;
                      })
                      .join(' | ')}
                  </span>
                </div>
              )}
              {params.pit_stop_laps && (
                <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
                  <span className="text-[10px] text-[#64748B] block">PIT LAPS</span>
                  <span className="text-rose-400 font-medium">
                    {Object.entries(params.pit_stop_laps)
                      .map(([d, p]) => `${d}: L${(p as number[]).join(',')}`)
                      .join(' | ')}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Grounding Sources (for Research inquiries) */}
          {groundingSources.length > 0 && (
            <div className="space-y-2 pt-1 border-t border-[#1E293B]/60">
              <div className="flex items-center justify-between text-[#94A3B8]">
                <span className="text-[10px] uppercase tracking-wider text-[#64748B]">
                  Google Search Grounding Sources ({groundingSources.length}):
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                {groundingSources.map((src, idx) => (
                  <a
                    key={idx}
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between rounded border border-[#1E293B] bg-[#0B0F17] px-2.5 py-1.5 text-[11px] text-[#94A3B8] hover:text-white hover:border-cyan-500/50 transition-colors"
                  >
                    <span className="truncate pr-2">{src.title || src.url}</span>
                    <ExternalLink className="h-3 w-3 shrink-0 text-cyan-400" />
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Exact SQL Query or Telemetry Parameters */}
          {trace.query ? (
            <div>
              <div className="flex items-center justify-between pb-1 text-[#94A3B8]">
                <span className="text-[10px] uppercase tracking-wider text-[#64748B]">
                  Exact Ground-Truth SQL Statement:
                </span>
                <button
                  type="button"
                  onClick={handleCopy}
                  className="flex items-center space-x-1 text-[11px] hover:text-white transition-colors"
                >
                  {copied ? (
                    <Check className="h-3 w-3 text-emerald-400" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                  <span>{copied ? 'Copied' : 'Copy SQL'}</span>
                </button>
              </div>
              <pre className="overflow-x-auto rounded bg-[#0B0F17] p-3 text-[11px] text-emerald-400 border border-[#1E293B] leading-relaxed whitespace-pre-wrap">
                {trace.query}
              </pre>
            </div>
          ) : params ? (
            <div>
              <div className="flex items-center justify-between pb-1 text-[#94A3B8]">
                <span className="text-[10px] uppercase tracking-wider text-[#64748B]">
                  {trace.strategy_params || (params && params.stint_counts)
                    ? 'Ground-Truth Tyre Stint & Strategy Parameters:'
                    : 'Ground-Truth Telemetry Trace Parameters:'}
                </span>
                <button
                  type="button"
                  onClick={handleCopy}
                  className="flex items-center space-x-1 text-[11px] hover:text-white transition-colors"
                >
                  {copied ? (
                    <Check className="h-3 w-3 text-emerald-400" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                  <span>{copied ? 'Copied' : 'Copy Parameters'}</span>
                </button>
              </div>
              <pre className="overflow-x-auto rounded bg-[#0B0F17] p-3 text-[11px] text-cyan-300 border border-[#1E293B] leading-relaxed whitespace-pre-wrap">
                {JSON.stringify(params, null, 2)}
              </pre>
            </div>
          ) : null}

          {trace.notes && (
            <p className="text-[11px] text-[#94A3B8] italic">Note: {trace.notes}</p>
          )}
        </div>
      )}
    </div>
  );
}
