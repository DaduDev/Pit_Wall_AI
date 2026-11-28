import { createClient, SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = (import.meta.env.VITE_SUPABASE_URL || '').trim();
const supabaseAnonKey = (import.meta.env.VITE_SUPABASE_ANON_KEY || '').trim();

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);

let _supabaseClient: SupabaseClient | null = null;

if (isSupabaseConfigured) {
  _supabaseClient = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  });
}

export function getSupabaseClient(): SupabaseClient {
  if (!_supabaseClient) {
    throw new Error(
      'Authentication is not configured: VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY must be set.'
    );
  }
  return _supabaseClient;
}
