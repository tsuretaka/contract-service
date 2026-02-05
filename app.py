import streamlit as st
import services
import pandas as pd
import os

# Page Config
st.set_page_config(page_title="Minimal e-Contract", layout="wide")

# --- Session Management ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def login():
    st.session_state['logged_in'] = True

def logout():
    st.session_state['logged_in'] = False

# --- Views ---

def show_login_view():
    st.markdown("""
    # 📑 Minimal E-Contract Service
    ### 安全・迅速な電子契約プラットフォーム
    
    契約書の作成、送信、署名、そして監査ログによる証拠保全まで。  
    すべてをワンストップで管理するミニマルな電子契約サービスです。
    """)
    
    st.divider()
    
    st.subheader("🔐 管理者ログイン")
    st.caption("※ここは管理者専用のポータルです。署名依頼を受け取った方は、メール内のリンクから直接アクセスしてください。")
    
    with st.form("login_form"):
        username = st.text_input("ユーザー名")
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン", type="primary")
        
        if submitted:
            # Secure Login via Env/Secrets
            from utils import get_env_or_secret
            
            valid_user = get_env_or_secret("ADMIN_USERNAME", "admin") # Fallback to admin/admin ONLY if not set (development convenience)
            valid_pass = get_env_or_secret("ADMIN_PASSWORD", "admin")
            
            if username == valid_user and password == valid_pass:
                login()
                st.rerun()
            else:
                st.error("❌ ユーザー名またはパスワードが間違っています")

def show_admin_dashboard():
    # --- Sidebar Menu ---
    with st.sidebar:
        st.header(f"管理画面 ({st.session_state.get('username', 'Admin')})")
        menu = st.radio("メニュー", ["契約一覧", "新規契約作成", "監査ログ"])
        
        st.divider()
        if st.button("ログアウト"):
            logout()
            st.rerun()

        # --- System Status (Debug) ---
        st.divider()
        st.caption("System Status")
        
        # Check DB
        from models import SessionLocal
        from sqlalchemy import text
        try:
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
            st.sidebar.success("Database: Connected")
        except Exception as e:
            st.sidebar.error(f"Database: API Error - {e}")
        
        # Check Storage
        from utils import supabase
        if supabase:
            st.sidebar.success("Storage: Configured")
        else:
            st.sidebar.error("Storage: Not Configured (Key Missing)")

    if menu == "契約一覧":
        show_contract_list()
    elif menu == "新規契約作成":
        show_create_contract()
    elif menu == "監査ログ":
        show_audit_logs()

def show_audit_logs():
    st.title("🛡️ セキュリティ監査ログ")
    st.write("システム内の全ての重要な操作は、改ざん不可能なハッシュチェーンとして記録されています。")

    events = services.get_all_audit_events(100)
    
    if not events:
        st.info("監査ログはまだありません。")
        return

    # 簡易表示用のデータ作成
    data = []
    for e in events:
        data.append({
            "Time": e.occurred_at,
            "Actor": f"{e.actor_type} ({e.actor_reference})",
            "Event": e.event_type,
            "Contract ID": e.contract_id,
            "IP": e.ip_address,
            "Hash Prefix": e.record_hash[:10] + "..." if e.record_hash else "N/A"
        })
    
    st.dataframe(pd.DataFrame(data), use_container_width=True)

    # 詳細検査（Raw Data & Chain Verification）
    st.subheader("チェーン詳細検査")
    
    # Select box to choose event by ID/Time for better UX than typing index
    event_options = {f"{e.occurred_at} - {e.event_type} ({e.id[:8]})": e for e in events}
    selected_option = st.selectbox("詳細を確認するイベントを選択", list(event_options.keys()))
    
    if selected_option:
        e = event_options[selected_option]
        with st.container(border=True):
            st.markdown(f"#### Event ID: `{e.id}`")
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Timestamp:**", convert_to_jst(e.occurred_at))
                st.write("**Actor:**", e.actor_type, e.actor_reference)
                st.write("**Event:**", e.event_type)
            with col2:
                st.write("**IP:**", e.ip_address)
                st.write("**User Agent:**", e.user_agent)
            
            st.divider()
            
            st.markdown("#### 🔗 Hash Chain Integrity")
            st.caption("各レコードは直前のレコードのハッシュを含んで計算されており、改ざんを検知できます。")
            st.code(f"Previous Hash: {e.previous_hash}", language="text")
            st.code(f"Current Hash:  {e.record_hash}", language="text")
            
            if e.metadata_json:
                st.markdown("#### 📄 Metadata")
                st.json(e.metadata_json)

