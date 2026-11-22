import React, { useState } from 'react';
import { ShieldCheck, AlertCircle } from 'lucide-react';

interface LoginPageProps {
  onLogin: (email: string, password: string) => Promise<boolean>;
  isLoading: boolean;
  error: string | null;
}

export function LoginPage({ onLogin, isLoading, error }: LoginPageProps) {
  const [email, setEmail] = useState('demo@pitwall.ai');
  const [password, setPassword] = useState('Pitwall2024!');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onLogin(email, password);
  };

  const handleDemoSignIn = async () => {
    setEmail('demo@pitwall.ai');
    setPassword('Pitwall2024!');
    await onLogin('demo@pitwall.ai', 'Pitwall2024!');
  };

  return (
    <div className="flex min-h-screen w-screen items-center justify-center bg-[#0B0F17] px-4 font-sans text-[#E2E8F0]">
      <div className="w-full max-w-md rounded-xl border border-[#1E293B] bg-[#121824] p-8 shadow-2xl backdrop-blur-md">
        {/* Brand Header */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-lg bg-[#E10600] font-mono text-xl font-black text-white shadow-lg">
            F1
          </div>
          <h1 className="font-mono text-2xl font-bold tracking-wider text-white">
            PITWALL <span className="text-[#E10600]">AI</span>
          </h1>
          <p className="mt-1 text-xs font-mono text-[#94A3B8]">
            FORMULA 1 AI RACE ENGINEER & TELEMETRY
          </p>
        </div>

        {error && (
          <div className="mb-4 flex items-center space-x-2 rounded border border-red-500/50 bg-red-950/30 p-3 text-xs text-red-300">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-mono uppercase tracking-wider text-[#94A3B8] mb-1">
              Engineer Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full rounded-md border border-[#1E293B] bg-[#0B0F17] px-3.5 py-2.5 text-sm text-white focus:border-[#E10600] focus:outline-none focus:ring-1 focus:ring-[#E10600]"
            />
          </div>

          <div>
            <label className="block text-xs font-mono uppercase tracking-wider text-[#94A3B8] mb-1">
              Access Key
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full rounded-md border border-[#1E293B] bg-[#0B0F17] px-3.5 py-2.5 text-sm text-white focus:border-[#E10600] focus:outline-none focus:ring-1 focus:ring-[#E10600]"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-md bg-[#E10600] py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#B80500] disabled:opacity-50"
          >
            {isLoading ? 'Authenticating...' : 'Sign In to Pit Wall'}
          </button>
        </form>

        <div className="my-5 flex items-center">
          <div className="flex-1 border-t border-[#1E293B]"></div>
          <span className="px-3 text-xs font-mono text-[#64748B]">DEMO ACCESS</span>
          <div className="flex-1 border-t border-[#1E293B]"></div>
        </div>

        <button
          type="button"
          onClick={handleDemoSignIn}
          disabled={isLoading}
          className="flex w-full items-center justify-center space-x-2 rounded-md border border-[#1E293B] bg-[#0B0F17] py-2 text-xs font-mono text-[#94A3B8] transition-colors hover:border-[#E10600] hover:text-white"
        >
          <ShieldCheck className="h-4 w-4 text-emerald-400" />
          <span>Quick Sign In as Demo Engineer</span>
        </button>

        <div className="mt-6 text-center text-[11px] font-mono text-[#64748B]">
          Pre-configured: demo@pitwall.ai / Pitwall2024!
        </div>
      </div>
    </div>
  );
}
