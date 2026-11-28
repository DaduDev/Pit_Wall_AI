import { useCallback, useEffect, useState } from 'react';
import { User as SupabaseUser, Session } from '@supabase/supabase-js';
import { AuthState, User } from '../types';
import { getSupabaseClient, isSupabaseConfigured } from '../lib/supabase';

export type SignUpOutcome = 'signed_in' | 'confirmation_required' | 'error';

function mapSupabaseUser(sbUser: SupabaseUser): User {
  const email = sbUser.email || '';
  const meta = (sbUser.user_metadata || {}) as Record<string, unknown>;
  const rawName = meta.display_name || meta.full_name || (email ? email.split('@')[0] : 'Engineer');
  return {
    id: sbUser.id,
    email,
    display_name: String(rawName || 'Engineer'),
  };
}

function formatSupabaseAuthError(rawMessage: string): string {
  const msg = (rawMessage || '').trim();
  const lower = msg.toLowerCase();
  if (lower.includes('email not confirmed')) {
    return 'Email confirmation is required before signing in. Check your inbox for the confirmation link.';
  }
  if (lower.includes('invalid login credentials')) {
    return 'Invalid email or password. Please check your credentials and try again.';
  }
  if (lower.includes('user already registered')) {
    return 'An account with this email already exists. Try signing in instead.';
  }
  if (lower.includes('password should be at least')) {
    return 'Password must be at least 6 characters long.';
  }
  return msg || 'Authentication failed. Please try again.';
}

