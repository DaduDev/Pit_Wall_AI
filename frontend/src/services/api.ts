const API_BASE = (import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "")).replace(/\/$/, "");

export { API_BASE };

export function apiUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE}${cleanPath}`;
}

export async function fetchHealth(): Promise<any> {
  const res = await fetch(apiUrl('/health'));
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: Health check failed`);
  }
  return res.json();
}
