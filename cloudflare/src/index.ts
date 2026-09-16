import { createSessionCookie, normalizeName, sha256, verifySessionCookie, randomToken, secureEqual } from './crypto';
import { recordAudit } from './audit';
import { createSignedArtifacts } from './pdf';
import type { ContractRow, Env, PartyRow, SessionRow } from './types';

const json = (body: unknown, status = 200, headers: HeadersInit = {}) => new Response(JSON.stringify(body), {
  status, headers: { 'content-type': 'application/json; charset=utf-8', ...headers }
});
const error = (message: string, status = 400) => json({ error: message }, status);
const cookieValue = (request: Request, name: string) => request.headers.get('cookie')?.split(';').map(v => v.trim()).find(v => v.startsWith(`${name}=`))?.slice(name.length + 1);
const adminCookie = (value: string, maxAge = 43200) => `cs_admin=${value}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${maxAge}`;
const clientIp = (request: Request) => request.headers.get('cf-connecting-ip') ?? request.headers.get('x-forwarded-for') ?? 'unknown';

async function requireAdmin(request: Request, env: Env): Promise<Response | null> {
  return await verifySessionCookie(env.SESSION_SECRET, cookieValue(request, 'cs_admin')) ? null : error('Authentication required', 401);
}

async function getContractBundle(env: Env, id: string) {
  const contract = await env.DB.prepare('SELECT * FROM cs_contracts WHERE id = ?').bind(id).first<ContractRow>();
  if (!contract) return null;
  const parties = (await env.DB.prepare('SELECT * FROM cs_parties WHERE contract_id = ? ORDER BY created_at').bind(id).all<PartyRow>()).results;
  return { ...contract, parties };
}

async function tokenBundle(env: Env, token: string, allowUsed = false) {
  const tokenHash = await sha256(token);
  const session = await env.DB.prepare('SELECT * FROM cs_signing_sessions WHERE token_hash = ?').bind(tokenHash).first<SessionRow>();
  if (!session || (!allowUsed && session.used_at) || session.expires_at <= new Date().toISOString()) return null;
  const contract = await getContractBundle(env, session.contract_id);
  const signer = contract?.parties.find(p => p.id === session.signer_party_id);
  return contract && signer ? { session, contract, signer } : null;
}

async function login(request: Request, env: Env) {
  const input = await request.json().catch(() => ({})) as { username?: string; password?: string };
  const validUser = input.username === env.ADMIN_USERNAME;
  const supplied = await sha256(input.password ?? '');
  const expected = await sha256(env.ADMIN_PASSWORD);
  if (!validUser || !secureEqual(supplied, expected)) return error('Invalid username or password', 401);
  const token = await createSessionCookie(env.SESSION_SECRET, input.username!);
  return json({ ok: true }, 200, { 'set-cookie': adminCookie(token), 'cache-control': 'no-store' });
}

