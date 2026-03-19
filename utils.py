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

def download_file_to_temp(path_uri):
    """
    Download file from URI (local path or supabase://) to a temp local file.
    Returns path to temp file.
    """
    if path_uri.startswith("supabase://"):
        # Format: supabase://bucket/path/to/file
        # Remove prefix
        core = path_uri.replace("supabase://", "")
        # Split bucket and path
        parts = core.split("/", 1)
        bucket = parts[0]
        key = parts[1]
        
        # Temp Location
        local_filename = os.path.basename(key)
        local_path = os.path.join("tmp_downloads", local_filename)
        os.makedirs("tmp_downloads", exist_ok=True)
        
        if os.path.exists(local_path):
             return local_path # Cache hit? For now simple return

        # Download
        with open(local_path, 'wb+') as f:
            res = supabase.storage.from_(bucket).download(key)
            f.write(res)
            
        return local_path
    else:
        return path_uri # It is already a local path


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

def generate_certificate(save_path, contract, signer, audit_event, typed_name=None):
    """
    Generate a Completion Certificate PDF.
    """
    try:
        # Register Japanese Font
        pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
        font_name = 'HeiseiKakuGo-W5'
    except:
        font_name = 'Helvetica' # Fallback
    
    c = canvas.Canvas(save_path, pagesize=A4)
    width, height = A4
    
    # Draw logic
    c.setFont(font_name, 18)
    c.drawString(20*mm, height - 30*mm, "Completion Certificate / 署名完了証明書")
    
    c.setFont(font_name, 10)
    y = height - 50*mm
    line_height = 10*mm
    
    # Data to print
    data = [
        ("Contract Title / 契約名", contract.title),
        ("Contract ID", str(contract.id)),
        ("Document Hash (SHA256)", contract.pdf_sha256),
        ("Signer Name / 署名者名", signer.name),
        ("Signer Email / メール", signer.email),
        ("Input Name / 入力氏名", typed_name if typed_name else "N/A"), # Added field
        ("Signed Date / 署名日時", str(contract.signed_at)),
        ("IP Address", audit_event.ip_address),
        ("User Agent", audit_event.user_agent[:60] + "..." if audit_event.user_agent else "N/A"),
    ]
    
    for label, value in data:
        c.drawString(20*mm, y, f"{label}:")
        val_str = str(value)
        
        # Simple wrapping for long text (e.g. Hash)
        if len(val_str) > 40:
            chunks = [val_str[i:i+40] for i in range(0, len(val_str), 40)]
            for i, chunk in enumerate(chunks):
                c.drawString(80*mm, y, chunk)
                if i < len(chunks) - 1:
                    y -= line_height 
        else:
            c.drawString(80*mm, y, val_str)
            
        y -= line_height
        
    c.drawString(20*mm, 20*mm, "Generated by Minimal e-Contract Service")
    
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
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
        c.setFont("HeiseiKakuGo-W5", 7)
    except:
        c.setFont("Helvetica", 7)
    
    # Draw text at the bottom center/left
    # Format: Contract ID | Hash | Signed on ...
    c.drawString(10*mm, 5*mm, text)
    
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
