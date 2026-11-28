import { useState, useCallback, useRef } from 'react';
import { ChatMessage, EngineeringTrace, PlotlySpec } from '../types';

interface UseSSEStreamReturn {
  messages: ChatMessage[];
  isStreaming: boolean;
  sessionId: string | null;
  sendMessage: (text: string) => Promise<void>;
  resetChat: () => void;
}

function buildChartSpecFromSSE(data: any): {
  kind: 'chart' | 'minimap';
  spec: PlotlySpec;
  preserveMinimap: boolean;
} {
  const resolvedMeta = data.metadata || data.spec?.metadata || {};
  const resolvedVizType =
    data.viz_type || data.spec?.viz_type || data.chart_type || 'historical_sql';
  const resolvedTitle = data.title || data.spec?.title || data.caption;

  if (
    resolvedVizType === 'web_intelligence_card' ||
    data.chart_type === 'web_intelligence_card' ||
    !!data.web_intelligence_card ||
    !!data.spec?.web_intelligence_card
  ) {
    return {
      kind: 'chart',
      preserveMinimap: false,
      spec: {
        viz_type: 'web_intelligence_card',
        chart_type: 'web_intelligence_card',
        title: resolvedTitle,
        web_intelligence_card:
          data.web_intelligence_card ||
          data.spec?.web_intelligence_card ||
          data.spec?.web_card ||
          data.spec,
        metadata: resolvedMeta,
      },
    };
  }

  if (
    resolvedVizType === 'kpi_card' ||
    data.chart_type === 'kpi_card' ||
    !!data.kpi_card ||
    !!data.spec?.kpi_card
  ) {
    return {
      kind: 'chart',
      preserveMinimap: false,
      spec: {
        viz_type: 'kpi_card',
        chart_type: 'kpi_card',
        title: resolvedTitle,
        kpi_card: data.kpi_card || data.spec?.kpi_card,
        metadata: resolvedMeta,
      },
    };
  }

  if (
    resolvedVizType === 'data_table' ||
    data.chart_type === 'data_table' ||
    !!data.data_table ||
    !!data.spec?.data_table
  ) {
    return {
      kind: 'chart',
      preserveMinimap: false,
      spec: {
        viz_type: 'data_table',
        chart_type: 'data_table',
        title: resolvedTitle,
        data_table: data.data_table || data.spec?.data_table,
        metadata: resolvedMeta,
      },
    };
  }

  if (resolvedVizType === 'track_minimap' || data.chart_type === 'track_minimap') {
    const miniFig = data.figure || data.spec || {};
    return {
      kind: 'minimap',
      preserveMinimap: true,
      spec: {
        ...miniFig,
        viz_type: 'track_minimap',
        chart_type: 'track_minimap',
        metadata: resolvedMeta,
      },
    };
  }

  const figPayload = data.figure || data.spec || {};
  const isCorner =
    resolvedVizType === 'corner_telemetry' || data.chart_type === 'corner_comparison';
  return {
    kind: 'chart',
    preserveMinimap: isCorner,
    spec: {
      ...figPayload,
      viz_type: resolvedVizType,
      chart_type: data.chart_type,
      title: resolvedTitle,
      metadata: resolvedMeta,
    },
  };
}

function upsertAssistantMessage(
  prev: ChatMessage[],
  assistantMsgId: string,
  timestamp: string,
  updater: (existing: ChatMessage) => ChatMessage
): ChatMessage[] {
  const existing = prev.find((m) => m.id === assistantMsgId);
  if (existing) {
    return prev.map((m) => (m.id === assistantMsgId ? updater(m) : m));
  }
  const base: ChatMessage = {
    id: assistantMsgId,
    role: 'assistant',
    content: '',
    timestamp,
    isStreaming: true,
    status: null,
    chart: null,
    minimap: null,
    trace: null,
  };
  return [...prev, updater(base)];
}

