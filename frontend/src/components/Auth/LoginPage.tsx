import React, { useState } from 'react';
import { AlertCircle, Loader2, MailCheck } from 'lucide-react';
import { SignUpOutcome } from '../../hooks/useAuth';

interface LoginPageProps {
  onSignIn: (email: string, password: string) => Promise<boolean>;
  onSignUp: (
    email: string,
    password: string,
    displayName?: string
  ) => Promise<SignUpOutcome>;
  onClearFeedback?: () => void;
  isLoading: boolean;
  error: string | null;
  confirmationMessage: string | null;
}

export function LoginPage({
  onSignIn,
  onSignUp,
  onClearFeedback,
  isLoading,
  error,
  confirmationMessage,
}: LoginPageProps) {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const switchMode = (nextMode: 'signin' | 'signup') => {
    setMode(nextMode);
    setLocalError(null);
    setPassword('');
    onClearFeedback?.();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      setLocalError('Please enter a valid email address.');
      return;
    }

    if (mode === 'signup') {
      if (password.length < 6) {
        setLocalError('Password must be at least 6 characters long.');
        return;
      }
      const outcome = await onSignUp(trimmedEmail, password, displayName);
      if (outcome === 'confirmation_required') {
        setMode('signin');
        setPassword('');
      }
      return;
    }

    if (!password) {
      setLocalError('Please enter your password.');
      return;
    }
    await onSignIn(trimmedEmail, password);
  };

  const displayedError = localError || error;

  return (
    <div className="flex min-h-screen w-screen items-center justify-center bg-[#0B0F17] px-4 font-sans text-[#E2E8F0]">
      <div className="w-full max-w-md rounded-xl border border-[#1E293B] bg-[#121824] p-8 shadow-2xl backdrop-blur-md">
        {/* Brand Header */}
        <div className="mb-6 text-center">
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

        {/* Sign In / Create Account Mode Switcher */}
        <div className="mb-6 grid grid-cols-2 rounded-lg border border-[#1E293B] bg-[#0B0F17] p-1 text-xs font-mono">
          <button
            type="button"
            disabled={isLoading}
            onClick={() => switchMode('signin')}
            className={`rounded-md py-2 font-semibold transition-colors ${
              mode === 'signin'
                ? 'bg-[#E10600] text-white shadow-sm'
                : 'text-[#94A3B8] hover:text-white'
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            disabled={isLoading}
            onClick={() => switchMode('signup')}
            className={`rounded-md py-2 font-semibold transition-colors ${
              mode === 'signup'
                ? 'bg-[#E10600] text-white shadow-sm'
                : 'text-[#94A3B8] hover:text-white'
            }`}
          >
            Create Account
          </button>
        </div>

        {/* Email Confirmation Required Banner */}
        {confirmationMessage && (
          <div
            role="status"
            className="mb-4 flex items-start space-x-2.5 rounded-lg border border-emerald-500/40 bg-emerald-950/30 p-3 text-xs text-emerald-300"
          >
            <MailCheck className="h-4 w-4 shrink-0 mt-0.5 text-emerald-400" />
            <span className="leading-relaxed">{confirmationMessage}</span>
          </div>
        )}

        {/* Inline Validation / Auth Error Banner */}
        {displayedError && (
          <div
            role="alert"
            className="mb-4 flex items-start space-x-2.5 rounded-lg border border-red-500/50 bg-red-950/30 p-3 text-xs text-red-300"
          >
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-red-400" />
            <span className="leading-relaxed">{displayedError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          {mode === 'signup' && (
            <div>
              <label
                htmlFor="pitwall-display-name"
                className="mb-1 block text-xs font-mono uppercase tracking-wider text-[#94A3B8]"
              >
                Display Name (Optional)
              </label>
              <input
                id="pitwall-display-name"
                type="text"
                autoComplete="name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                disabled={isLoading}
                placeholder="Race Engineer"
                className="w-full rounded-md border border-[#1E293B] bg-[#0B0F17] px-3.5 py-2.5 text-sm text-white placeholder-[#64748B] focus:border-[#E10600] focus:outline-none focus:ring-1 focus:ring-[#E10600] disabled:opacity-50"
              />
            </div>
          )}

          <div>
            <label
              htmlFor="pitwall-email"
              className="mb-1 block text-xs font-mono uppercase tracking-wider text-[#94A3B8]"
            >
              Engineer Email
            </label>
            <input
              id="pitwall-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isLoading}
              required
              placeholder="name@example.com"
              className="w-full rounded-md border border-[#1E293B] bg-[#0B0F17] px-3.5 py-2.5 text-sm text-white placeholder-[#64748B] focus:border-[#E10600] focus:outline-none focus:ring-1 focus:ring-[#E10600] disabled:opacity-50"
            />
          </div>

          <div>
            <label
              htmlFor="pitwall-password"
              className="mb-1 block text-xs font-mono uppercase tracking-wider text-[#94A3B8]"
            >
              Password
            </label>
            <input
              id="pitwall-password"
              type="password"
              autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isLoading}
              minLength={mode === 'signup' ? 6 : undefined}
              required
              placeholder={mode === 'signup' ? 'Minimum 6 characters' : 'Enter your password'}
              className="w-full rounded-md border border-[#1E293B] bg-[#0B0F17] px-3.5 py-2.5 text-sm text-white placeholder-[#64748B] focus:border-[#E10600] focus:outline-none focus:ring-1 focus:ring-[#E10600] disabled:opacity-50"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="flex w-full items-center justify-center space-x-2 rounded-md bg-[#E10600] py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#B80500] disabled:opacity-50"
          >
            {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
            <span>
              {isLoading
                ? mode === 'signup'
                  ? 'Creating Account...'
                  : 'Authenticating...'
                : mode === 'signup'
                ? 'Create PitWall Account'
                : 'Sign In to Pit Wall'}
            </span>
          </button>
        </form>
      </div>
    </div>
  );
}
