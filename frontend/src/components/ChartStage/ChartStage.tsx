import { useEffect, useState } from 'react';
import { Activity, Maximize2, X } from 'lucide-react';
import { PlotlySpec } from '../../types';
import { PlotlyChart } from './PlotlyChart';
import { TrackMiniMap } from './TrackMiniMap';
import { SectorSummaryBar } from './SectorSummaryBar';
import { WebIntelligenceCard } from './WebIntelligenceCard';
import { KpiCard } from './KpiCard';
import { DataTableCard } from './DataTableCard';
import { MetadataBar } from '../MetadataBar/MetadataBar';
import { ErrorBoundary } from '../ErrorBoundary/ErrorBoundary';

interface ChartStageProps {
  chart?: PlotlySpec | null;
  minimap?: PlotlySpec | null;
  onResetChart?: () => void;
}

export function ChartStage({ chart, minimap, onResetChart }: ChartStageProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    if (!isFullscreen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsFullscreen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isFullscreen]);

  if (!chart) {
    return null;
  }

  const vizType = chart.viz_type || chart.chart_type;

  const isWebCard =
    vizType === 'web_intelligence_card' ||
    chart.chart_type === 'web_intelligence_card' ||
    !!chart.web_intelligence_card;

  const isKpiCard =
    !isWebCard &&
    (vizType === 'kpi_card' || chart.chart_type === 'kpi_card' || !!chart.kpi_card);

  const isDataTable =
    !isWebCard &&
    !isKpiCard &&
    (vizType === 'data_table' || chart.chart_type === 'data_table' || !!chart.data_table);

  const isStructuredCard = isWebCard || isKpiCard || isDataTable;

  const webCardData =
    chart.web_intelligence_card ||
    (chart as any)?.web_card ||
    (isWebCard ? (chart as any) : null);

  const hasValidPlotlyTraces = Array.isArray(chart.data) && chart.data.length > 0;

  const rawDrivers = Array.isArray(chart.metadata?.drivers) ? chart.metadata.drivers : [];
  const driverCodes = rawDrivers
    .map((d: any) => (typeof d === 'string' ? d : d?.code || ''))
    .filter(Boolean)
    .join('-');

  const chartKey = `${vizType || 'chart'}_${chart.metadata?.year || ''}_${chart.metadata?.grand_prix || ''}_${driverCodes}_${chart.layout?.title?.text || chart.title || ''}`;

  const renderPlotlyVisual = (expanded: boolean) => {
    if (minimap) {
      return (
        <div
          className={`grid grid-cols-1 lg:grid-cols-3 gap-3 ${
            expanded ? 'h-full' : ''
          }`}
        >
          <div className={expanded ? 'lg:col-span-2 h-full' : 'lg:col-span-2'}>
            <PlotlyChart
              key={`${chartKey}_${expanded ? 'fs' : 'inline'}`}
              spec={chart}
              expanded={expanded}
            />
          </div>
          <div className={expanded ? 'lg:col-span-1 h-full' : 'lg:col-span-1'}>
            <TrackMiniMap
              key={`mini_${chartKey}_${expanded ? 'fs' : 'inline'}`}
              spec={minimap}
              expanded={expanded}
            />
          </div>
        </div>
      );
    }
    return (
      <div className={expanded ? 'h-full w-full' : 'w-full'}>
        <PlotlyChart
          key={`${chartKey}_${expanded ? 'fs' : 'inline'}`}
          spec={chart}
          expanded={expanded}
        />
      </div>
    );
  };

  return (
    <>
      <div className="w-full space-y-2.5">
        {/* Metadata Bar + Fullscreen Toggle for Plotly visualizations */}
        {!isStructuredCard && hasValidPlotlyTraces && (
          <ErrorBoundary fallbackTitle="Telemetry Metadata Render Error" onReset={onResetChart}>
            <div className="flex flex-col sm:flex-row sm:items-center gap-2">
              <div className="flex-1 min-w-0">
                <MetadataBar chart={chart} minimap={minimap || null} />
              </div>
              <button
                type="button"
                onClick={() => setIsFullscreen(true)}
                title="Expand telemetry chart to fullscreen"
                className="inline-flex items-center justify-center space-x-1.5 shrink-0 rounded-md border border-[#1E293B] bg-[#121824] px-3 py-2 text-xs font-mono text-[#CBD5E1] hover:border-[#38BDF8]/60 hover:bg-[#1A2234] hover:text-white transition-colors"
              >
                <Maximize2 className="h-3.5 w-3.5 text-[#38BDF8]" />
                <span>Expand</span>
              </button>
            </div>
          </ErrorBoundary>
        )}

        {/* Sector & Speed Trap Summary Bar for Full-Lap Overlays */}
        {!isStructuredCard &&
          (vizType === 'full_lap' || chart.chart_type === 'full_lap_comparison') && (
            <ErrorBoundary fallbackTitle="Sector Splits Summary Error" onReset={onResetChart}>
              <SectorSummaryBar chart={chart} />
            </ErrorBoundary>
          )}

        {/* Visual Artifact Container */}
        <ErrorBoundary fallbackTitle="Telemetry Stage Error" onReset={onResetChart}>
          <div className="w-full">
            {isWebCard ? (
              <WebIntelligenceCard card={webCardData} />
            ) : isKpiCard ? (
              <KpiCard title={chart.title} card={chart.kpi_card} />
            ) : isDataTable ? (
              <DataTableCard title={chart.title} table={chart.data_table} />
            ) : !hasValidPlotlyTraces ? (
              <div className="flex flex-col items-center justify-center rounded-lg border border-[#1E293B] bg-[#0E1420] p-6 text-center text-[#94A3B8]">
                <Activity className="h-7 w-7 mb-2 text-[#38BDF8]" />
                <p className="font-mono text-xs text-white">
                  {chart.title || 'No Plottable Series Returned'}
                </p>
                <p className="mt-1 text-[11px] text-[#64748B] max-w-md">
                  Numeric trace data was empty for this request. See the Race Engineer summary below for details.
                </p>
              </div>
            ) : (
              renderPlotlyVisual(false)
            )}
          </div>
        </ErrorBoundary>
      </div>

      {/* Fullscreen Modal for Interactive Telemetry Inspection */}
      {isFullscreen && hasValidPlotlyTraces && !isStructuredCard && (
        <div
          className="fixed inset-0 z-50 flex flex-col bg-[#0B0F17]/95 backdrop-blur-md p-4 sm:p-6 space-y-3"
          role="dialog"
          aria-modal="true"
          aria-label="Expanded Telemetry Visualization"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex-1 min-w-0">
              <MetadataBar chart={chart} minimap={minimap || null} />
            </div>
            <button
              type="button"
              onClick={() => setIsFullscreen(false)}
              className="inline-flex items-center space-x-1.5 shrink-0 rounded-md border border-[#1E293B] bg-[#121824] px-3 py-2 text-xs font-mono text-white hover:border-[#E10600] hover:bg-[#1E293B] transition-colors"
            >
              <X className="h-4 w-4 text-[#E10600]" />
              <span>Close</span>
            </button>
          </div>
          <div className="flex-1 min-h-0 overflow-hidden">
            {renderPlotlyVisual(true)}
          </div>
        </div>
      )}
    </>
  );
}
