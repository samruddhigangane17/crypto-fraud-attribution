import { API_BASE } from './api';

export interface VictimSession {
  token: string;
  phone?: string;
  email?: string;
  displayName?: string;
  victimId: string;
}

export interface ComplaintData {
  id: string;
  ack_id?: string;
  status: 'draft' | 'submitted';
  lifecycle: 'received' | 'verified' | 'in_progress' | 'action_taken' | 'closed';
  fraud_type?: string;
  incident_time?: string;
  amount_lost?: string | number;
  asset?: string;
  payment_method?: string;
  scammer_wallet?: string;
  tx_hash?: string;
  chain?: string;
  platform?: string;
  story?: string;
  declaration_true?: boolean;
  submitted_at?: string;
  created_at?: string;
  case_id?: string;
  verification?: 'unverified' | 'verified' | 'rejected';
}

export interface EvidenceFileItem {
  id: string;
  file_id: string;
  filename: string;
  mime: string;
  size: number;
  sha256: string;
  version: number;
  uploaded_at: string;
  uploaded_by: string;
  restricted: boolean;
  preview_url?: string;
}

export interface OfficerRequestItem {
  id: string;
  text: string;
  status: 'open' | 'answered';
  created_at: string;
}

const VICTIM_TOKEN_KEY = 'cryptotracer_victim_token';
const VICTIM_USER_KEY = 'cryptotracer_victim_user';

export function getStoredVictimSession(): VictimSession | null {
  try {
    const raw = localStorage.getItem(VICTIM_USER_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function saveVictimSession(session: VictimSession): void {
  try {
    localStorage.setItem(VICTIM_USER_KEY, JSON.stringify(session));
    localStorage.setItem(VICTIM_TOKEN_KEY, session.token);
  } catch {}
}

export function clearVictimSession(): void {
  try {
    localStorage.removeItem(VICTIM_USER_KEY);
    localStorage.removeItem(VICTIM_TOKEN_KEY);
  } catch {}
}

export async function ensureVictimSession(): Promise<VictimSession> {
  const existing = getStoredVictimSession();
  if (existing && existing.token) return existing;
  try {
    const base = API_BASE || (typeof window !== 'undefined' && window.location.port === '5173' ? '' : 'http://localhost:8000');
    const phone = '9876543210';
    const otpRes = await fetch(`${base}/api/victim/auth/otp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone }),
    });
    const otpData = await otpRes.json();
    const otp = otpData.dev_otp || '123456';
    const verRes = await fetch(`${base}/api/victim/auth/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone, otp, consent_accepted: true, display_name: 'Citizen Anonymous' }),
    });
    const verData = await verRes.json();
    if (verData.access_token) {
      const sess: VictimSession = {
        token: verData.access_token,
        phone,
        displayName: 'Citizen Anonymous',
        victimId: verData.victim?.id || 'citizen-01',
      };
      saveVictimSession(sess);
      return sess;
    }
  } catch (e) {
    console.warn('Auto victim session creation notice:', e);
  }
  return {
    token: 'fallback-victim-token',
    phone: '9876543210',
    displayName: 'Citizen Anonymous',
    victimId: 'citizen-guest',
  };
}

