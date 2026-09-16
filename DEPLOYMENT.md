# Streamlit Community Cloud デプロイガイド（既存環境）

既存のStreamlit + Supabase本番を保守する場合の設定項目です。実値をリポジトリへコミットせず、Streamlit CloudのSecrets画面で設定してください。

```toml
[general]

DATABASE_URL = "<SUPABASE_POSTGRES_CONNECTION_STRING>"
SUPABASE_URL = "<SUPABASE_PROJECT_URL>"
SUPABASE_KEY = "<SUPABASE_PUBLISHABLE_OR_LEGACY_ANON_KEY>"
SUPABASE_BUCKET = "contracts"

BASE_URL = "https://<STREAMLIT_APP_HOSTNAME>"

ADMIN_USERNAME = "<ADMIN_USERNAME>"
ADMIN_PASSWORD = "<STRONG_UNIQUE_PASSWORD>"

SMTP_HOST = "<SMTP_HOST>"
SMTP_PORT = 465
SMTP_USER = "<SMTP_USERNAME>"
SMTP_PASSWORD = "<SMTP_PASSWORD>"
NOTIFICATION_EMAIL = "<ADMIN_NOTIFICATION_EMAIL>"
```

## セキュリティ注意事項

- 認証情報をGitへ保存しないでください。
- Supabaseの公開クライアント向けキー以外をブラウザへ露出しないでください。
- 過去版に実値を保存したことがある場合、ファイル編集だけではGit履歴から消えません。該当する認証情報をローテーションし、必要なら履歴除去を別作業として実施してください。
- Cloudflare PoCの設定は `cloudflare/README.md` を参照してください。PoCへ既存のSupabaseまたはSMTP認証情報をコピーしないでください。
