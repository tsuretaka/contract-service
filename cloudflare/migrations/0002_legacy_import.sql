ALTER TABLE cs_contracts ADD COLUMN source_system TEXT NOT NULL DEFAULT 'cloudflare';
ALTER TABLE cs_signing_sessions ADD COLUMN revoked_at TEXT;

CREATE TABLE cs_legacy_audit_events (
  id TEXT PRIMARY KEY,
  contract_id TEXT,
  actor_type TEXT NOT NULL,
  actor_reference TEXT,
  event_type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  ip_address TEXT,
  user_agent TEXT,
  metadata_json TEXT,
  previous_hash TEXT NOT NULL,
  record_hash TEXT NOT NULL UNIQUE,
  source_system TEXT NOT NULL DEFAULT 'legacy_supabase'
);

CREATE INDEX idx_legacy_audit_contract ON cs_legacy_audit_events(contract_id);
CREATE INDEX idx_legacy_audit_time ON cs_legacy_audit_events(occurred_at DESC, id DESC);

CREATE TABLE cs_migration_runs (
  id TEXT PRIMARY KEY,
  source_system TEXT NOT NULL,
  source_digest TEXT NOT NULL UNIQUE,
  exported_at TEXT NOT NULL,
  imported_at TEXT NOT NULL,
  contract_count INTEGER NOT NULL,
  party_count INTEGER NOT NULL,
  session_count INTEGER NOT NULL,
  audit_count INTEGER NOT NULL,
  object_count INTEGER NOT NULL
);
