import React, { useEffect, useRef, useState } from 'react';
import { Loader2, Mic, Send, Zap } from 'lucide-react';
import { PresetPrompts } from './PresetPrompts';

interface ComposerBarProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export function ComposerBar({ onSend, disabled }: ComposerBarProps) {
  const [input, setInput] = useState('');
  const [showPrompts, setShowPrompts] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-grow textarea height smoothly up to 140px
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [input]);

  // Close Quick-Prompts popover on outside click or Escape
  useEffect(() => {
    if (!showPrompts) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowPrompts(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowPrompts(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [showPrompts]);

  const submitQuery = () => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setInput('');
    setShowPrompts(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    submitQuery();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitQuery();
    }
  };

  return (
    <div
      ref={containerRef}
      className="pointer-events-none fixed inset-x-0 bottom-0 z-30 bg-gradient-to-t from-[#0B0F17] via-[#0B0F17]/95 to-transparent px-4 pb-4 pt-6"
    >
      <div className="pointer-events-auto relative mx-auto w-full max-w-3xl">
        {/* Compact Quick-Prompts Popover */}
        {showPrompts && (
          <div className="absolute bottom-full left-0 right-0 mb-2.5 z-40">
            <PresetPrompts
              onSelect={(prompt) => {
                onSend(prompt);
                setShowPrompts(false);
              }}
              onClose={() => setShowPrompts(false)}
              disabled={disabled}
            />
          </div>
        )}

        {/* Floating Dark Pill Composer */}
        <form
          onSubmit={handleSubmit}
          className="flex items-end gap-2 rounded-2xl border border-[#1E293B] bg-[#121824]/95 px-3 py-2 shadow-2xl backdrop-blur-md focus-within:border-[#38BDF8]/60 transition-colors"
        >
          {/* Compact Quick-Prompts Toggle Button */}
          <button
            type="button"
            onClick={() => setShowPrompts((prev) => !prev)}
            disabled={disabled}
            title="Quick engineering prompts"
            aria-expanded={showPrompts}
            className={`mb-0.5 inline-flex items-center space-x-1.5 rounded-xl border px-2.5 py-2 text-xs font-mono transition-colors shrink-0 disabled:opacity-50 ${
              showPrompts
                ? 'border-[#E10600]/60 bg-[#E10600]/15 text-white'
                : 'border-[#1E293B] bg-[#0B0F17] text-[#CBD5E1] hover:border-[#38BDF8]/50 hover:text-white'
            }`}
          >
            <Zap className="h-3.5 w-3.5 text-[#E10600]" />
            <span className="hidden sm:inline">Prompts</span>
          </button>

          {/* Auto-Growing Textarea */}
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Ask PitWall AI about race results, corner telemetry, or strategy..."
            className="max-h-[140px] flex-1 resize-none bg-transparent py-2 text-sm text-white placeholder-[#64748B] focus:outline-none disabled:opacity-50"
          />

          {/* Reserved Voice Pit-Wall Radio Slot */}
          <button
            type="button"
            disabled
            aria-label="Voice Pit-Wall Radio (coming soon)"
            title="Pit-Wall Voice Radio (coming soon)"
            className="mb-0.5 inline-flex items-center justify-center rounded-xl border border-[#1E293B] bg-[#0B0F17]/70 p-2 text-[#64748B] opacity-70 cursor-not-allowed shrink-0"
          >
            <Mic className="h-4 w-4" />
          </button>

          {/* Send Button */}
          <button
            type="submit"
            disabled={!input.trim() || disabled}
            aria-label="Send message"
            className="mb-0.5 inline-flex items-center justify-center rounded-xl bg-[#E10600] p-2.5 text-white shadow-sm transition-colors hover:bg-[#B80500] disabled:opacity-40 shrink-0"
          >
            {disabled ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
