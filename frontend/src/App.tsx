import { useEffect, useRef } from 'react';
import { LogOut, Plus, Radio } from 'lucide-react';
import { useAuth } from './hooks/useAuth';
import { useSSEStream } from './hooks/useSSEStream';
import { LoginPage } from './components/Auth/LoginPage';
import { WelcomeHero } from './components/ChatPanel/WelcomeHero';
import { TurnItem } from './components/ChatPanel/TurnItem';
import { ComposerBar } from './components/ChatPanel/ComposerBar';
import { ErrorBoundary } from './components/ErrorBoundary/ErrorBoundary';

export default function App() {
  const { user, token, isAuthenticated, isLoading, error, login, logout } = useAuth();
  const { messages, isStreaming, sendMessage, resetChat } = useSSEStream(token);

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const feedEndRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const prevMessageCountRef = useRef(0);

  const handleScroll = () => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    shouldAutoScrollRef.current = distanceFromBottom < 180;
  };

  useEffect(() => {
    if (messages.length > prevMessageCountRef.current) {
      shouldAutoScrollRef.current = true;
    }
    prevMessageCountRef.current = messages.length;

    if (messages.length > 0 && shouldAutoScrollRef.current) {
      feedEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [messages]);

  if (!isAuthenticated) {
    return <LoginPage onLogin={login} isLoading={isLoading} error={error} />;
  }

  return (
    <div className="flex h-screen w-screen flex-col bg-[#0B0F17] font-sans text-[#E2E8F0]">
      {/* Slim Top HUD Bar */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-[#1E293B] px-4 sm:px-6 bg-[#121824]/90 backdrop-blur-md">
        <div className="flex items-center space-x-3">
          <div className="flex h-7 w-7 items-center justify-center rounded bg-[#E10600] font-mono text-xs font-black text-white shadow-sm">
            F1
          </div>
          <span className="font-mono text-sm sm:text-base font-bold tracking-wider text-white">
            F1 PITWALL <span className="text-[#E10600]">AI</span>
          </span>
          <div className="hidden md:flex items-center space-x-4 pl-3 border-l border-[#1E293B] text-[11px] font-mono">
            <div className="flex items-center space-x-1.5 text-emerald-400">
              <Radio className="h-3.5 w-3.5 animate-pulse" />
              <span>DUCKDB</span>
            </div>
            <div className="flex items-center space-x-1.5 text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
              <span>FASTF1</span>
            </div>
          </div>
        </div>

        {/* + New Session, User profile & Sign out */}
        <div className="flex items-center space-x-3 text-xs font-mono">
          <button
            type="button"
            onClick={resetChat}
            title="Start a new PitWall session"
            className="inline-flex items-center space-x-1.5 rounded-lg border border-[#1E293B] bg-[#0B0F17] px-3 py-1.5 text-xs font-mono text-[#E2E8F0] hover:border-[#E10600]/60 hover:bg-[#1A2234] hover:text-white transition-colors"
          >
            <Plus className="h-3.5 w-3.5 text-[#E10600]" />
            <span>New Session</span>
          </button>

          <div className="hidden sm:block h-4 w-px bg-[#1E293B]"></div>

          <div className="flex items-center space-x-2 text-[#94A3B8]">
            <span className="hidden sm:inline truncate max-w-[160px]">
              {user?.display_name || user?.email}
            </span>
            <button
              type="button"
              onClick={logout}
              title="Sign Out"
              className="rounded p-1.5 text-[#94A3B8] hover:bg-[#1E293B] hover:text-[#EF4444] transition-colors"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Centered Single-Column Conversational Feed */}
      <main
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto pb-36"
      >
        <ErrorBoundary fallbackTitle="PitWall Conversation Stage Error">
          {messages.length === 0 ? (
            <div className="flex min-h-full flex-col justify-center">
              <WelcomeHero onSelect={sendMessage} disabled={isStreaming} />
            </div>
          ) : (
            <div className="mx-auto w-full max-w-5xl px-4 sm:px-6 py-6 space-y-8">
              {messages.map((message) => (
                <TurnItem key={message.id} message={message} />
              ))}
              <div ref={feedEndRef} className="h-2" />
            </div>
          )}
        </ErrorBoundary>
      </main>

      {/* Floating Centered Bottom Pill Composer */}
      <ComposerBar onSend={sendMessage} disabled={isStreaming} />
    </div>
  );
}
