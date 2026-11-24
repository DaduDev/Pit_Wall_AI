import { useState } from 'react';
import { ChevronDown, ChevronUp, Copy, Check, Terminal, Clock } from 'lucide-react';
import { EngineeringTrace } from '../../types';

interface TraceDrawerProps {
  trace: EngineeringTrace | null;
}

export function TraceDrawer({ trace }: TraceDrawerProps) {
  const [isOpen, setIsOpen] = useState(true);
  const [copied, setCopied] = useState(false);

  if (!trace) {
    return null;
  }

  const isTelemetry = trace.data_domain === 'telemetry' || !!trace.telemetry_params;
  const params = trace.telemetry_params;

  const handleCopy = () => {
    const textToCopy = trace.query || (params ? JSON.stringify(params, null, 2) : '');
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="rounded-lg border border-[#1E293B] bg-[#121824] shadow-lg">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-xs font-mono text-[#94A3B8] hover:bg-[#1A2234] transition-colors rounded-t-lg"
      >
        <div className="flex items-center space-x-2">
          <Terminal className="h-3.5 w-3.5 text-[#E10600]" />
          <span className="font-semibold text-white uppercase tracking-wider">
            Engineering Trace & Provenance
          </span>
          <span className="rounded bg-[#1E293B] px-1.5 py-0.5 text-[10px] text-emerald-400">
            {trace.data_domain.toUpperCase()}
          </span>
        </div>
        <div className="flex items-center space-x-3">
          {trace.execution_time_ms !== undefined && (
            <span className="flex items-center space-x-1 text-[11px] text-[#94A3B8]">
              <Clock className="h-3 w-3" />
              <span>{trace.execution_time_ms} ms</span>
            </span>
          )}
          {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
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
                {isTelemetry ? 'SAMPLES / ROWS' : 'ROW COUNT'}
              </span>
              <span className="text-white font-medium">{trace.row_count ?? 'N/A'}</span>
            </div>
            <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
              <span className="text-[10px] text-[#64748B] block">CONFIDENCE</span>
              <span className="text-emerald-400 font-medium">{(trace.confidence * 100).toFixed(0)}%</span>
            </div>
            <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
              <span className="text-[10px] text-[#64748B] block">PROVIDER</span>
              <span className="text-white font-medium">
                {isTelemetry ? 'OpenF1 REST API' : 'DuckDB Read-Only'}
              </span>
            </div>
          </div>

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
                      : Object.entries(params.lap_numbers).map(([d, l]) => `${d}: L${l}`).join(' | ')}
                  </span>
                </div>
              )}
              {params.sector_boundaries_m && (
                <div className="rounded border border-[#1E293B] bg-[#0B0F17] p-2">
                  <span className="text-[10px] text-[#64748B] block">SECTORS</span>
                  <span className="text-amber-400 font-medium">
                    S1: {Math.round(params.sector_boundaries_m[0])}m | S2: {Math.round(params.sector_boundaries_m[1])}m
                  </span>
                </div>
              )}
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
                  onClick={handleCopy}
                  className="flex items-center space-x-1 text-[11px] hover:text-white transition-colors"
                >
                  {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
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
                  Ground-Truth Telemetry Trace Parameters:
                </span>
                <button
                  onClick={handleCopy}
                  className="flex items-center space-x-1 text-[11px] hover:text-white transition-colors"
                >
                  {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                  <span>{copied ? 'Copied' : 'Copy Parameters'}</span>
                </button>
              </div>
              <pre className="overflow-x-auto rounded bg-[#0B0F17] p-3 text-[11px] text-cyan-300 border border-[#1E293B] leading-relaxed whitespace-pre-wrap">
                {JSON.stringify(params, null, 2)}
              </pre>
            </div>
          ) : null}

          {trace.notes && (
            <p className="text-[11px] text-[#94A3B8] italic">
              Note: {trace.notes}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