export function useAuth() {
  const [authState, setAuthState] = useState<AuthState>(() => ({
    user: null,
    token: null,
    isAuthenticated: false,
    isInitializing: true,
    confirmationMessage: null,
    error: isSupabaseConfigured
      ? null
      : 'Authentication service is not configured (VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY missing).',
  }));
  const [isLoading, setIsLoading] = useState(false);

  const applySession = useCallback((session: Session | null) => {
    if (session?.user && session.access_token) {
      setAuthState((prev) => ({
        ...prev,
        user: mapSupabaseUser(session.user),
        token: session.access_token,
        isAuthenticated: true,
        isInitializing: false,
        confirmationMessage: null,
        error: null,
      }));
    } else {
      setAuthState((prev) => ({
        ...prev,
        user: null,
        token: null,
        isAuthenticated: false,
        isInitializing: false,
      }));
    }
  }, []);

  useEffect(() => {
    // Purge legacy placeholder storage keys if present from older builds
    localStorage.removeItem('pitwall_token');
    localStorage.removeItem('pitwall_user');

    if (!isSupabaseConfigured) {
      setAuthState((prev) => ({ ...prev, isInitializing: false }));
      return;
    }

    let mounted = true;
    const supabase = getSupabaseClient();

    supabase.auth
      .getSession()
      .then(({ data, error }) => {
        if (!mounted) return;
        if (error) {
          setAuthState((prev) => ({
            ...prev,
            user: null,
            token: null,
            isAuthenticated: false,
            isInitializing: false,
            error: formatSupabaseAuthError(error.message),
          }));
          return;
        }
        applySession(data.session ?? null);
      })
      .catch(() => {
        if (!mounted) return;
        setAuthState((prev) => ({
          ...prev,
          user: null,
          token: null,
          isAuthenticated: false,
          isInitializing: false,
        }));
      });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!mounted) return;
      applySession(session);
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, [applySession]);

  const clearFeedback = useCallback(() => {
    setAuthState((prev) => ({
      ...prev,
      error: null,
      confirmationMessage: null,
    }));
  }, []);

  const signIn = useCallback(async (email: string, password: string): Promise<boolean> => {
    if (!isSupabaseConfigured) {
      setAuthState((prev) => ({
        ...prev,
        error: 'Authentication service is not configured.',
      }));
      return false;
    }

    const cleanEmail = email.trim();
    if (!cleanEmail || !password) {
      setAuthState((prev) => ({
        ...prev,
        error: 'Please enter both your email address and password.',
      }));
      return false;
    }

    setIsLoading(true);
    setAuthState((prev) => ({ ...prev, error: null, confirmationMessage: null }));
    try {
      const supabase = getSupabaseClient();
      const { data, error } = await supabase.auth.signInWithPassword({
        email: cleanEmail,
        password,
      });

      if (error) {
        setAuthState((prev) => ({
          ...prev,
          error: formatSupabaseAuthError(error.message),
        }));
        return false;
      }

      if (!data.session) {
        setAuthState((prev) => ({
          ...prev,
          error: 'No active session returned. Check whether email confirmation is required.',
        }));
        return false;
      }

      applySession(data.session);
      return true;
    } catch (err: any) {
      setAuthState((prev) => ({
        ...prev,
        error: formatSupabaseAuthError(err?.message || 'Sign in failed'),
      }));
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [applySession]);

  const signUp = useCallback(
    async (
      email: string,
      password: string,
      displayName?: string
    ): Promise<SignUpOutcome> => {
      if (!isSupabaseConfigured) {
        setAuthState((prev) => ({
          ...prev,
          error: 'Authentication service is not configured.',
        }));
        return 'error';
      }

      const cleanEmail = email.trim();
      const cleanName = (displayName || '').trim();
      if (!cleanEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
        setAuthState((prev) => ({
          ...prev,
          error: 'Please enter a valid email address.',
        }));
        return 'error';
      }
      if (password.length < 6) {
        setAuthState((prev) => ({
          ...prev,
          error: 'Password must be at least 6 characters long.',
        }));
        return 'error';
      }

      setIsLoading(true);
      setAuthState((prev) => ({ ...prev, error: null, confirmationMessage: null }));
      try {
        const supabase = getSupabaseClient();
        const { data, error } = await supabase.auth.signUp({
          email: cleanEmail,
          password,
          options: cleanName ? { data: { display_name: cleanName } } : undefined,
        });

        if (error) {
          setAuthState((prev) => ({
            ...prev,
            error: formatSupabaseAuthError(error.message),
          }));
          return 'error';
        }

        if (data.session) {
          applySession(data.session);
          return 'signed_in';
        }

        if (data.user && !data.session) {
          setAuthState((prev) => ({
            ...prev,
            user: null,
            token: null,
            isAuthenticated: false,
            error: null,
            confirmationMessage: `Confirmation email sent to ${cleanEmail}. Check your inbox and confirm your address before signing in.`,
          }));
          return 'confirmation_required';
        }

        setAuthState((prev) => ({
          ...prev,
          error: 'Unable to complete registration. Please try again.',
        }));
        return 'error';
      } catch (err: any) {
        setAuthState((prev) => ({
          ...prev,
          error: formatSupabaseAuthError(err?.message || 'Registration failed'),
        }));
        return 'error';
      } finally {
        setIsLoading(false);
      }
    },
    [applySession]
  );

  const signOut = useCallback(async (): Promise<void> => {
    try {
      if (isSupabaseConfigured) {
        await getSupabaseClient().auth.signOut();
      }
    } catch {
      // Clear client state even if remote sign-out fails
    } finally {
      localStorage.removeItem('pitwall_token');
      localStorage.removeItem('pitwall_user');
      setAuthState({
        user: null,
        token: null,
        isAuthenticated: false,
        isInitializing: false,
        confirmationMessage: null,
        error: null,
      });
    }
  }, []);

  const handleUnauthorized = useCallback(async (message?: string): Promise<void> => {
    try {
      if (isSupabaseConfigured) {
        await getSupabaseClient().auth.signOut();
      }
    } catch {
      // Ignore network sign-out error during expired-session cleanup
    } finally {
      setAuthState({
        user: null,
        token: null,
        isAuthenticated: false,
        isInitializing: false,
        confirmationMessage: null,
        error: message || 'Your session has expired or is invalid. Please sign in again.',
      });
    }
  }, []);

  return {
    ...authState,
    isLoading,
    signIn,
    signUp,
    signOut,
    clearFeedback,
    handleUnauthorized,
  };
}
