const encoder = new TextEncoder();

export function hex(bytes: ArrayBuffer | Uint8Array): string {
  return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export async function sha256(value: string | ArrayBuffer): Promise<string> {
  const data = typeof value === 'string' ? encoder.encode(value) : value;
  return hex(await crypto.subtle.digest('SHA-256', data));
}

export function randomToken(bytes = 32): string {
  const data = crypto.getRandomValues(new Uint8Array(bytes));
  return btoa(String.fromCharCode(...data)).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '');
}

function b64url(bytes: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(bytes))).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '');
}

async function hmac(secret: string, value: string): Promise<string> {
  const key = await crypto.subtle.importKey('raw', encoder.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return b64url(await crypto.subtle.sign('HMAC', key, encoder.encode(value)));
}

export function secureEqual(left: string, right: string): boolean {
  const size = Math.max(left.length, right.length);
  let difference = left.length ^ right.length;
  for (let index = 0; index < size; index++) difference |= (left.charCodeAt(index) || 0) ^ (right.charCodeAt(index) || 0);
  return difference === 0;
}

export async function createSessionCookie(secret: string, username: string, now = Date.now()): Promise<string> {
  const payload = btoa(JSON.stringify({ sub: username, exp: now + 12 * 60 * 60 * 1000 })).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '');
  return `${payload}.${await hmac(secret, payload)}`;
}

export async function verifySessionCookie(secret: string, token?: string): Promise<boolean> {
  if (!token) return false;
  const [payload, signature, extra] = token.split('.');
  if (!payload || !signature || extra || !secureEqual(signature, await hmac(secret, payload))) return false;
  try {
    const normalized = payload.replaceAll('-', '+').replaceAll('_', '/').padEnd(Math.ceil(payload.length / 4) * 4, '=');
    const value = JSON.parse(atob(normalized)) as { exp?: number };
    return typeof value.exp === 'number' && value.exp > Date.now();
  } catch { return false; }
}

export function normalizeName(value: string): string {
  return value.normalize('NFKC').replace(/\s/gu, '').toUpperCase();
}

export function stableJson(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${stableJson(object[key])}`).join(',')}}`;
}
