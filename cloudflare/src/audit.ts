import { sha256, stableJson } from './crypto';
import type { Env } from './types';

export interface AuditInput {
  contractId: string | null; actorType: 'admin' | 'signer' | 'system'; actorReference?: string | null;
  eventType: string; ip?: string | null; userAgent?: string | null; metadata?: Record<string, unknown> | null;
}

export async function auditHash(previousHash: string, input: AuditInput, occurredAt: string): Promise<string> {
  const metadata = { ip: input.ip ?? null, ua: input.userAgent ?? null, ref: input.actorReference ?? null, meta: input.metadata ?? null };
  return sha256(`${previousHash}|${input.contractId ?? 'None'}|${input.actorType}|${input.eventType}|${occurredAt}|${stableJson(metadata)}`);
}

export async function recordAudit(env: Env, input: AuditInput): Promise<{ id: string; recordHash: string; previousHash: string; occurredAt: string }> {
  for (let attempt = 0; attempt < 4; attempt++) {
    const last = await env.DB.prepare('SELECT record_hash FROM cs_audit_events ORDER BY occurred_at DESC, id DESC LIMIT 1').first<{ record_hash: string }>();
    const previousHash = last?.record_hash ?? '0'.repeat(64);
    const id = crypto.randomUUID();
    const occurredAt = new Date().toISOString();
    const recordHash = await auditHash(previousHash, input, occurredAt);
    try {
      await env.DB.prepare(`INSERT INTO cs_audit_events
        (id, contract_id, actor_type, actor_reference, event_type, occurred_at, ip_address, user_agent, metadata_json, previous_hash, record_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`).bind(
        id, input.contractId, input.actorType, input.actorReference ?? null, input.eventType, occurredAt,
        input.ip ?? null, input.userAgent ?? null, input.metadata ? stableJson(input.metadata) : null, previousHash, recordHash
      ).run();
      return { id, recordHash, previousHash, occurredAt };
    } catch (error) {
      if (!String(error).toLowerCase().includes('unique') || attempt === 3) throw error;
    }
  }
  throw new Error('Could not append audit event');
}
