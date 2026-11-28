import { useState } from 'react';
import { User, AuthState } from '../types';
import { apiUrl } from '../services/api';

export function useAuth() {
  const [authState, setAuthState] = useState<AuthState>(() => {
    const token = localStorage.getItem('pitwall_token');
    const userStr = localStorage.getItem('pitwall_user');
    if (token && userStr) {
      try {
        return {
          token,
          user: JSON.parse(userStr) as User,
          isAuthenticated: true,
        };
      } catch {
        // invalid JSON
      }
    }
    return { token: null, user: null, isAuthenticated: false };
  });

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = async (email: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(apiUrl('/api/auth/login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to authenticate');
      }

      const data = await res.json();
      localStorage.setItem('pitwall_token', data.access_token);
      localStorage.setItem('pitwall_user', JSON.stringify(data.user));

      setAuthState({
        token: data.access_token,
        user: data.user,
        isAuthenticated: true,
      });
      return true;
    } catch (err: any) {
      setError(err.message || 'Login failed');
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('pitwall_token');
    localStorage.removeItem('pitwall_user');
    setAuthState({ token: null, user: null, isAuthenticated: false });
  };

  return {
    ...authState,
    isLoading,
    error,
    login,
    logout,
  };
}
