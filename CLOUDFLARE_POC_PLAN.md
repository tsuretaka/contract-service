# Cloudflare PoC change plan and dependency map

## Boundary

All new runtime code lives in `cloudflare/`; the Streamlit application, Supabase database, Supabase Storage, and their production deployment remain unchanged. The PoC uses test data only.

## Dependency map

```text
GitHub branch poc/cloudflare-workers-pages
  -> GitHub Actions verification/deployment
  -> Cloudflare Pages (static admin and signer UI)
      -> Cloudflare Worker API
          -> D1: cs_contracts, cs_parties, cs_signing_sessions, cs_audit_events
          -> R2: original, signed, and certificate PDFs
          -> Secrets: admin password and session-signing secret
```

`pdf-lib` is the only production package. It stamps existing pages and appends the completion certificate inside the Workers runtime. Wrangler, TypeScript, and Vitest are development-only dependencies.

## Acceptance mapping

| Requirement | Implementation |
|---|---|
| Admin login | `/api/auth/*`, signed secure cookie |
| Create/upload | multipart API, PDF signature/size checks, SHA-256, private R2 |
| Signing URL | 256-bit token; D1 stores SHA-256 only |
| Review/sign | public token-scoped endpoints and Pages signer UI |
| Signed PDF | every page stamped; completion certificate appended |
| Integrity | original SHA-256 recomputed immediately before signing |
| Audit chain | A unique `previous_hash` prevents forks; concurrent conflicts retry from the new head |
| GitHub deployment | scoped GitHub Actions workflow |
| No sleep/wake screen | Pages/Workers request model; no Streamlit process |

## Deliberate PoC exclusions

- No production Supabase data or file migration.
- No cutover, DNS change, or deployment from this workspace.
- No SMTP credential reuse. Provider-neutral email delivery is a post-acceptance integration.
- The certificate uses the PDF standard font for a dependency-light Workers build. Japanese party text is retained in D1/UI; non-Latin glyphs in the PDF certificate are represented conservatively until a licensed Japanese font asset is selected for production.
