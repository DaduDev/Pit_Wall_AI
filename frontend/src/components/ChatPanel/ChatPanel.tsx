import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, RotateCcw } from 'lucide-react';
import { ChatMessage } from '../../types';
import { MessageBubble } from './MessageBubble';
import { PresetPrompts } from './PresetPrompts';

interface ChatPanelProps {
  messages: ChatMessage[];
  currentStatus: string | null;
  isStreaming: boolean;
  onSendMessage: (text: string) => void;
  onReset: () => void;
}

export function ChatPanel({
  messages,
  currentStatus,
  isStreaming,
  onSendMessage,
  onReset,
}: ChatPanelProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentStatus]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    onSendMessage(input.trim());
    setInput('');
  };

  return (
    <div className="flex h-full flex-col bg-[#0B0F17]">
      {/* Panel Header */}
      <div className="flex h-11 items-center justify-between border-b border-[#1E293B] px-4 bg-[#121824]/50">
        <span className="text-xs font-mono tracking-wider text-[#94A3B8]">
          PITWALL COMMS (VOICE & DATA)
        </span>
        <button
          onClick={onReset}
          title="Reset telemetry session"
          className="rounded p-1 text-[#94A3B8] hover:bg-[#1E293B] hover:text-white transition-colors"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center p-6 text-[#94A3B8]">
            <div className="rounded-full bg-[#121824] p-3 border border-[#1E293B] mb-3">
              <span className="font-mono text-sm font-bold text-[#E10600]">AI-ENG</span>
            </div>
            <h3 className="font-mono text-sm text-white font-semibold">
              Race Engineer Ready
            </h3>
            <p className="mt-1 text-xs max-w-xs leading-relaxed">
              Ask historical Formula 1 questions (1950–2024+) or compare driver corner telemetry.
            </p>
          </div>
        ) : (
          messages.map((m) => <MessageBubble key={m.id} message={m} />)
        )}

        {/* Live streaming status badge */}
        {currentStatus && (
          <div className="flex items-center space-x-2 rounded-md border border-[#1E293B] bg-[#121824]/80 px-3 py-2 text-xs font-mono text-[#38BDF8] animate-pulse">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>{currentStatus}</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Preset Suggestions */}
      <PresetPrompts onSelect={onSendMessage} disabled={isStreaming} />

      {/* Chat Input */}
      <form
        onSubmit={handleSubmit}
        className="flex items-center space-x-2 border-t border-[#1E293B] bg-[#121824] p-3"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isStreaming}
          placeholder="Ask a race engineering question (e.g. 2023 Bahrain GP winner)..."
          className="flex-1 rounded-md border border-[#1E293B] bg-[#0B0F17] px-3.5 py-2 text-sm text-white placeholder-[#94A3B8] focus:border-[#E10600] focus:outline-none focus:ring-1 focus:ring-[#E10600] disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!input.trim() || isStreaming}
          className="rounded-md bg-[#E10600] p-2 text-white transition-colors hover:bg-[#B80500] disabled:opacity-50"
        >
          {isStreaming ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </button>
      </form>
    </div>
  );
}