async function createContract(request: Request, env: Env) {
  const form = await request.formData();
  const file = form.get('pdf');
  const title = String(form.get('title') ?? '').trim();
  const companyName = String(form.get('companyName') ?? '').trim();
  const signerName = String(form.get('signerName') ?? '').trim();
  const signerEmail = String(form.get('signerEmail') ?? '').trim().toLowerCase();
  if (!(file instanceof File) || !title || !companyName || !signerName || !/^\S+@\S+\.\S+$/.test(signerEmail)) return error('All fields and a valid signer email are required');
  const bytes = await file.arrayBuffer();
  const max = Number(env.MAX_PDF_BYTES || 10485760);
  if (bytes.byteLength < 5 || bytes.byteLength > max || new TextDecoder().decode(bytes.slice(0, 5)) !== '%PDF-') return error(`A PDF up to ${max} bytes is required`);
  const id = crypto.randomUUID();
  const hash = await sha256(bytes);
  const objectKey = `uploads/${id}/${hash}.pdf`;
  await env.CONTRACTS.put(objectKey, bytes, { httpMetadata: { contentType: 'application/pdf' }, customMetadata: { sha256: hash, originalName: file.name.slice(0, 180) } });
  const now = new Date().toISOString();
  try {
    await env.DB.batch([
      env.DB.prepare('INSERT INTO cs_contracts (id,title,status,pdf_path,pdf_sha256,created_at) VALUES (?,?,?,?,?,?)').bind(id, title, 'draft', objectKey, hash, now),
      env.DB.prepare('INSERT INTO cs_parties (id,contract_id,role,name,email,created_at) VALUES (?,?,?,?,?,?)').bind(crypto.randomUUID(), id, 'company', companyName, null, now),
      env.DB.prepare('INSERT INTO cs_parties (id,contract_id,role,name,email,created_at) VALUES (?,?,?,?,?,?)').bind(crypto.randomUUID(), id, 'signer', signerName, signerEmail, now)
    ]);
    await recordAudit(env, { contractId: id, actorType: 'admin', actorReference: env.ADMIN_USERNAME, eventType: 'created', metadata: { filename: file.name, pdf_sha256: hash } });
  } catch (cause) {
    await env.CONTRACTS.delete(objectKey);
    throw cause;
  }
  return json(await getContractBundle(env, id), 201);
}

async function sendContract(env: Env, id: string) {
  const contract = await getContractBundle(env, id);
  const signer = contract?.parties.find(p => p.role === 'signer');
  if (!contract || !signer || contract.status !== 'draft') return error('Only a draft contract can be sent', 409);
  const rawToken = randomToken();
  const now = new Date();
  const expires = new Date(now.getTime() + Number(env.SIGNING_VALID_DAYS || 7) * 86400000);
  const result = await env.DB.batch([
    env.DB.prepare("UPDATE cs_contracts SET status='sent', sent_at=? WHERE id=? AND status='draft'").bind(now.toISOString(), id),
    env.DB.prepare('INSERT INTO cs_signing_sessions (id,contract_id,signer_party_id,token_hash,expires_at,created_at) VALUES (?,?,?,?,?,?)')
      .bind(crypto.randomUUID(), id, signer.id, await sha256(rawToken), expires.toISOString(), now.toISOString())
  ]);
  if (!result[0].meta.changes) return error('Contract state changed; reload and retry', 409);
  await recordAudit(env, { contractId: id, actorType: 'admin', actorReference: env.ADMIN_USERNAME, eventType: 'sent' });
  return json({ signingUrl: `${env.APP_ORIGIN.replace(/\/$/, '')}/sign/?token=${encodeURIComponent(rawToken)}`, expiresAt: expires.toISOString(), recipient: signer.email });
}

