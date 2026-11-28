import { useEffect, useMemo, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';
import { PlotlySpec } from '../../types';

const Plot = createPlotlyComponent(Plotly);

interface PlotlyChartProps {
  spec: PlotlySpec;
  expanded?: boolean;
}

export function PlotlyChart({ spec, expanded = false }: PlotlyChartProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = wrapperRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => {
      const plotEl = el.querySelector('.js-plotly-plot') as HTMLElement | null;
      if (plotEl) {
        try {
          Plotly.Plots.resize(plotEl);
        } catch {
          // Ignore transient resize errors before initial plot mount
        }
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const { plotData, layout, config } = useMemo(() => {
    const isFullLap =
      spec.chart_type === 'full_lap_comparison' || spec.viz_type === 'full_lap';
    const rawLayout = spec.layout || {};
    const { width: _ignoredWidth, height: rawHeight, ...restLayout } = rawLayout;

    const computedLayout: Record<string, any> = {
      ...restLayout,
      paper_bgcolor: '#0B0F17',
      plot_bgcolor: '#0B0F17',
      autosize: true,
      height: expanded ? undefined : rawHeight || 440,
      hovermode: isFullLap ? 'x unified' : rawLayout.hovermode || 'closest',
    };

    const computedConfig: Record<string, any> = {
      responsive: true,
      displayModeBar: 'hover',
      modeBarButtonsToRemove: ['lasso2d', 'select2d'],
      displaylogo: false,
      scrollZoom: isFullLap || expanded,
      ...(spec.config || {}),
    };

    return {
      plotData: Array.isArray(spec.data) ? spec.data : [],
      layout: computedLayout,
      config: computedConfig,
    };
  }, [spec, expanded]);

  return (
    <div
      ref={wrapperRef}
      className={`relative w-full rounded-lg border border-[#1E293B] bg-[#0B0F17] p-2 ${
        expanded ? 'h-full min-h-[500px]' : 'min-h-[380px]'
      }`}
    >
      <Plot
        data={plotData}
        layout={layout}
        config={config}
        useResizeHandler={true}
        style={{ width: '100%', height: expanded ? '100%' : undefined }}
        className="w-full h-full"
      />
    </div>
  );
}
