import React, { useState } from 'react';
import { Activity, Terminal, Database, ShieldCheck } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState<'chat' | 'trace'>('chat');

  return (
    <div className="flex h-screen w-screen flex-col bg-[#0B0F17] text-[#E2E8F0]">
      {/* Top HUD Status Bar */}
      <header className="flex h-14 items-center justify-between border-b border-[#1E293B] px-6 bg-[#121824]/80 backdrop-blur-sm">
        <div className="flex items-center space-x-3">
          <div className="flex h-7 w-7 items-center justify-center rounded bg-[#E10600] font-bold text-white text-xs">
            F1
          </div>
          <span className="font-mono text-lg font-bold tracking-wider text-white">
            PITWALL <span className="text-[#E10600]">AI</span>
          </span>
          <span className="rounded bg-[#1E293B] px-2 py-0.5 text-xs font-mono text-[#94A3B8]">
            RACE ENGINEER v0.1
          </span>
        </div>

        <div className="flex items-center space-x-4 text-xs font-mono text-[#94A3B8]">
          <div className="flex items-center space-x-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>DUCKDB: CONNECTED</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
            <span>FASTF1 CACHE: READY</span>
          </div>
        </div>
      </header>

      {/* Main Two-Panel Layout */}
      <main className="flex flex-1 overflow-hidden">
        {/* Left Panel: Chat & Prompt Suggestions */}
        <section className="flex w-2/5 min-w-[380px] flex-col border-r border-[#1E293B] bg-[#0B0F17]">
          <div className="p-4 border-b border-[#1E293B] text-xs font-mono text-[#94A3B8] flex items-center justify-between">
            <span>SESSION: SES_LIVE_01</span>
            <span className="text-emerald-400">TELEMETRY LINK ACTIVE</span>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div className="rounded-lg border border-[#1E293B] bg-[#121824] p-4 text-sm leading-relaxed">
              <div className="flex items-center space-x-2 text-[#E10600] font-mono font-semibold text-xs mb-1">
                <Terminal className="h-3.5 w-3.5" />
                <span>PITWALL ENGINEER</span>
              </div>
              Telemetry and historical databases online. You can ask historical queries (1950–2024+) or compare driver telemetry (2018+).
            </div>
          </div>

          <div className="p-4 border-t border-[#1E293B] bg-[#121824]/50">
            <input
              type="text"
              placeholder="Ask a race engineering question or corner comparison..."
              className="w-full rounded-md border border-[#1E293B] bg-[#0B0F17] px-4 py-2.5 text-sm text-white placeholder-[#94A3B8] focus:border-[#E10600] focus:outline-none focus:ring-1 focus:ring-[#E10600]"
            />
          </div>
        </section>

        {/* Right Panel: Interactive Plotly Stage & Engineering Trace Drawer */}
        <section className="flex flex-1 flex-col bg-[#0B0F17] p-6 overflow-y-auto">
          <div className="flex items-center justify-between pb-4 border-b border-[#1E293B]">
            <h2 className="font-mono text-sm uppercase tracking-wider text-white">
              Telemetry & Analytics Stage
            </h2>
            <div className="flex space-x-2">
              <button className="rounded border border-[#1E293B] bg-[#121824] px-3 py-1 text-xs font-mono text-[#94A3B8] hover:text-white">
                Engineering Trace
              </button>
            </div>
          </div>

          <div className="flex flex-1 items-center justify-center">
            <div className="text-center text-xs font-mono text-[#94A3B8]">
              <Activity className="mx-auto h-8 w-8 mb-2 text-[#334155]" />
              Select a query or submit a question to initialize telemetry visualization.
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
