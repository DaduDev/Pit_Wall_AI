import { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';
import { PlotlySpec } from '../../types';
import { MapPin } from 'lucide-react';

interface TrackMiniMapProps {
  spec: PlotlySpec;
}

export function TrackMiniMap({ spec }: TrackMiniMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !spec) return;

    const layout = {
      ...spec.layout,
      paper_bgcolor: '#0B0F17',
      plot_bgcolor: '#0B0F17',
      autosize: true,
      yaxis: {
        ...(spec.layout?.yaxis || {}),
        scaleanchor: 'x',
        scaleratio: 1,
        showticklabels: false,
        showgrid: false,
        zeroline: false,
      },
      xaxis: {
        ...(spec.layout?.xaxis || {}),
        showticklabels: false,
        showgrid: false,
        zeroline: false,
      },
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
    <div className="flex flex-col rounded-lg border border-[#1E293B] bg-[#0B0F17] p-2.5 shadow-sm">
      <div className="flex items-center space-x-1.5 border-b border-[#1E293B] pb-1.5 mb-1 px-1">
        <MapPin className="h-3.5 w-3.5 text-[#E10600]" />
        <span className="font-mono text-xs font-semibold text-white">
          GPS CORNER MINI-MAP
        </span>
      </div>
      <div ref={containerRef} className="h-[280px] w-full" />
    </div>
  );
}
