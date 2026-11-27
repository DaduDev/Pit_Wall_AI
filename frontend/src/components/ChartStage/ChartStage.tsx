import { Activity, BarChart2 } from 'lucide-react';
import { PlotlySpec, EngineeringTrace } from '../../types';
import { PlotlyChart } from './PlotlyChart';
import { TrackMiniMap } from './TrackMiniMap';
import { SectorSummaryBar } from './SectorSummaryBar';
import { WebIntelligenceCard } from './WebIntelligenceCard';
import { KpiCard } from './KpiCard';
import { DataTableCard } from './DataTableCard';
import { MetadataBar } from '../MetadataBar/MetadataBar';
import { TraceDrawer } from '../EngineeringTrace/TraceDrawer';
import { ErrorBoundary } from '../ErrorBoundary/ErrorBoundary';

interface ChartStageProps {
  chart: PlotlySpec | null;
  minimap?: PlotlySpec | null;
  trace: EngineeringTrace | null;
  onResetChart?: () => void;
}

export function ChartStage({ chart, minimap, trace, onResetChart }: ChartStageProps) {
  const vizType = chart?.viz_type || chart?.chart_type;

  const isWebCard =
    vizType === 'web_intelligence_card' ||
    chart?.chart_type === 'web_intelligence_card' ||
    !!chart?.web_intelligence_card;

  const isKpiCard =
    !isWebCard &&
    (vizType === 'kpi_card' || chart?.chart_type === 'kpi_card' || !!chart?.kpi_card);

  const isDataTable =
    !isWebCard &&
    !isKpiCard &&
    (vizType === 'data_table' || chart?.chart_type === 'data_table' || !!chart?.data_table);

  const isStructuredCard = isWebCard || isKpiCard || isDataTable;

  const webCardData =
    chart?.web_intelligence_card ||
    ((chart as any)?.web_card) ||
    (isWebCard ? (chart as any) : null);

  const hasValidPlotlyTraces = Array.isArray(chart?.data) && chart.data.length > 0;

  const rawDrivers = Array.isArray(chart?.metadata?.drivers) ? chart.metadata.drivers : [];
  const driverCodes = rawDrivers
    .map((d: any) => (typeof d === 'string' ? d : d?.code || ''))
    .filter(Boolean)
    .join('-');

  const chartKey = chart
    ? `${vizType || 'chart'}_${chart.metadata?.year || ''}_${chart.metadata?.grand_prix || ''}_${driverCodes}_${chart.layout?.title?.text || chart.title || ''}`
    : 'no_chart';

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

      {/* Metadata Bar for Active Chart (omitted for structured HUD cards/tables) */}
      {!isStructuredCard && (
        <ErrorBoundary fallbackTitle="Telemetry Metadata Render Error" onReset={onResetChart}>
          {chart && hasValidPlotlyTraces && <MetadataBar chart={chart} minimap={minimap || null} />}
        </ErrorBoundary>
      )}

      {/* Sector & Speed Trap Summary Bar for Full-Lap Overlays */}
      {!isStructuredCard && (
        <ErrorBoundary fallbackTitle="Sector Splits Summary Error" onReset={onResetChart}>
          {(vizType === 'full_lap' || chart?.chart_type === 'full_lap_comparison') && (
            <SectorSummaryBar chart={chart} />
          )}
        </ErrorBoundary>
      )}

      {/* Main visualization container */}
      <ErrorBoundary fallbackTitle="Telemetry Stage Error" onReset={onResetChart}>
        <div className="flex-1 min-h-[420px]">
          {chart ? (
            isWebCard ? (
              <WebIntelligenceCard card={webCardData} />
            ) : isKpiCard ? (
              <KpiCard title={chart.title} card={chart.kpi_card} />
            ) : isDataTable ? (
              <DataTableCard title={chart.title} table={chart.data_table} />
            ) : !hasValidPlotlyTraces ? (
              <div className="flex h-full flex-col items-center justify-center rounded-lg border border-[#1E293B] bg-[#0E1420] p-8 text-center text-[#94A3B8]">
                <Activity className="h-8 w-8 mb-2 text-[#38BDF8]" />
                <p className="font-mono text-xs text-white">
                  {chart.title || 'No Plottable Series Returned'}
                </p>
                <p className="mt-1 text-[11px] text-[#64748B] max-w-sm">
                  Numeric trace data was empty for this request. Review the Engineering Trace below for raw query details.
                </p>
              </div>
            ) : minimap ? (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                <div className="lg:col-span-2">
                  <PlotlyChart key={chartKey} spec={chart} />
                </div>
                <div className="lg:col-span-1">
                  <TrackMiniMap key={`mini_${chartKey}`} spec={minimap} />
                </div>
              </div>
            ) : (
              <div className="h-full w-full">
                <PlotlyChart key={chartKey} spec={chart} />
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
      </ErrorBoundary>

      {/* Collapsible Engineering Trace Drawer */}
      <TraceDrawer trace={trace} />
    </div>
  );
}