# Helper for Timezone
from datetime import datetime
import pytz

def convert_to_jst(dt):
    """Convert UTC datetime to JST."""
    if dt is None:
        return None
    # Ensure dt is aware. If naive, assume UTC.
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(pytz.timezone('Asia/Tokyo'))

def get_status_badge(status):
    """Return status badge configuration."""
    if status == 'draft':
        return "⚪ 下書き"
    elif status == 'sent':
        return "🟡 送信済み"
    elif status == 'signed':
        return "🟢 締結完了"
    elif status == 'void':
        return "🔴 破棄"
    return status

def show_contract_list():
    st.title("📄 契約書一覧")
    
    contracts = services.list_contracts()
    
    if not contracts:
        st.info("まだ契約書がありません。")
        return

    # Convert to DataFrame for display
    data = []
    for c in contracts:
        # Parties info
        signer = next((p for p in c.parties if p.role == 'signer'), None)
        signer_name = signer.name if signer else "Unknown"
        
        data.append({
            "ID": c.id,
            "Title": c.title,
            "Status": get_status_badge(c.status),
            "Signer": signer_name,
            "Created": convert_to_jst(c.created_at),
            "Signed": convert_to_jst(c.signed_at)
        })
    
    df = pd.DataFrame(data)
    
    # Rich Table Display
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "ID": st.column_config.TextColumn("ID", width="small", help="契約ID"),
            "Title": st.column_config.TextColumn("タイトル", width="large"),
            "Status": st.column_config.TextColumn("ステータス", width="small"),
            "Signer": "署名者",
            "Created": st.column_config.DatetimeColumn("作成日", format="YYYY/MM/DD HH:mm"),
            "Signed": st.column_config.DatetimeColumn("署名日", format="YYYY/MM/DD HH:mm"),
        },
        hide_index=True
    )

    # Detail View
    st.markdown("---")
    st.subheader("📋 詳細アクション")
    
    # Improve Selection UX
    contract_options = {f"[{get_status_badge(c.status)}] {c.title} ({c.id[:8]})": c.id for c in contracts}
    selected_label = st.selectbox("操作する契約書を選択:", list(contract_options.keys()))
    selected_id = contract_options[selected_label]
    
    if selected_id:
        detail = services.get_contract_details(selected_id)
        
        # Detail Card
        with st.container(border=True):
            # Header
            col_head1, col_head2 = st.columns([3, 1])
            with col_head1:
                st.markdown(f"### {detail.title}")
                st.caption(f"ID: {detail.id}")
            with col_head2:
                st.markdown(f"**ステータス**")
                st.write(get_status_badge(detail.status))

            st.divider()

            # Body
            col_body1, col_body2 = st.columns(2)
            with col_body1:
                st.markdown("#### 📎 文書情報")
                # Handle display name for Supabase paths
                disp_name = os.path.basename(detail.pdf_path)
                if "supabase://" in detail.pdf_path:
                     disp_name = detail.pdf_path.split("/")[-1] # Simple extraction
                
                created_jst = convert_to_jst(detail.created_at)
                st.write(f"**PDF:** `{disp_name}`")
                st.write(f"**作成日時:** {created_jst.strftime('%Y/%m/%d %H:%M')}")
            
            with col_body2:
                st.markdown("#### 👥 関係者")
                for p in detail.parties:
                    role_icon = "🏢" if p.role == 'company' else "✍️"
                    st.write(f"{role_icon} **{p.role.capitalize()}**: {p.name}")
                    if p.email:
                        st.caption(f"📧 {p.email}")
            
            st.divider()
            
            # Action Area
            st.markdown("#### ⚙️ アクション")
            
            if detail.status == 'draft':
                col_act1, col_act2 = st.columns([2, 1])
                
                with col_act1:
                    # Send Button with Config
                    with st.popover("📧 契約書を送信（URL発行）", use_container_width=True):
                        st.subheader("送信設定")
                        st.write("有効期限を設定して署名用URLを発行します。")
                        valid_days = st.number_input(
                            "有効期限（日）", 
                            min_value=1, 
                            max_value=365, 
                            value=7, 
                            step=1, 
                            key=f"days_{detail.id}"
                        )
                        st.caption("※ 発行されたURLをメール等で相手方に送付してください。")
                        
                        if st.button("URLを発行する", key=f"confirm_send_{detail.id}", type="primary"):
                            email_body = services.send_contract(detail.id, valid_days=valid_days)
                            if email_body:
                                st.success("✅ 署名用URLを発行しました！")
                                st.code(email_body, language="text")
                            else:
                                st.error("送信に失敗しました")
                
                with col_act2:
                    with st.popover("🗑️ 契約書を破棄"):
                        st.warning("この操作は取り消せません。")
                        if st.button("本当に破棄する", key=f"void_{detail.id}", type="primary"):
                            if services.void_contract_service(detail.id):
                                st.toast("契約書を破棄しました")
                                st.rerun()

            elif detail.status == 'signed':
                st.success("✅ 署名が完了しています。")
                
                col_dl1, col_dl2 = st.columns(2)
                
                # Dynamic merging logic
                # Dynamic merging logic
                merged_path = services.get_signed_contract_path(detail.id)
                cert_path = services.get_certificate_path(detail.id)
                
                # Ensure we have the ORIGINAL file locally (download if needed)
                from utils import download_file_to_temp
                try:
                    local_original_path = download_file_to_temp(detail.pdf_path)
                except Exception as e:
                    local_original_path = None
                    st.error(f"Failed to retrieve original PDF: {e}")

                # Check/Create merged file
                # Only if we have both original and cert locally
                if not os.path.exists(merged_path) and local_original_path and os.path.exists(local_original_path) and os.path.exists(cert_path):
                     from utils import merge_pdf_with_certificate
                     merge_pdf_with_certificate(local_original_path, cert_path, merged_path)

                with col_dl1:
                    if os.path.exists(merged_path):
                        with open(merged_path, "rb") as f:
                            st.download_button(
                                "📥 契約書+証明書 (統合版)",
                                f,
                                file_name=f"signed_{os.path.basename(detail.pdf_path)}",
                                mime="application/pdf",
                                key=f"dl_merged_{detail.id}",
                                use_container_width=True
                            )
                    elif local_original_path and os.path.exists(local_original_path):
                         # Fallback: Original Only
                         with open(local_original_path, "rb") as f:
                            st.download_button(
                                "📄 契約書PDF (未結合)",
                                f,
                                file_name=os.path.basename(local_original_path),
                                mime="application/pdf",
                                key=f"dl_pdf_fallback_{detail.id}",
                                use_container_width=True
                            )
                
                with col_dl2:
                    if os.path.exists(cert_path):
                        with open(cert_path, "rb") as f:
                            st.download_button(
                                "🎖️ 証明書のみ",
                                f,
                                file_name=f"certificate_{detail.id}.pdf",
                                mime="application/pdf",
                                key=f"dl_cert_{detail.id}",
                                use_container_width=True
                            )
            
            elif detail.status == 'void':
                st.error("⛔️ この契約書は破棄されています。")

