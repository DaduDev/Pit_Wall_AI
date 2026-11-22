import { useState, useCallback } from 'react';
import { ChatMessage, EngineeringTrace, PlotlySpec } from '../types';

interface UseSSEStreamReturn {
  messages: ChatMessage[];
  currentStatus: string | null;
  currentTrace: EngineeringTrace | null;
  currentChart: PlotlySpec | null;
  currentMinimap: PlotlySpec | null;
  isStreaming: boolean;
  sessionId: string | null;
  sendMessage: (text: string) => Promise<void>;
  resetChat: () => void;
}

export function useSSEStream(token?: string | null): UseSSEStreamReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentStatus, setCurrentStatus] = useState<string | null>(null);
  const [currentTrace, setCurrentTrace] = useState<EngineeringTrace | null>(null);
  const [currentChart, setCurrentChart] = useState<PlotlySpec | null>(null);
  const [currentMinimap, setCurrentMinimap] = useState<PlotlySpec | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isStreaming) return;

      const userMsg: ChatMessage = {
        id: `usr_${Date.now()}`,
        role: 'user',
        content: text.trim(),
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, userMsg]);
      setIsStreaming(true);
      setCurrentStatus('Initializing connection to Pit Wall...');

      const assistantMsgId = `ast_${Date.now()}`;
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
            message: text.trim(),
            session_id: sessionId,
          }),
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
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split('\n\n');
          buffer = frames.pop() || '';

          for (const frame of frames) {
            if (!frame.trim()) continue;

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

                case 'status':
                  setCurrentStatus(data.detail || data.step || data.message);
                  break;

                case 'text':
                  if (data.delta) {
                    accumulatedText += data.delta;
                    setMessages((prev) => {
                      const existing = prev.find((m) => m.id === assistantMsgId);
                      if (existing) {
                        return prev.map((m) =>
                          m.id === assistantMsgId
                            ? { ...m, content: accumulatedText, isStreaming: true }
                            : m
                        );
                      } else {
                        return [
                          ...prev,
                          {
                            id: assistantMsgId,
                            role: 'assistant',
                            content: accumulatedText,
                            timestamp: new Date().toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                            }),
                            isStreaming: true,
                          },
                        ];
                      }
                    });
                  }
                  break;

                case 'chart':
                  if (data.spec) {
                    if (data.chart_type === 'track_minimap') {
                      setCurrentMinimap({
                        ...data.spec,
                        chart_type: data.chart_type,
                        metadata: data.metadata,
                      });
                    } else {
                      setCurrentChart({
                        ...data.spec,
                        chart_type: data.chart_type,
                        metadata: data.metadata,
                      });
                      if (data.chart_type !== 'corner_comparison') {
                        setCurrentMinimap(null);
                      }
                    }
                  }
                  break;

                case 'trace':
                  setCurrentTrace(data);
                  break;

                case 'error':
                  setCurrentStatus(`Error: ${data.message || data.error}`);
                  break;

                case 'done':
                  setCurrentStatus(null);
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === assistantMsgId ? { ...m, isStreaming: false } : m
                    )
                  );
                  break;
              }
            } catch (jsonErr) {
              console.warn('Failed to parse SSE JSON chunk:', dataStr, jsonErr);
            }
          }
        }
      } catch (err: any) {
        console.error('SSE streaming error:', err);
        setMessages((prev) => [
          ...prev,
          {
            id: `err_${Date.now()}`,
            role: 'assistant',
            content: `Telemetry error: ${err.message || 'Connection lost to PitWall server.'}`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            isStreaming: false,
          },
        ]);
      } finally {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId ? { ...m, isStreaming: false } : m
          )
        );
        setIsStreaming(false);
        setCurrentStatus(null);
      }
    },
    [isStreaming, sessionId, token]
  );

  const resetChat = useCallback(() => {
    setMessages([]);
    setCurrentStatus(null);
    setCurrentTrace(null);
    setCurrentChart(null);
    setCurrentMinimap(null);
    setSessionId(null);
  }, []);

  return {
    messages,
    currentStatus,
    currentTrace,
    currentChart,
    currentMinimap,
    isStreaming,
    sessionId,
    sendMessage,
    resetChat,
  };
}
