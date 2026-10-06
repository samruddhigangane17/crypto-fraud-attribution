import { supabase } from './supabase';

export const API_BASE: string =
  import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : (typeof window !== 'undefined' && (window.location.port === '5173' || window.location.port === '80')
        ? ''
        : 'http://localhost:8000');

/** Fetch from the FastAPI backend with the investigator's Supabase token attached. */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  const primaryUrl = `${API_BASE}${path}`;
  try {
    return await fetch(primaryUrl, { ...init, headers });
  } catch (err) {
    // If the primary request hit a network/CORS boundary, attempt the alternate route
    if (API_BASE === '' && typeof window !== 'undefined') {
      const fallbackUrl = `http://localhost:8000${path}`;
      return await fetch(fallbackUrl, { ...init, headers });
    } else if (API_BASE !== '' && API_BASE.includes(':8000')) {
      return await fetch(path, { ...init, headers });
    }
    throw err;
  }
}

/** Like apiFetch, but parses JSON and throws a readable error on non-2xx responses. */
export async function apiJson<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}
