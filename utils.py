import pytz
from datetime import datetime

JST = pytz.timezone("Asia/Tokyo")

def to_jst(dt: datetime) -> datetime:
    """Convert any UTC (or naive UTC) datetime to JST."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(JST)

def format_jst_datetime(dt, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Convert UTC datetime to JST and format as string."""
    if dt is None:
        return "N/A"
    if isinstance(dt, str):
        return dt
    jst_dt = to_jst(dt)
    return jst_dt.strftime(fmt)

import hashlib
import os
import shutil
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

# Email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# Load env variables explicitly
load_dotenv()

# Helper to get env or secret
def get_env_or_secret(key, default=None):
    val = os.environ.get(key)
    if not val:
        try:
            import streamlit as st
            if hasattr(st, "secrets"):
                if key in st.secrets:
                    val = st.secrets[key]
                elif "general" in st.secrets and key in st.secrets["general"]:
                    val = st.secrets["general"][key]
        except:
            pass
    return val if val else default

def send_email_notification(to_email, subject, body, attachment_path=None):
    """Send email via SMTP with optional attachment."""
    smtp_host = get_env_or_secret("SMTP_HOST")
    smtp_port = get_env_or_secret("SMTP_PORT", 587)
    smtp_user = get_env_or_secret("SMTP_USER")
    smtp_password = get_env_or_secret("SMTP_PASSWORD")

    if not all([smtp_host, smtp_user, smtp_password]):
        print("⚠️ SMTP credentials missing. Email skipped.")
        return False

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    if attachment_path:
        try:
            with open(attachment_path, "rb") as f:
                # Use standard pdf name if possible
                filename = os.path.basename(attachment_path)
                part = MIMEApplication(f.read(), Name=filename)
            part['Content-Disposition'] = f'attachment; filename="{filename}"'
            msg.attach(part)
        except Exception as e:
            print(f"❌ Failed to attach file: {e}")

    try:
        if int(smtp_port) == 465:
            # SSL Connection (MuuMuu Mail etc.)
            server = smtplib.SMTP_SSL(smtp_host, int(smtp_port))
        else:
            # TLS Connection (Gmail etc.)
            server = smtplib.SMTP(smtp_host, int(smtp_port))
            server.starttls()
            
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

# Supabase Auth
SUPABASE_URL = get_env_or_secret("SUPABASE_URL")
SUPABASE_KEY = get_env_or_secret("SUPABASE_KEY")
SUPABASE_BUCKET = get_env_or_secret("SUPABASE_BUCKET", "contracts")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Supabase Init Warning: {e}")

def calculate_file_hash(filepath=None, file_content=None):
    """Calculate SHA256 hash of a file path OR bytes content."""
    sha256_hash = hashlib.sha256()
    
    if file_content:
        sha256_hash.update(file_content)
    elif filepath:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
                
    return sha256_hash.hexdigest()

def save_uploaded_file(uploaded_file, dest_dir="contracts/uploads"):
    """
    Save uploaded Streamlit file.
    If Supabase is configured, upload to Storage Bucket.
    Else, save to local disk.
    
    Returns: (path_or_key, file_hash)
    """
    file_bytes = uploaded_file.getvalue()
    file_hash = calculate_file_hash(file_content=file_bytes)
    
    if supabase:
        print(f"DEBUG: Attempting upload to Supabase Bucket: {SUPABASE_BUCKET}")
        # Upload to Supabase
        # Use Hash in filename to prevent collision/override and issues with Japanese
        # Extract extension safely
        ext = os.path.splitext(uploaded_file.name)[1]
        if not ext: ext = ".pdf" # Default
        
        filename = f"{file_hash}{ext}"
        file_path = f"uploads/{filename}" # Key in bucket
        
        try:
            # Check if exists? (Optional, but safe)
            # Just overwrite for now or ignore error
            print(f"DEBUG: Uploading {file_path}...")
            supabase.storage.from_(SUPABASE_BUCKET).upload(
                path=file_path,
                file=file_bytes,
                file_options={"content-type": uploaded_file.type, "upsert": "true"}
            )
            print("DEBUG: Upload Success!")
            # Prefix with 'supabase://' to distinguish later
            return f"supabase://{SUPABASE_BUCKET}/{file_path}", file_hash
            
        except Exception as e:
            # Fallback to local if upload fails? No, raise error in Prod.
            print(f"DEBUG: Upload failed: {e}")
            raise e
    else:
        print("DEBUG: Supabase client NOT initialized. Saving locally.")
        # Local Local
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        
        file_path = os.path.join(dest_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        
        return file_path, file_hash

def upload_local_file_to_storage(local_path, remote_folder="signed", use_hash_name=False):
    """
    Upload a local file to Supabase Storage.
    Returns the supabase:// path if successful, otherwise raises or returns local path?
    Since we want persistence, we should probably enforce upload if supabase is active.
    """
    if not supabase:
        return local_path # Local mode
        
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"File not found: {local_path}")
        
    filename = os.path.basename(local_path)
    ext = os.path.splitext(filename)[1]
    if not ext: ext = ".pdf"
    
    if use_hash_name:
        file_hash = calculate_file_hash(local_path)
        remote_filename = f"{file_hash}{ext}"
    else:
        remote_filename = filename
    
    # Remote Path
    remote_path = f"{remote_folder}/{remote_filename}"
    
    print(f"DEBUG: Uploading local file {local_path} to {remote_path}...")
    
    with open(local_path, "rb") as f:
        file_bytes = f.read()
    
    try:
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            path=remote_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )
        print("DEBUG: Upload Success!")
        return f"supabase://{SUPABASE_BUCKET}/{remote_path}"
    except Exception as e:
        print(f"DEBUG: Storage Upload Failed: {e}")
        # If we can't upload, we might be in trouble for persistence.
        # But for now, returning local path (which will be lost on restart) is the only fallback.
        # Or re-raise? Let's re-raise to be safe.
        raise e

