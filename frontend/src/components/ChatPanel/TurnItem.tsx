import { Loader2 } from 'lucide-react';
import { ChatMessage } from '../../types';
import { ChartStage } from '../ChartStage/ChartStage';
import { MessageBubble } from './MessageBubble';
import { TraceDrawer } from '../EngineeringTrace/TraceDrawer';

interface TurnItemProps {
  message: ChatMessage;
}

export function TurnItem({ message }: TurnItemProps) {
  if (message.role === 'user') {
    return (
      <div className="flex w-full justify-end">
        <MessageBubble message={message} />
      </div>
    );
  }

  const showLiveStatus = Boolean(message.isStreaming && message.status && !message.content);
  const showProse = Boolean(message.content || message.isStreaming);

  return (
    <article className="w-full space-y-3">
      {/* 1) Live Status Pill (auto-hides once text content arrives) */}
      {showLiveStatus && (
        <div className="inline-flex items-center space-x-2 rounded-full border border-[#38BDF8]/30 bg-[#121824] px-3.5 py-1.5 text-xs font-mono text-[#38BDF8] shadow-sm">
          <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
          <span>{message.status}</span>
        </div>
      )}

      {/* 2) Visual Artifact on Top (Plotly chart, KpiCard, DataTableCard, WebIntelligenceCard) */}
      {message.chart && (
        <ChartStage chart={message.chart} minimap={message.minimap || null} />
      )}

      {/* 3) Race Engineer Text Below */}
      {showProse && <MessageBubble message={message} />}

      {/* 4) Collapsible Engineering Trace Bar */}
      {message.trace && <TraceDrawer trace={message.trace} />}
    </article>
  );
}