async function signContract(request: Request, env: Env, token: string) {
  const bundle = await tokenBundle(env, token);
  if (!bundle || bundle.contract.status !== 'sent') return error('Signing link is invalid, expired, or already used', 410);
  const input = await request.json().catch(() => ({})) as { typedName?: string; confirmed?: boolean };
  if (!input.confirmed || !input.typedName || normalizeName(input.typedName) !== normalizeName(bundle.signer.name)) return error('The confirmation and registered signer name must match', 422);
  const original = await env.CONTRACTS.get(bundle.contract.pdf_path);
  if (!original) return error('Original PDF is missing', 500);
  const originalBytes = await original.arrayBuffer();
  if (await sha256(originalBytes) !== bundle.contract.pdf_sha256) return error('Original PDF integrity check failed', 409);
  const signedAt = new Date().toISOString();
  const claim = await env.DB.prepare('UPDATE cs_signing_sessions SET processing_at=? WHERE id=? AND used_at IS NULL AND processing_at IS NULL')
    .bind(signedAt, bundle.session.id).run();
  if (!claim.meta.changes) return error('This signing link is already being processed', 409);
  const signedKey = `signed/${bundle.contract.id}/${bundle.contract.id}_signed.pdf`;
  const certificateKey = `signed/${bundle.contract.id}/${bundle.contract.id}_certificate.pdf`;
  let completed = false;
  try {
    const verificationAudit = await recordAudit(env, {
      contractId: bundle.contract.id, actorType: 'signer', actorReference: bundle.signer.email, eventType: 'signature_verified',
      ip: clientIp(request), userAgent: request.headers.get('user-agent'), metadata: { typed_name_verification: input.typedName, match_result: true }
    });
    const issuer = bundle.contract.parties.find(p => p.role === 'company');
    const artifacts = await createSignedArtifacts(originalBytes, {
      contractId: bundle.contract.id, title: bundle.contract.title, issuer: issuer?.name ?? 'N/A', signer: bundle.signer.name,
      signerEmail: bundle.signer.email ?? 'N/A', originalSha256: bundle.contract.pdf_sha256, signedAt,
      ipAddress: clientIp(request), userAgent: request.headers.get('user-agent') ?? 'unknown', auditHash: verificationAudit.recordHash
    });
    await Promise.all([
      env.CONTRACTS.put(signedKey, artifacts.signed, { httpMetadata: { contentType: 'application/pdf' } }),
      env.CONTRACTS.put(certificateKey, artifacts.certificate, { httpMetadata: { contentType: 'application/pdf' } })
    ]);
    const results = await env.DB.batch([
      env.DB.prepare('UPDATE cs_signing_sessions SET used_at=?, processing_at=NULL WHERE id=? AND used_at IS NULL AND processing_at=?').bind(signedAt, bundle.session.id, signedAt),
      env.DB.prepare("UPDATE cs_contracts SET status='signed', signed_at=?, signed_pdf_path=?, certificate_path=? WHERE id=? AND status='sent'")
        .bind(signedAt, signedKey, certificateKey, bundle.contract.id)
    ]);
    if (!results[0].meta.changes || !results[1].meta.changes) throw new Error('Signing state changed concurrently');
    const audit = await recordAudit(env, {
      contractId: bundle.contract.id, actorType: 'signer', actorReference: bundle.signer.email, eventType: 'signed',
      ip: clientIp(request), userAgent: request.headers.get('user-agent'), metadata: { verification_audit_hash: verificationAudit.recordHash, signed_pdf_path: signedKey, certificate_path: certificateKey }
    });
    completed = true;
    return json({ ok: true, contractId: bundle.contract.id, signedAt, auditHash: audit.recordHash });
  } catch (cause) {
    await Promise.allSettled([env.CONTRACTS.delete(signedKey), env.CONTRACTS.delete(certificateKey)]);
    await recordAudit(env, { contractId: bundle.contract.id, actorType: 'system', actorReference: 'worker', eventType: 'signing_failed', metadata: { reason: String(cause).slice(0, 300) } }).catch(() => undefined);
    throw cause;
  } finally {
    if (!completed) await env.DB.prepare('UPDATE cs_signing_sessions SET processing_at=NULL WHERE id=? AND processing_at=? AND used_at IS NULL').bind(bundle.session.id, signedAt).run();
  }
}

async function r2Response(env: Env, key: string | null, filename: string) {
  if (!key) return error('File is not available', 404);
  const object = await env.CONTRACTS.get(key);
  if (!object || !('body' in object)) return error('File is not available', 404);
  const headers = new Headers({ 'content-type': 'application/pdf', 'content-disposition': `inline; filename="${filename}"`, 'cache-control': 'private, no-store', etag: object.httpEtag });
  return new Response(object.body, { headers });
}

