import { describe, expect, it } from 'vitest';
import { createSessionCookie, normalizeName, sha256, stableJson, verifySessionCookie } from '../src/crypto';
import { auditHash } from '../src/audit';

describe('security primitives', () => {
  it('matches the SHA-256 standard vector', async () => {
    expect(await sha256('abc')).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  });
  it('normalizes the signer name like the Python implementation', () => {
    expect(normalizeName(' Ａｋａ　Ｍｉｎｅ ')).toBe('AKAMINE');
  });
  it('sorts nested metadata deterministically', () => {
    expect(stableJson({ z: 1, a: { y: 2, x: 3 } })).toBe('{"a":{"x":3,"y":2},"z":1}');
  });
  it('rejects tampered and expired admin sessions', async () => {
    const token = await createSessionCookie('a-secret-at-least-32-characters!', 'admin');
    expect(await verifySessionCookie('a-secret-at-least-32-characters!', token)).toBe(true);
    expect(await verifySessionCookie('a-secret-at-least-32-characters!', `${token}x`)).toBe(false);
    const expired = await createSessionCookie('a-secret-at-least-32-characters!', 'admin', Date.now() - 13 * 60 * 60 * 1000);
    expect(await verifySessionCookie('a-secret-at-least-32-characters!', expired)).toBe(false);
  });
  it('includes previous hash and canonical metadata in the audit hash', async () => {
    const input = { contractId: 'c1', actorType: 'admin' as const, actorReference: 'admin', eventType: 'created', metadata: { b: 2, a: 1 } };
    expect(await auditHash('0'.repeat(64), input, '2026-01-01T00:00:00.000Z')).toHaveLength(64);
    expect(await auditHash('0'.repeat(64), input, '2026-01-01T00:00:00.000Z')).not.toBe(await auditHash('1'.repeat(64), input, '2026-01-01T00:00:00.000Z'));
  });
});
