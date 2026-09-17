# Cloudflare replacement PoC

This directory is an isolated replacement for the Streamlit + Supabase application. The existing Python application and production data are not modified.

## Preserved behavior

- Administrator login and private dashboard
- Contract creation with PDF upload and SHA-256 integrity record
- Company and signer parties (`cs_parties`)
- One-time, expiring signing URL; only the SHA-256 token hash is stored
- NFKC signer-name verification and explicit consent
- Original PDF integrity verification before signing
- Footer stamp on every page, appended completion certificate, and private downloads
- Global `previous_hash -> record_hash` audit chain protected from concurrent forks by a unique predecessor constraint
- Draft, sent, signed, and void lifecycle

The PoC intentionally does not migrate or connect to production Supabase. Email delivery is also kept out of the acceptance path: the admin receives a one-time signing URL and can pass it through the existing operational channel. An email provider can be added after the core flow is accepted.

## Local verification

1. Copy `.dev.vars.example` to `.dev.vars` and replace both values.
2. Run `npm ci`, `npm run db:migrate:local`, then `npm run dev`.
3. In another terminal serve the Pages UI with `npx wrangler pages dev frontend --port 8788 --proxy 8787`.
4. Open `http://localhost:8788`, create a test contract, issue its URL, and complete the signature.

Local Wrangler uses local D1 and R2 state under `.wrangler/`; it does not touch production services.

## Cloudflare setup

1. Create D1 database `contract-service-poc` and R2 bucket `contract-service-poc`.
2. Put the returned D1 ID in `wrangler.jsonc`.
3. Set `APP_ORIGIN` to the Pages production URL. Remove the local default admin username if a different name is desired.
4. Add encrypted Worker secrets with `wrangler secret put ADMIN_PASSWORD` and `wrangler secret put SESSION_SECRET` (32+ random bytes).
5. Apply migrations, deploy the Worker, replace the Worker hostname in `frontend/_redirects`, and deploy `frontend` as a Pages project.
6. Add `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` as GitHub Actions secrets. The workflow verifies every change and deploys pushes to this PoC branch.

Do not add production Supabase credentials or real contract data. The committed historical `DEPLOYMENT.md` contains legacy operational values and must not be reused for the PoC; rotate any value that is still active before production use.

## Secrets and boundaries

- D1 and R2 are accessed through bindings, not access keys.
- PDF objects have no public R2 URL; authenticated API routes or the live signing token proxy them.
- Admin sessions are HMAC-signed, `HttpOnly`, `Secure`, `SameSite=Strict`, and expire after 12 hours.
- Raw signing tokens are returned once and never persisted.
- This is a functional PoC, not a legal determination about electronic-signature enforceability.
