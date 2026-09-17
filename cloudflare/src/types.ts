export interface Env {
  DB: D1Database;
  CONTRACTS: R2Bucket;
  APP_ORIGIN: string;
  ADMIN_USERNAME: string;
  ADMIN_PASSWORD: string;
  SESSION_SECRET: string;
  SIGNING_VALID_DAYS: string;
  MAX_PDF_BYTES: string;
  PDF_FONT_KEY: string;
}

export interface ContractRow {
  id: string; title: string; status: 'draft' | 'sent' | 'signed' | 'void';
  pdf_path: string; pdf_sha256: string; signed_pdf_path: string | null;
  certificate_path: string | null; created_at: string; sent_at: string | null;
  signed_at: string | null; voided_at: string | null; source_system: string;
}

export interface PartyRow { id: string; contract_id: string; role: 'company' | 'signer'; name: string; email: string | null; created_at: string }
export interface SessionRow { id: string; contract_id: string; signer_party_id: string; token_hash: string; expires_at: string; processing_at: string | null; used_at: string | null; revoked_at: string | null; created_at: string }
