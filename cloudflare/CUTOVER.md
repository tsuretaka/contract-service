# Contract service cutover record

Last verified: 2026-09-17 (Asia/Tokyo)

Cutover status: complete. The `contract-service` Streamlit Community Cloud app was deleted after the final source-delta check. Its former URL now resolves to Streamlit's not-found page. The GitHub repository and the shared Supabase project were retained.

## Migration result

- 25 legacy contracts: 3 draft, 8 sent, 13 signed, and 1 void
- 50 parties, 21 signing sessions, and 58 legacy audit events
- 47 Storage objects (6,623,647 bytes) copied to private R2 keys below `legacy/contracts/`
- D1 foreign-key check returned no violations
- Source and destination counts matched after import; a second source check found no post-export changes
- Representative original, signed, and certificate PDFs matched the Supabase objects byte for byte
- The deployed dashboard displayed all 25 legacy contracts and all 58 legacy audit events

The import backup, source export, and detailed reports are operator records and must not be committed.

## Preserved source anomalies

Five predecessor links in the legacy audit history do not form a continuous chain. The same five discontinuities exist in Supabase, so the migration preserved the source hashes and did not rewrite historical evidence.

One signed test contract (`6dfe9342-4e8e-4d9d-bfde-15cc3b116970`) has no signed PDF or certificate in the source bucket. The destination therefore exposes only its original PDF.

## Required decisions before disabling the old application

- Email delivery is not implemented in the Cloudflare application. Signing URLs must be copied from the dashboard and sent through an existing communication channel until a provider is configured.
- Eight legacy contracts remain in `sent` status. Their old tokens are revoked in Cloudflare; reissue a URL only for contracts that are still operationally valid.
- Confirm whether the `pages.dev` URL is acceptable or configure the production custom domain.
- Confirm the shared administrator credential and store it in the organization password manager.

## Safe cutover sequence

1. Stop creating or updating contracts in the Streamlit application.
2. Recheck the four source table counts and newest audit timestamp. If they changed, rerun the idempotent import and verification.
3. Verify administrator login, one migrated PDF download, the audit page, and a fresh test signing flow on Cloudflare.
4. Decide how signing URLs will be delivered and review the eight legacy `sent` contracts.
5. Switch users/bookmarks to the Cloudflare URL.
6. Disable only the Streamlit contract application. Do not pause the Supabase project because it also hosts unrelated services.
7. Keep the Supabase contract tables and bucket read-only as a rollback archive for an agreed retention period. Restrict the public bucket only after confirming no active old signing URLs are required.