/** Fetch with Victim JWT token attached in headers */
export async function victimFetch(path: string, init: RequestInit = {}): Promise<Response> {
  let session = getStoredVictimSession();
  if (!session?.token && !path.includes('/auth/')) {
    session = await ensureVictimSession();
  }
  const token = session?.token;
  const headers = new Headers(init.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const normalizedPath = path.startsWith('/victim/') ? `/api${path}` : path;
  const primaryUrl = `${API_BASE}${normalizedPath}`;
  try {
    return await fetch(primaryUrl, { ...init, headers });
  } catch (err) {
    if (API_BASE === '' && typeof window !== 'undefined') {
      const fallbackUrl = `http://localhost:8000${normalizedPath}`;
      return await fetch(fallbackUrl, { ...init, headers });
    }
    throw err;
  }
}

export async function victimJson<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await victimFetch(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {}
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

/** Compute SHA-256 digest of a File object using Web Crypto API */
export async function computeBrowserSha256(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** Chain format detection helper */
export function detectCryptoChain(address: string): { chain: string; isValid: boolean; label: string } {
  const trimmed = address.trim();
  if (!trimmed) {
    return { chain: 'unknown', isValid: false, label: 'Enter suspect address' };
  }

  // Ethereum / BSC / EVM (0x + 40 hex chars)
  if (/^0x[a-fA-F0-9]{40}$/.test(trimmed)) {
    return { chain: 'ethereum', isValid: true, label: 'EVM (Ethereum / BSC / Polygon)' };
  }

  // TRON (Base58 starting with T, length 34)
  if (/^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(trimmed)) {
    return { chain: 'tron', isValid: true, label: 'TRON (TRC-20)' };
  }

  // Bitcoin Legacy, P2SH, Bech32
  if (/^(1[1-9A-HJ-NP-Za-km-z]{25,34}|3[1-9A-HJ-NP-Za-km-z]{25,34}|bc1[qpzry9x8gf2tvdw0s3jn54khce6mua7l]{38,59})$/i.test(trimmed)) {
    return { chain: 'bitcoin', isValid: true, label: 'Bitcoin (BTC)' };
  }

  // Mock / Testnet format support (for local demo)
  if (trimmed.startsWith('0xmock') || trimmed.startsWith('mock_')) {
    return { chain: 'ethereum', isValid: true, label: 'Demo / Mock Address' };
  }

  return { chain: 'unknown', isValid: false, label: 'Unrecognized address format' };
}

/** Strict Seed Phrase and Sensitive Credential Blocker */
const COMMON_ENGLISH_WORDS = new Set([
  'the', 'and', 'for', 'you', 'your', 'are', 'was', 'were', 'with', 'that', 'this', 'have', 'has', 'had',
  'not', 'but', 'they', 'them', 'their', 'then', 'than', 'from', 'into', 'out', 'our', 'his', 'her', 'she',
  'him', 'its', 'who', 'what', 'when', 'where', 'why', 'how', 'can', 'could', 'would', 'should', 'will',
  'just', 'all', 'any', 'some', 'one', 'two', 'been', 'being', 'did', 'does', 'done', 'get', 'got', 'let',
  'via', 'per', 'also', 'very', 'more', 'most', 'much', 'many', 'such', 'only', 'over', 'after', 'before',
  'again', 'about', 'above', 'below', 'under', 'off', 'own', 'same', 'too', 'yes', 'say', 'said', 'tell',
  'told', 'ask', 'asked', 'sent', 'send', 'give', 'gave', 'take', 'took', 'made', 'make', 'went', 'come',
  'came', 'use', 'used', 'like', 'want', 'need', 'know', 'see', 'saw', 'look', 'back', 'there', 'here',
  'now', 'still', 'even', 'ever', 'never', 'because', 'while', 'which', 'these', 'those', 'other', 'another',
  'each', 'both', 'few', 'new', 'old'
]);

export function scanSensitiveInput(text: string): { isBlocked: boolean; reason?: string } {
  if (!text || text.trim().length === 0) return { isBlocked: false };

  // 1. Private keys detection (64-hex private key, WIF, xprv)
  if (/\bxprv[1-9A-HJ-NP-Za-km-z]{100,}\b/.test(text) || /\b[5KL][1-9A-HJ-NP-Za-km-z]{50,51}\b/.test(text)) {
    return {
      isBlocked: true,
      reason: 'CRITICAL SECURITY: Private key detected. Never share your private keys or master keys with anyone.'
    };
  }
  if (/private\s*key\s*(is|:|=)?\s*(0x)?[0-9a-fA-F]{64}\b/i.test(text)) {
    return {
      isBlocked: true,
      reason: 'CRITICAL SECURITY: Private key detected. Legitimate law enforcement will NEVER ask for private keys.'
    };
  }

  // 2. Aadhaar numbers (12 digits with or without spacing)
  if (/\b\d{4}[ -]\d{4}[ -]\d{4}\b/.test(text) || /aadh?a+r\D{0,12}\d{12}\b/i.test(text)) {
    return {
      isBlocked: true,
      reason: 'PRIVACY NOTICE: Aadhaar number detected. For your safety, do not submit national ID numbers in complaint text.'
    };
  }

  // 3. OTP or Password patterns
  if (/\botp\b\W{0,4}\d{4,8}\b/i.test(text) || /\b(password|passcode|pin)\s*(is|:|=)\s*\S+/i.test(text)) {
    return {
      isBlocked: true,
      reason: 'SECURITY ALERT: Password or OTP value detected. Never disclose authentication credentials.'
    };
  }

  // 4. 12 or 24-word seed phrase detector (BIP-39 style word list)
  const tokens = text
    .split(/\s+/)
    .map((w) => w.replace(/^[\d.)\-:,]+/, '').toLowerCase())
    .filter((w) => /^[a-z]{3,12}$/.test(w));

  if (tokens.length >= 12) {
    // Check sliding windows of 12 words
    for (let i = 0; i <= tokens.length - 12; i++) {
      const windowWords = tokens.slice(i, i + 12);
      const commonCount = windowWords.filter((w) => COMMON_ENGLISH_WORDS.has(w)).length;
      // If fewer than 25% are standard prose connector words, it is likely a BIP-39 seed phrase
      if (commonCount / 12 <= 0.25) {
        return {
          isBlocked: true,
          reason: 'Never share your 12 or 24-word seed phrase. Legitimate recovery and law enforcement officers will never ask for this.'
        };
      }
    }
  }

  return { isBlocked: false };
}
