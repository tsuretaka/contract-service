# Streamlit Community Cloud デプロイガイド

## Secrets設定 (TOML形式)

以下の内容をコピーして、Streamlit Cloudの「Secrets」欄に貼り付けてください。
※ `BASE_URL` は、デプロイ後に発行される実際のアプリのURL（例: `https://contract-service.streamlit.app`）に書き換えることを強く推奨します。

```toml
[general]

# --- Database ---
DATABASE_URL = "postgresql://postgres.mhslyqrqlfbmdmbwwfri:qaqjym-pyXdif-9befne@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres"

# --- Supabase Storage ---
SUPABASE_URL = "https://mhslyqrqlfbmdmbwwfri.supabase.co"
SUPABASE_KEY = "sb_publishable_wlPNQLFkj4zkXaV9wee26Q_tSAPxRG4"
SUPABASE_BUCKET = "contracts"

# --- App Config ---
# デプロイ後に実際のURL「https://xxxx.streamlit.app」に書き換えてください
BASE_URL = "https://contract-service.streamlit.app"

# --- Admin Authenticator ---
ADMIN_USERNAME = "akamine1732"
ADMIN_PASSWORD = "SecurePass_2026_Go!"

# --- Email Notifications (New) ---
SMTP_HOST = "smtp.muumuu-mail.com"
SMTP_PORT = 465
SMTP_USER = "contract-service@colt.co.jp"
SMTP_PASSWORD = "contract1732"
NOTIFICATION_EMAIL = "contract-service@colt.co.jp"
```