def show_create_contract():
    st.title("➕ 新規契約作成")
    
    with st.form("create_contract"):
        title = st.text_input("契約書タイトル", "〇〇業務委託契約書")
        company_name = st.text_input("自社名 (甲)", "株式会社Example")
        
        st.subheader("相手方情報 (乙)")
        signer_name = st.text_input("相手方 氏名/会社名")
        signer_email = st.text_input("相手方 メールアドレス")
        
        uploaded_file = st.file_uploader("契約書PDFをアップロード", type=["pdf"])
        
        submitted = st.form_submit_button("作成する")
        
        if submitted:
            if not title or not signer_name or not uploaded_file:
                st.error("必須項目を入力してください")
            else:
                try:
                    contract = services.create_contract(
                        title=title,
                        company_name=company_name,
                        signer_name=signer_name,
                        signer_email=signer_email,
                        uploaded_file=uploaded_file
                    )
                    st.success(f"契約書「{contract.title}」を作成しました！")
                except Exception as e:
                    st.error(f"作成エラー: {e}")

# --- Main Routing ---
def main():
    # Check for Signing URL (Query Params) -- Phase 3
    # Use st.query_params (New API)
    params = st.query_params
    token = params.get("token")
    
    if token:
        show_signing_view(token)
    else:
        # Standard Admin Flow
        if st.session_state['logged_in']:
            show_admin_dashboard()
        else:
            show_login_view()

