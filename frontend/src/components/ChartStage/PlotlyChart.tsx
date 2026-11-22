import { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';
import { PlotlySpec } from '../../types';

interface PlotlyChartProps {
  spec: PlotlySpec;
}

export function PlotlyChart({ spec }: PlotlyChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !spec) return;

    // Ensure layout uses dark HUD background #0B0F17
    const layout = {
      ...spec.layout,
      paper_bgcolor: '#0B0F17',
      plot_bgcolor: '#0B0F17',
      autosize: true,
    };

    const config = {
      responsive: true,
      displayModeBar: false,
      ...(spec.config || {}),
    };

    Plotly.newPlot(containerRef.current, spec.data, layout, config);

    const handleResize = () => {
      if (containerRef.current) {
        Plotly.Plots.resize(containerRef.current);
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (containerRef.current) {
        Plotly.purge(containerRef.current);
      }
    };
  }, [spec]);

  return (
    <div className="relative h-full w-full rounded-lg border border-[#1E293B] bg-[#0B0F17] p-2">
      <div ref={containerRef} className="h-full w-full min-h-[350px]" />
    </div>
  );
}