export function useSSEStream(token?: string | null): UseSSEStreamReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const sessionGenerationRef = useRef(0);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      const gen = sessionGenerationRef.current;
      const nowTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const userMsg: ChatMessage = {
        id: `usr_${Date.now()}`,
        role: 'user',
        content: trimmed,
        timestamp: nowTime,
      };

      const assistantMsgId = `ast_${Date.now()}`;
      const assistantPlaceholder: ChatMessage = {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        timestamp: nowTime,
        isStreaming: true,
        status: 'Initializing connection to Pit Wall...',
        chart: null,
        minimap: null,
        trace: null,
      };

      setMessages((prev) => [...prev, userMsg, assistantPlaceholder]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortControllerRef.current = controller;
      let accumulatedText = '';

      try {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
        };
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        const res = await fetch('/api/chat/stream', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            message: trimmed,
            session_id: sessionId,
          }),
          signal: controller.signal,
        });

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: Failed to initiate stream`);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error('ReadableStream not available');

        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done || sessionGenerationRef.current !== gen) break;

          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split('\n\n');
          buffer = frames.pop() || '';

          for (const frame of frames) {
            if (!frame.trim() || sessionGenerationRef.current !== gen) continue;

            const lines = frame.split('\n');
            let eventType = 'message';
            let dataStr = '';

            for (const line of lines) {
              if (line.startsWith('event: ')) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith('data: ')) {
                dataStr = line.slice(6).trim();
              }
            }

            if (!dataStr) continue;

            try {
              const data = JSON.parse(dataStr);

              switch (eventType) {
                case 'session':
                  if (data.session_id) setSessionId(data.session_id);
                  break;

                case 'status': {
                  const statusText = data.detail || data.step || data.message || null;
                  setMessages((prev) =>
                    upsertAssistantMessage(prev, assistantMsgId, nowTime, (m) => ({
                      ...m,
                      status: m.content ? null : statusText,
                    }))
                  );
                  break;
                }

                case 'text':
                  if (data.delta) {
                    accumulatedText += data.delta;
                    setMessages((prev) =>
                      upsertAssistantMessage(prev, assistantMsgId, nowTime, (m) => ({
                        ...m,
                        content: accumulatedText,
                        status: null,
                        isStreaming: true,
                      }))
                    );
                  }
                  break;

                case 'chart':
                  if (
                    data &&
                    (data.viz_type ||
                      data.spec ||
                      data.figure ||
                      data.kpi_card ||
                      data.data_table ||
                      data.web_intelligence_card)
                  ) {
                    const parsed = buildChartSpecFromSSE(data);
                    setMessages((prev) =>
                      upsertAssistantMessage(prev, assistantMsgId, nowTime, (m) => {
                        if (parsed.kind === 'minimap') {
                          return { ...m, minimap: parsed.spec };
                        }
                        return {
                          ...m,
                          chart: parsed.spec,
                          minimap: parsed.preserveMinimap ? m.minimap ?? null : null,
                        };
                      })
                    );
                  }
                  break;

                case 'trace':
                  setMessages((prev) =>
                    upsertAssistantMessage(prev, assistantMsgId, nowTime, (m) => ({
                      ...m,
                      trace: data as EngineeringTrace,
                    }))
                  );
                  break;

                case 'error': {
                  const errorDetail = data.message || data.error || 'Unknown telemetry error';
                  accumulatedText +=
                    (accumulatedText ? '\n\n' : '') + `⚠️ **PitWall Error**: ${errorDetail}`;
                  setMessages((prev) =>
                    upsertAssistantMessage(prev, assistantMsgId, nowTime, (m) => ({
                      ...m,
                      content: accumulatedText,
                      status: null,
                      isStreaming: false,
                    }))
                  );
                  break;
                }

                case 'done':
                  setMessages((prev) =>
                    upsertAssistantMessage(prev, assistantMsgId, nowTime, (m) => ({
                      ...m,
                      content:
                        !m.content && !m.chart
                          ? '⚠️ **PitWall Notice**: Query completed with no telemetry commentary.'
                          : m.content,
                      status: null,
                      isStreaming: false,
                    }))
                  );
                  break;
              }
            } catch (jsonErr) {
              console.warn('Failed to parse SSE JSON chunk:', dataStr, jsonErr);
            }
          }
        }
      } catch (err: any) {
        if (err?.name === 'AbortError' || sessionGenerationRef.current !== gen) {
          return;
        }
        console.error('SSE streaming error:', err);
        accumulatedText +=
          (accumulatedText ? '\n\n' : '') +
          `⚠️ **PitWall Error**: ${err.message || 'Connection lost to PitWall server.'}`;
        setMessages((prev) =>
          upsertAssistantMessage(prev, assistantMsgId, nowTime, (m) => ({
            ...m,
            content: accumulatedText,
            status: null,
            isStreaming: false,
          }))
        );
      } finally {
        if (sessionGenerationRef.current === gen) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId ? { ...m, status: null, isStreaming: false } : m
            )
          );
          setIsStreaming(false);
          abortControllerRef.current = null;
        }
      }
    },
    [isStreaming, sessionId, token]
  );

  const resetChat = useCallback(() => {
    sessionGenerationRef.current += 1;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
    setMessages([]);
    setSessionId(null);
  }, []);

  return {
    messages,
    isStreaming,
    sessionId,
    sendMessage,
    resetChat,
  };
}
