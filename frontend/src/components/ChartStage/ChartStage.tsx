import { Activity, BarChart2 } from 'lucide-react';
import { PlotlySpec, EngineeringTrace } from '../../types';
import { PlotlyChart } from './PlotlyChart';
import { TrackMiniMap } from './TrackMiniMap';
import { SectorSummaryBar } from './SectorSummaryBar';
import { MetadataBar } from '../MetadataBar/MetadataBar';
import { TraceDrawer } from '../EngineeringTrace/TraceDrawer';

interface ChartStageProps {
  chart: PlotlySpec | null;
  minimap?: PlotlySpec | null;
  trace: EngineeringTrace | null;
}

export function ChartStage({ chart, minimap, trace }: ChartStageProps) {
  const isTelemetry =
    chart?.chart_type === 'corner_comparison' ||
    chart?.chart_type === 'full_lap_comparison' ||
    Boolean(minimap);

  return (
    <div className="flex h-full flex-col bg-[#0B0F17] p-4 overflow-y-auto space-y-3">
      {/* Top stage header */}
      <div className="flex h-10 items-center justify-between border-b border-[#1E293B] pb-2">
        <div className="flex items-center space-x-2">
          <BarChart2 className="h-4 w-4 text-[#E10600]" />
          <h2 className="font-mono text-xs uppercase tracking-wider text-white">
            Telemetry & Visual Analytics Stage
          </h2>
        </div>
        <div className="text-[11px] font-mono text-[#94A3B8]">
          HUD STANDARD: #0B0F17 • ZERO-HALLUCINATION
        </div>
      </div>

      {/* Metadata Bar for Telemetry Sessions */}
      {isTelemetry && <MetadataBar chart={chart} minimap={minimap || null} />}

      {/* Sector & Speed Trap Summary Bar for Full-Lap Overlays */}
      {chart?.chart_type === 'full_lap_comparison' && <SectorSummaryBar chart={chart} />}

      {/* Main visualization container */}
      <div className="flex-1 min-h-[420px]">
        {chart ? (
          minimap ? (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <div className="lg:col-span-2">
                <PlotlyChart spec={chart} />
              </div>
              <div className="lg:col-span-1">
                <TrackMiniMap spec={minimap} />
              </div>
            </div>
          ) : (
            <div className="h-full w-full">
              <PlotlyChart spec={chart} />
            </div>
          )
        ) : (
          <div className="flex h-full flex-col items-center justify-center text-center p-8 text-[#64748B]">
            <Activity className="h-10 w-10 mb-3 text-[#1E293B]" />
            <p className="font-mono text-xs text-[#94A3B8]">
              Awaiting query execution...
            </p>
            <p className="mt-1 text-[11px] max-w-sm">
              Select a preset prompt or ask a Formula 1 question to render interactive Plotly charts, synchronized telemetry panels, and GPS track maps.
            </p>
          </div>
        )}
      </div>

      {/* Collapsible Engineering Trace Drawer */}
      <TraceDrawer trace={trace} />
    </div>
  );
}
