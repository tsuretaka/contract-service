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
    const head = await env.DB.prepare('SELECT head_hash FROM cs_audit_chain_head WHERE id = 1').first<{ head_hash: string }>();
    if (!head) throw new Error('Audit chain head is missing');
    const id = crypto.randomUUID();
    const occurredAt = new Date().toISOString();
    const recordHash = await auditHash(head.head_hash, input, occurredAt);
    try {
      await env.DB.prepare(`INSERT INTO cs_audit_events
        (id, contract_id, actor_type, actor_reference, event_type, occurred_at, ip_address, user_agent, metadata_json, previous_hash, record_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`).bind(
        id, input.contractId, input.actorType, input.actorReference ?? null, input.eventType, occurredAt,
        input.ip ?? null, input.userAgent ?? null, input.metadata ? stableJson(input.metadata) : null, head.head_hash, recordHash
      ).run();
      return { id, recordHash, previousHash: head.head_hash, occurredAt };
    } catch (error) {
      if (!String(error).includes('audit_chain_conflict') || attempt === 3) throw error;
    }
  }
  throw new Error('Could not append audit event');
}