def download_file_to_temp(path_uri, force_download=False):
    """
    Download file from URI (local path or supabase://) to a temp local file.
    Returns path to temp file.
    """
    if path_uri.startswith("supabase://"):
        # Format: supabase://bucket/path/to/file
        core = path_uri.replace("supabase://", "")
        parts = core.split("/", 1)
        bucket = parts[0]
        key = parts[1]
        
        # Temp Location
        local_filename = os.path.basename(key)
        local_path = os.path.join("tmp_downloads", local_filename)
        os.makedirs("tmp_downloads", exist_ok=True)
        
        # Check if valid file exists (size > 100 bytes) unless force_download is requested
        if not force_download and os.path.exists(local_path) and os.path.getsize(local_path) > 100:
             return local_path

        # Download
        if supabase:
            with open(local_path, 'wb+') as f:
                res = supabase.storage.from_(bucket).download(key)
                f.write(res)
            
        return local_path
    else:
        return path_uri


import secrets

def generate_secure_token():
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(32)

def get_base_url():
    """
    Get the base URL of the Streamlit app.
    Prioritizes BASE_URL environment variable (for Cloud/Prod/Custom Ports).
    Fallback to localhost:8501.
    """
    return get_env_or_secret("BASE_URL", "http://localhost:8501")

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import os

