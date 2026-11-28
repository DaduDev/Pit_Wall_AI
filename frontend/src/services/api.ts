import { getSupabaseClient, isSupabaseConfigured } from '../lib/supabase';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

export { API_BASE };

export function apiUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE}${cleanPath}`;
}

export async function getAccessToken(): Promise<string | null> {
  if (!isSupabaseConfigured) {
    return null;
  }
  const { data, error } = await getSupabaseClient().auth.getSession();
  if (error || !data.session?.access_token) {
    return null;
  }
  return data.session.access_token;
}

export async function authHeaders(
  extra: Record<string, string> = {}
): Promise<Record<string, string>> {
  const token = await getAccessToken();
  const headers: Record<string, string> = { ...extra };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export async function fetchHealth(): Promise<any> {
  const res = await fetch(apiUrl('/health'));
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: Health check failed`);
  }
  return res.json();
}
