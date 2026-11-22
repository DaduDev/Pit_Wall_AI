import { LogOut, Radio } from 'lucide-react';
import { useAuth } from './hooks/useAuth';
import { useSSEStream } from './hooks/useSSEStream';
import { LoginPage } from './components/Auth/LoginPage';
import { ChatPanel } from './components/ChatPanel/ChatPanel';
import { ChartStage } from './components/ChartStage/ChartStage';

export default function App() {
  const { user, token, isAuthenticated, isLoading, error, login, logout } = useAuth();
  const {
    messages,
    currentStatus,
    currentTrace,
    currentChart,
    currentMinimap,
    isStreaming,
    sendMessage,
    resetChat,
  } = useSSEStream(token);

  if (!isAuthenticated) {
    return <LoginPage onLogin={login} isLoading={isLoading} error={error} />;
  }

  return (
    <div className="flex h-screen w-screen flex-col bg-[#0B0F17] font-sans text-[#E2E8F0]">
      {/* Top HUD Status Bar */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-[#1E293B] px-6 bg-[#121824]/90 backdrop-blur-md">
        <div className="flex items-center space-x-3">
          <div className="flex h-7 w-7 items-center justify-center rounded bg-[#E10600] font-mono text-xs font-black text-white shadow-sm">
            F1
          </div>
          <span className="font-mono text-base font-bold tracking-wider text-white">
            PITWALL <span className="text-[#E10600]">AI</span>
          </span>
          <span className="rounded bg-[#1E293B] px-2 py-0.5 text-[11px] font-mono text-[#94A3B8]">
            RACE ENGINEER v0.1
          </span>
        </div>

        {/* Live System Diagnostics */}
        <div className="flex items-center space-x-6 text-xs font-mono">
          <div className="flex items-center space-x-1.5 text-emerald-400">
            <Radio className="h-3.5 w-3.5 animate-pulse" />
            <span>DUCKDB: ONLINE</span>
          </div>
          <div className="flex items-center space-x-1.5 text-emerald-400">
            <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
            <span>FASTF1: READY</span>
          </div>

          <div className="h-4 w-px bg-[#1E293B]"></div>

          {/* User profile & sign out */}
          <div className="flex items-center space-x-3 text-[#94A3B8]">
            <span>{user?.display_name || user?.email}</span>
            <button
              onClick={logout}
              title="Sign Out"
              className="rounded p-1 text-[#94A3B8] hover:bg-[#1E293B] hover:text-[#EF4444] transition-colors"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Two-Panel Layout */}
      <main className="flex flex-1 overflow-hidden">
        {/* Left Panel: Comms & Query Assistant (40% width) */}
        <section className="flex w-[42%] min-w-[380px] max-w-[550px] flex-col border-r border-[#1E293B]">
          <ChatPanel
            messages={messages}
            currentStatus={currentStatus}
            isStreaming={isStreaming}
            onSendMessage={sendMessage}
            onReset={resetChat}
          />
        </section>

        {/* Right Panel: Plotly Telemetry Stage & Trace Drawer (60% width) */}
        <section className="flex flex-1 flex-col overflow-hidden">
          <ChartStage chart={currentChart} minimap={currentMinimap} trace={currentTrace} />
        </section>
      </main>
    </div>
  );
}