def generate_certificate(save_path, contract, signer, audit_event, typed_name=None, issuer=None, sent_audit=None):
    """
    Generate an enhanced Completion Certificate PDF including both Issuer (甲) and Signer (乙) details.
    """
    try:
        pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
        font_name = 'HeiseiKakuGo-W5'
    except:
        font_name = 'Helvetica' # Fallback
    
    # Auto-resolve issuer if not provided
    if issuer is None and hasattr(contract, 'parties'):
        issuer = next((p for p in contract.parties if p.role == 'company'), None)
        
    c = canvas.Canvas(save_path, pagesize=A4)
    width, height = A4 # 210mm x 297mm
    
    # Decorative border
    c.setStrokeColorRGB(0.8, 0.85, 0.9)
    c.setLineWidth(1)
    c.rect(12*mm, 12*mm, width - 24*mm, height - 24*mm)
    c.rect(13*mm, 13*mm, width - 26*mm, height - 26*mm)
    
    # Title
    c.setFillColorRGB(0.1, 0.2, 0.4)
    c.setFont(font_name, 18)
    c.drawCentredString(width / 2.0, height - 25*mm, "合意締結証明書")
    c.setFont(font_name, 9)
    c.setFillColorRGB(0.3, 0.35, 0.45)
    c.drawCentredString(width / 2.0, height - 31*mm, "Completion Certificate & Audit Record")
    c.drawCentredString(width / 2.0, height - 36*mm, "本契約は以下の当事者間において、電磁的記録により適法に合意・締結されたことを証明します。")
    
    # Divider line
    c.setStrokeColorRGB(0.2, 0.3, 0.5)
    c.setLineWidth(1.5)
    c.line(20*mm, height - 40*mm, width - 20*mm, height - 40*mm)
    
    y = height - 48*mm
    line_h = 6.2*mm
    
    def draw_section_header(title_jp, title_en, current_y):
        c.setFillColorRGB(0.15, 0.25, 0.45)
        c.rect(20*mm, current_y - 1*mm, width - 40*mm, 6.2*mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(font_name, 10)
        c.drawString(24*mm, current_y + 0.8*mm, f"■ {title_jp} ({title_en})")
        return current_y - 7.5*mm

    def draw_kv(label, val, current_y, label_w=48*mm):
        c.setFont(font_name, 9)
        c.setFillColorRGB(0.3, 0.3, 0.3)
        c.drawString(24*mm, current_y, label)
        c.setFillColorRGB(0.05, 0.05, 0.05)
        
        val_str = str(val) if val is not None else "N/A"
        max_chars = 50
        if len(val_str) > max_chars:
            chunks = [val_str[i:i+max_chars] for i in range(0, len(val_str), max_chars)]
            for i, chunk in enumerate(chunks):
                c.drawString(24*mm + label_w, current_y, chunk)
                if i < len(chunks) - 1:
                    current_y -= 4.8*mm
        else:
            c.drawString(24*mm + label_w, current_y, val_str)
        return current_y - line_h

    # 1. Contract Information
    y = draw_section_header("1. 契約基本情報", "Contract Information", y)
    y = draw_kv("契約件名 / Title:", contract.title, y)
    y = draw_kv("契約ID / Contract ID:", str(contract.id), y)
    y = draw_kv("原本ハッシュ (SHA256):", contract.pdf_sha256, y)
    y = draw_kv("最終締結日時 / Signed At:", f"{format_jst_datetime(contract.signed_at)} JST", y)
    y -= 2*mm

    # 2. Issuer (甲)
    issuer_name = issuer.name if issuer else "N/A"
    sent_date_val = contract.sent_at or contract.created_at
    if sent_audit and hasattr(sent_audit, 'occurred_at') and sent_audit.occurred_at:
        sent_date_val = sent_audit.occurred_at
    sent_date_str = f"{format_jst_datetime(sent_date_val)} JST" if sent_date_val else "N/A"
    
    y = draw_section_header("2. 甲：発行者 / 提示者", "Issuer / Company", y)
    y = draw_kv("発行者・会社名 / Issuer:", issuer_name, y)
    if issuer and getattr(issuer, 'email', None):
        y = draw_kv("連絡先メール / Email:", issuer.email, y)
    y = draw_kv("発行・送信日時 / Sent Date:", sent_date_str, y)
    y = draw_kv("送信操作認証 / Authentication:", "管理者アカウント認証済み (Admin Authenticated)", y)
    y -= 2*mm

    # 3. Signer (乙)
    signer_name = signer.name if signer else "N/A"
    signer_email = signer.email if signer else "N/A"
    input_name = typed_name if typed_name else (signer.name if signer else "N/A")
    ip_addr = audit_event.ip_address if audit_event and hasattr(audit_event, 'ip_address') else "N/A"
    ua = audit_event.user_agent if audit_event and hasattr(audit_event, 'user_agent') and audit_event.user_agent else "N/A"
    if len(ua) > 60: ua = ua[:60] + "..."

    y = draw_section_header("3. 乙：署名者 / 承諾者", "Signer / Counterparty", y)
    y = draw_kv("署名者氏名 / Signer Name:", signer_name, y)
    y = draw_kv("署名者メール / Signer Email:", signer_email, y)
    y = draw_kv("署名時入力氏名 / Input Name:", input_name, y)
    y = draw_kv("署名・承諾日時 / Signed Date:", f"{format_jst_datetime(contract.signed_at)} JST", y)
    y = draw_kv("アクセス元IP / IP Address:", ip_addr, y)
    y = draw_kv("署名環境 / User Agent:", ua, y)
    y -= 3*mm

    # Footer
    c.setStrokeColorRGB(0.7, 0.75, 0.8)
    c.setLineWidth(0.5)
    c.line(20*mm, y + 2*mm, width - 20*mm, y + 2*mm)
    
    c.setFont(font_name, 7.5)
    c.setFillColorRGB(0.4, 0.45, 0.5)
    c.drawString(20*mm, 18*mm, "本証明書は、電子契約システム「Minimal e-Contract Service」において記録された監査ログおよびハッシュチェーンに基づき自動発行されたものです。")
    c.drawRightString(width - 20*mm, 18*mm, f"発行日時: {format_jst_datetime(contract.signed_at)} JST")

    c.save()
    return save_path

import json

def compute_hash(data_str):
    return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

def compute_audit_hash(prev_hash, contract_id, actor_type, event_type, timestamp, metadata):
    """
    Compute a hash chain for audit logs.
    Payload = prev_hash | contract_id | actor_type | event_type | timestamp | metadata_json
    """
    # Create a consistent string representation
    # Sort keys for consistent JSON string
    meta_str = json.dumps(metadata, sort_keys=True) if metadata else ""
    payload = f"{prev_hash}|{contract_id}|{actor_type}|{event_type}|{str(timestamp)}|{meta_str}"
    return compute_hash(payload)

def normalize_name(name):
    """Normalize name for comparison: remove all whitespace and uppercase."""
    if not name: return ""
    return "".join(name.split()).upper()

def save_anchor_file(contract_id, chain_data):
    """
    Save robust anchor file locally (simulating external storage) 
    and return content for email simulation.
    """
    anchor_dir = "anchors"
    os.makedirs(anchor_dir, exist_ok=True)
    
    filename = f"{contract_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_anchor.json"
    filepath = os.path.join(anchor_dir, filename)
    
    with open(filepath, "w", encoding='utf-8') as f:
        json.dump(chain_data, f, indent=4, ensure_ascii=False)
        
    return filepath

import unicodedata

def normalize_name_nfkc(name):
    """
    Normalize name using NFKC form + whitespace removal + uppercase.
    This handles half-width kana, full-width alphanumerics, etc.
    """
    if not name: return ""
    # 1. NFKC Normalization
    normalized = unicodedata.normalize('NFKC', name)
    # 2. Whitespace Removal
    no_space = "".join(normalized.split())
    # 3. Uppercase
    return no_space.upper()

def append_anchor_jsonl(chain_data):
    """
    Append anchor data to a JSONL file (audit_anchors.jsonl).
    JSONL is robust for append-only logging.
    """
    anchor_dir = "anchors"
    os.makedirs(anchor_dir, exist_ok=True)
    
    # Single file for MVP simplicity, or rotate by date
    filepath = os.path.join(anchor_dir, "audit_anchors.jsonl")
    
    # Ensure generated_at is set if not present
    if "generated_at" not in chain_data:
        chain_data["generated_at"] = str(datetime.now())
    
    with open(filepath, "a", encoding='utf-8') as f:
        # Compact JSON, one line
        line = json.dumps(chain_data, ensure_ascii=False)
        f.write(line + "\n")
        
    return filepath

from pypdf import PdfReader, PdfWriter

def merge_pdf_with_certificate(original_pdf_path, cert_pdf_path, output_path):
    """
    Merge the original contract PDF with the certificate PDF appended at the end.
    """
    writer = PdfWriter()

    # Append Original
    with open(original_pdf_path, "rb") as f:
        reader = PdfReader(f)
        for page in reader.pages:
            writer.add_page(page)

    # Append Certificate
    with open(cert_pdf_path, "rb") as f:
        reader = PdfReader(f)
        for page in reader.pages:
            writer.add_page(page)

    # Write Output
    with open(output_path, "wb") as f_out:
        writer.write(f_out)

from pypdf import PdfWriter, PdfReader
import io

def create_stamp_pdf(text, width, height):
    """
    Create a temporary PDF with the stamp text at the bottom.
    """
    packet = io.BytesIO()
    # Use explicit page size matching the target if possible, here assuming A4 or dynamic
    c = canvas.Canvas(packet, pagesize=(width, height))
    
    # Stamp Style
    c.setFillColorRGB(0.5, 0.5, 0.5, 0.8) # Grey, almost opaque
    font_name = "Helvetica"
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
        font_name = "HeiseiKakuGo-W5"
    except:
        pass
    
    # Auto-adjust font size to fit within margins
    margin = 8 * mm
    usable_width = width - (2 * margin)
    font_size = 6.0
    try:
        text_width = pdfmetrics.stringWidth(text, font_name, font_size)
        if text_width > usable_width and text_width > 0:
            font_size = font_size * (usable_width / text_width)
    except:
        font_size = 5.0
    
    c.setFont(font_name, font_size)
    c.drawString(margin, 4 * mm, text)
    
    c.save()
    packet.seek(0)
    return packet

def stamp_all_pages(original_pdf_path, output_path, stamp_text):
    """
    Overlay a stamp text on the footer of EVERY page of the PDF.
    """
    reader = PdfReader(original_pdf_path)
    writer = PdfWriter()
    
    for page in reader.pages:
        # Get page dimensions
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        
        # Create a stamp for this page size
        stamp_io = create_stamp_pdf(stamp_text, width, height)
        stamp_pdf = PdfReader(stamp_io)
        stamp_page = stamp_pdf.pages[0]
        
        # Merge stamp onto the content page
        page.merge_page(stamp_page)
        writer.add_page(page)
        
    with open(output_path, "wb") as f_out:
        writer.write(f_out)
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