async function handle(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, '') || '/';
  if (request.method === 'OPTIONS') return new Response(null, { status: 204 });
  if (path === '/api/health') return json({ ok: true, runtime: 'cloudflare-workers' });
  if (path === '/api/auth/login' && request.method === 'POST') return login(request, env);
  if (path === '/api/auth/logout' && request.method === 'POST') return json({ ok: true }, 200, { 'set-cookie': adminCookie('', 0) });
  if (path === '/api/auth/me' && request.method === 'GET') return (await requireAdmin(request, env)) ?? json({ authenticated: true, username: env.ADMIN_USERNAME });

  const signing = path.match(/^\/api\/signing\/([^/]+)(?:\/(pdf|sign|signed-pdf|certificate))?$/);
  if (signing) {
    const token = decodeURIComponent(signing[1]);
    const action = signing[2];
    if (!action && request.method === 'GET') {
      const bundle = await tokenBundle(env, token, true);
      if (!bundle) return error('Signing link is invalid or expired', 410);
      return json({ contract: { id: bundle.contract.id, title: bundle.contract.title, status: bundle.contract.status, pdfSha256: bundle.contract.pdf_sha256 }, signer: { name: bundle.signer.name, email: bundle.signer.email }, expiresAt: bundle.session.expires_at, usedAt: bundle.session.used_at });
    }
    if (action === 'pdf' && request.method === 'GET') { const b = await tokenBundle(env, token); return b ? r2Response(env, b.contract.pdf_path, 'contract.pdf') : error('Signing link is invalid', 410); }
    if (action === 'sign' && request.method === 'POST') return signContract(request, env, token);
    if ((action === 'signed-pdf' || action === 'certificate') && request.method === 'GET') {
      const b = await tokenBundle(env, token, true);
      if (!b || !b.session.used_at) return error('Signed file is not available', 404);
      return r2Response(env, action === 'signed-pdf' ? b.contract.signed_pdf_path : b.contract.certificate_path, `${action}.pdf`);
    }
  }

  const authError = await requireAdmin(request, env);
  if (authError) return authError;
  if (path === '/api/contracts' && request.method === 'GET') {
    const contracts = (await env.DB.prepare(`SELECT c.*, p.name signer_name, p.email signer_email FROM cs_contracts c LEFT JOIN cs_parties p ON p.contract_id=c.id AND p.role='signer' ORDER BY c.created_at DESC`).all()).results;
    return json(contracts);
  }
  if (path === '/api/contracts' && request.method === 'POST') return createContract(request, env);
  if (path === '/api/audit' && request.method === 'GET') return json((await env.DB.prepare('SELECT * FROM cs_audit_events ORDER BY occurred_at DESC, id DESC LIMIT 200').all()).results);
  const contractRoute = path.match(/^\/api\/contracts\/([^/]+)(?:\/(send|void|pdf|signed-pdf|certificate))?$/);
  if (contractRoute) {
    const id = contractRoute[1], action = contractRoute[2];
    const contract = await getContractBundle(env, id);
    if (!contract) return error('Contract not found', 404);
    if (!action && request.method === 'GET') return json(contract);
    if (action === 'send' && request.method === 'POST') return sendContract(env, id);
    if (action === 'void' && request.method === 'POST') {
      if (contract.status === 'signed' || contract.status === 'void') return error('Signed or void contracts cannot be voided', 409);
      await env.DB.prepare("UPDATE cs_contracts SET status='void', voided_at=? WHERE id=?").bind(new Date().toISOString(), id).run();
      await recordAudit(env, { contractId: id, actorType: 'admin', actorReference: env.ADMIN_USERNAME, eventType: 'voided' });
      return json({ ok: true });
    }
    if (request.method === 'GET' && ['pdf', 'signed-pdf', 'certificate'].includes(action ?? '')) {
      const key = action === 'pdf' ? contract.pdf_path : action === 'signed-pdf' ? contract.signed_pdf_path : contract.certificate_path;
      return r2Response(env, key, `${action}.pdf`);
    }
  }
  return error('Not found', 404);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    try { return await handle(request, env); }
    catch (cause) { console.error(cause); return error('Internal server error', 500); }
  }
} satisfies ExportedHandler<Env>;
