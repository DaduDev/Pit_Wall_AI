import { useCallback, useEffect, useRef } from 'react';
import { Loader2, LogOut, Plus, Radio } from 'lucide-react';
import { useAuth } from './hooks/useAuth';
import { useSSEStream } from './hooks/useSSEStream';
import { LoginPage } from './components/Auth/LoginPage';
import { WelcomeHero } from './components/ChatPanel/WelcomeHero';
import { TurnItem } from './components/ChatPanel/TurnItem';
import { ComposerBar } from './components/ChatPanel/ComposerBar';
import { ErrorBoundary } from './components/ErrorBoundary/ErrorBoundary';

export default function App() {
  const {
    user,
    isAuthenticated,
    isInitializing,
    isLoading,
    error,
    confirmationMessage,
    signIn,
    signUp,
    signOut,
    clearFeedback,
    handleUnauthorized,
  } = useAuth();

  const onSessionExpired = useCallback(
    (msg?: string) => {
      void handleUnauthorized(msg);
    },
    [handleUnauthorized]
  );

  const { messages, isStreaming, sendMessage, resetChat } = useSSEStream(onSessionExpired);

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const feedContentRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const lastScrollTopRef = useRef(0);
  const prevMessageCountRef = useRef(0);
  const isStreamingRef = useRef(isStreaming);
  const justFinishedRef = useRef(false);

  const scrollToBottom = useCallback((smooth = false) => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const targetTop = el.scrollHeight - el.clientHeight;
    if (smooth) {
      el.scrollTo({ top: targetTop, behavior: 'smooth' });
    } else {
      el.scrollTop = targetTop;
    }
    lastScrollTopRef.current = el.scrollTop;
  }, []);

  useEffect(() => {
    if (isStreamingRef.current && !isStreaming) {
      // Allow a brief grace window after stream 'done' for final chart/trace layout resize
      justFinishedRef.current = true;
      const timer = setTimeout(() => {
        justFinishedRef.current = false;
      }, 600);
      isStreamingRef.current = isStreaming;
      if (shouldAutoScrollRef.current) {
        requestAnimationFrame(() => scrollToBottom(false));
      }
      return () => clearTimeout(timer);
    }
    isStreamingRef.current = isStreaming;
  }, [isStreaming, scrollToBottom]);

  const handleScroll = () => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const currentTop = el.scrollTop;
    const distanceFromBottom = el.scrollHeight - currentTop - el.clientHeight;

    // Only pause auto-scroll when the user intentionally scrolls upward
    if (currentTop < lastScrollTopRef.current - 10 && distanceFromBottom > 80) {
      shouldAutoScrollRef.current = false;
    } else if (distanceFromBottom <= 80) {
      shouldAutoScrollRef.current = true;
    }
    lastScrollTopRef.current = currentTop;
  };

  // Scroll whenever messages update (new turn or streamed token/chart/trace)
  useEffect(() => {
    const isNewTurn = messages.length > prevMessageCountRef.current;
    if (isNewTurn) {
      shouldAutoScrollRef.current = true;
    }
    prevMessageCountRef.current = messages.length;

    if (messages.length > 0 && shouldAutoScrollRef.current) {
      requestAnimationFrame(() => scrollToBottom(isNewTurn && !isStreaming));
    }
  }, [messages, isStreaming, scrollToBottom]);

  // Follow async height growth (e.g. Plotly chart / card mounting) during active turn
  useEffect(() => {
    const contentEl = feedContentRef.current;
    if (!contentEl || typeof ResizeObserver === 'undefined') return;

    const observer = new ResizeObserver(() => {
      if (
        shouldAutoScrollRef.current &&
        (isStreamingRef.current || justFinishedRef.current)
      ) {
        scrollToBottom(false);
      }
    });
    observer.observe(contentEl);
    return () => observer.disconnect();
  }, [messages.length, scrollToBottom]);

  const handleSignOut = async () => {
    resetChat();
    await signOut();
  };

  if (isInitializing) {
    return (
      <div className="flex h-screen w-screen flex-col items-center justify-center bg-[#0B0F17] font-mono text-xs text-[#94A3B8]">
        <Loader2 className="mb-3 h-6 w-6 animate-spin text-[#E10600]" />
        <span>VERIFYING PITWALL SESSION...</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <LoginPage
        onSignIn={signIn}
        onSignUp={signUp}
        onClearFeedback={clearFeedback}
        isLoading={isLoading}
        error={error}
        confirmationMessage={confirmationMessage}
      />
    );
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
              onClick={handleSignOut}
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
        className="flex-1 overflow-y-auto"
      >
        <ErrorBoundary fallbackTitle="PitWall Conversation Stage Error">
          {messages.length === 0 ? (
            <div className="flex min-h-full flex-col justify-center pb-32">
              <WelcomeHero onSelect={sendMessage} disabled={isStreaming} />
            </div>
          ) : (
            <div
              ref={feedContentRef}
              className="mx-auto w-full max-w-5xl px-4 sm:px-6 pt-6 pb-40 space-y-8"
            >
              {messages.map((message) => (
                <TurnItem key={message.id} message={message} />
              ))}
            </div>
          )}
        </ErrorBoundary>
      </main>

      {/* Floating Centered Bottom Pill Composer */}
      <ComposerBar onSend={sendMessage} disabled={isStreaming} />
    </div>
  );
}
