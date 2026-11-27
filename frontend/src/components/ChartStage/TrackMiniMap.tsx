import { useEffect, useMemo, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';
import { MapPin } from 'lucide-react';
import { PlotlySpec } from '../../types';

const Plot = createPlotlyComponent(Plotly);

interface TrackMiniMapProps {
  spec: PlotlySpec;
  expanded?: boolean;
}

export function TrackMiniMap({ spec, expanded = false }: TrackMiniMapProps) {
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
          // Ignore transient resize errors
        }
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const { plotData, layout, config } = useMemo(() => {
    const rawLayout = spec.layout || {};
    const { width: _ignoredWidth, ...restLayout } = rawLayout;
    return {
      plotData: Array.isArray(spec.data) ? spec.data : [],
      layout: {
        ...restLayout,
        paper_bgcolor: '#0B0F17',
        plot_bgcolor: '#0B0F17',
        autosize: true,
        yaxis: {
          ...(rawLayout.yaxis || {}),
          scaleanchor: 'x',
          scaleratio: 1,
          showticklabels: false,
          showgrid: false,
          zeroline: false,
        },
        xaxis: {
          ...(rawLayout.xaxis || {}),
          showticklabels: false,
          showgrid: false,
          zeroline: false,
        },
      },
      config: {
        responsive: true,
        displayModeBar: false,
        ...(spec.config || {}),
      },
    };
  }, [spec]);

  return (
    <div
      ref={wrapperRef}
      className={`flex flex-col rounded-lg border border-[#1E293B] bg-[#0B0F17] p-2.5 shadow-sm ${
        expanded ? 'h-full' : ''
      }`}
    >
      <div className="flex items-center space-x-1.5 border-b border-[#1E293B] pb-1.5 mb-1 px-1">
        <MapPin className="h-3.5 w-3.5 text-[#E10600]" />
        <span className="font-mono text-xs font-semibold text-white">
          GPS CORNER MINI-MAP
        </span>
      </div>
      <div className={expanded ? 'flex-1 min-h-[320px] w-full' : 'h-[320px] w-full'}>
        <Plot
          data={plotData}
          layout={layout}
          config={config}
          useResizeHandler={true}
          style={{ width: '100%', height: '100%' }}
          className="w-full h-full"
        />
      </div>
    </div>
  );
}
