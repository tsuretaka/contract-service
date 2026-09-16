PRAGMA foreign_keys = ON;

CREATE TABLE cs_contracts (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','sent','signed','void')),
  pdf_path TEXT NOT NULL,
  pdf_sha256 TEXT,
  signed_pdf_path TEXT,
  certificate_path TEXT,
  created_at TEXT NOT NULL,
  sent_at TEXT,
  signed_at TEXT,
  voided_at TEXT
);

CREATE TABLE cs_parties (
  id TEXT PRIMARY KEY,
  contract_id TEXT NOT NULL REFERENCES cs_contracts(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('company','signer')),
  name TEXT NOT NULL,
  email TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE cs_signing_sessions (
  id TEXT PRIMARY KEY,
  contract_id TEXT NOT NULL REFERENCES cs_contracts(id) ON DELETE CASCADE,
  signer_party_id TEXT NOT NULL REFERENCES cs_parties(id),
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  processing_at TEXT,
  used_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE cs_audit_events (
  id TEXT PRIMARY KEY,
  contract_id TEXT REFERENCES cs_contracts(id) ON DELETE SET NULL,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('admin','signer','system')),
  actor_reference TEXT,
  event_type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  ip_address TEXT,
  user_agent TEXT,
  metadata_json TEXT,
  previous_hash TEXT NOT NULL,
  record_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE cs_audit_chain_head (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  head_hash TEXT NOT NULL
);
INSERT INTO cs_audit_chain_head (id, head_hash) VALUES (1, printf('%064d', 0));

CREATE TRIGGER cs_audit_chain_guard
BEFORE INSERT ON cs_audit_events
BEGIN
  SELECT CASE WHEN NEW.previous_hash != (SELECT head_hash FROM cs_audit_chain_head WHERE id = 1)
    THEN RAISE(ABORT, 'audit_chain_conflict') END;
END;

CREATE TRIGGER cs_audit_chain_advance
AFTER INSERT ON cs_audit_events
BEGIN
  UPDATE cs_audit_chain_head SET head_hash = NEW.record_hash WHERE id = 1;
END;

CREATE INDEX idx_parties_contract ON cs_parties(contract_id);
CREATE INDEX idx_sessions_contract ON cs_signing_sessions(contract_id);
CREATE INDEX idx_sessions_token ON cs_signing_sessions(token_hash);
CREATE INDEX idx_audit_contract ON cs_audit_events(contract_id);
CREATE INDEX idx_audit_time ON cs_audit_events(occurred_at DESC, id DESC);