# --- Signing View (Phase 3) ---

def show_signing_view(token):
    # Note: page config cannot be set twice, but layout changes might be needed.
    # We ignore setting page config here as it is set at top.
    
    contract, session, signer = services.validate_token(token)
    
    if not contract:
        st.error("❌ 無効なリンクか、有効期限が切れています。")
        return

    st.title("✍️ 電子契約書の署名")
    st.info(f"契約書: {contract.title}")
    
    st.markdown("### 1. 契約内容の確認")
    st.write("以下のPDF内容をよくご確認ください。")
    
    # PDF Display (Embedded)
    # Streamlit's native PDF display via iframe or base64
    import base64
    from utils import download_file_to_temp
    
    # Ensure we have a local path (Download if Supabase)
    local_pdf_path = download_file_to_temp(contract.pdf_path)
    
    with open(local_pdf_path, "rb") as f:
        pdf_bytes = f.read()
        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    
    # Download Button (Fail-safe)
    st.download_button(
        label="📄 契約書PDFをダウンロード",
        data=pdf_bytes,
        file_name=f"{contract.title}.pdf",
        mime='application/pdf'
    )

    # PDF Display using streamlit-pdf-viewer (Better cross-browser support including Safari)
    from streamlit_pdf_viewer import pdf_viewer
    
    # annotations (optional) could be added here later
    pdf_viewer(input=pdf_bytes, width=700)
    
    st.divider()
    
    st.markdown("### 2. 署名の実行")
    st.write(f"署名者: **{signer.name}** ({signer.email})")
    
    st.markdown("#### 署名者名の確認")
    st.write("本人確認のため、**契約書に登録されている署名者名（会社名または氏名）** を正確に入力してください。")
    st.caption(f"※登録名: {signer.name} （この通りに入力してください）")
    typed_name = st.text_input("署名者名", placeholder=signer.name)

    confirm = st.checkbox("私は上記契約書の内容を確認し、これに同意します。")
    
    # Validation
    is_valid = confirm and typed_name and len(typed_name) > 1
    
    if st.button("署名して完了する", type="primary", disabled=not is_valid):
        # Create Signature
        try:
            # Capture Client Info (Best Effort)
            client_ip = "Unknown IP"
            user_agent = "Unknown User-Agent"
            
            try:
                from streamlit.web.server.websocket_headers import _get_websocket_headers
                headers = _get_websocket_headers()
                if headers:
                    client_ip = headers.get("X-Forwarded-For", headers.get("Remote-Addr", "Unknown IP"))
                    user_agent = headers.get("User-Agent", "Streamlit Cloud Browser")
            except Exception as e:
                print(f"Header capture failed: {e}")
                client_ip = "Streamlit Cloud"
                user_agent = "Web Browser"

            # Pass capture info to service
            success, result_message = services.execute_signature(session.id, client_ip, user_agent, typed_name)
            
            if success:
                st.success("✅ 署名が完了しました！ありがとうございました。")
                
                # Show Anchor Information for MVP evidence
                with st.expander("🔐 セキュリティ監査情報（管理者通知）", expanded=True):
                    st.info("以下のアンカー情報が管理者に送信されました（証拠保全）")
                    st.code(result_message, language="text")
                
                st.balloons()
                # Wait a bit for user to read or manual reload
            else:
                st.error(f"署名エラー: {result_message}")
            
        except Exception as e:
            st.error(f"システムエラー: {e}")

    # If signed
    if contract.status == 'signed':
        st.success("この契約書は署名済みです。")
        col1, col2 = st.columns(2)
        with col1:
             with open(contract.pdf_path, "rb") as f:
                st.download_button(
                    label="📄 契約書PDFをダウンロード",
                    data=f,
                    file_name=os.path.basename(contract.pdf_path),
                    mime="application/pdf"
                )
        with col2:
            cert_path = services.get_certificate_path(contract.id)
            if os.path.exists(cert_path):
                with open(cert_path, "rb") as f:
                    st.download_button(
                        label="🎖️ 署名完了証明書をダウンロード",
                        data=f,
                        file_name=f"certificate.pdf",
                        mime="application/pdf"
                    )

if __name__ == "__main__":
    main()
import os
