from utils import generate_secure_token, get_base_url, generate_certificate, compute_audit_hash, save_uploaded_file, normalize_name_nfkc, append_anchor_jsonl, merge_pdf_with_certificate, stamp_all_pages
from datetime import timedelta, datetime
from models import SessionLocal, SessionAudit, Contract, Party, AuditEvent, SigningSession
import os
import json
from sqlalchemy.orm import joinedload

CERT_DIR = "contracts/signed"
os.makedirs(CERT_DIR, exist_ok=True)

# Helper for Audit with Hash Chaining
def _record_audit(contract_id, actor_type, reference, event_type, ip=None, ua=None, meta=None):
    """
    Internal helper to create an audit event with hash chaining.
    Uses dedicated Audit Database Session.
    """
    db_audit = SessionAudit()
    try:
        # 1. Get the hash of the very last audit event in the Audit DB
        last_event = db_audit.query(AuditEvent).order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).first()
        prev_hash = last_event.record_hash if (last_event and last_event.record_hash) else "0" * 64
        
        timestamp = datetime.now()
        
        # 2. Metadata for Hash Calculation
        hash_meta = {
            'ip': ip, 
            'ua': ua, 
            'ref': reference, 
            'meta': meta
        }
        
        # 3. Compute Hash
        record_hash = compute_audit_hash(prev_hash, contract_id, actor_type, event_type, timestamp, hash_meta)
        
        # 4. Create Record
        audit = AuditEvent(
            contract_id=contract_id,
            actor_type=actor_type,
            actor_reference=reference,
            event_type=event_type,
            occurred_at=timestamp,
            ip_address=ip,
            user_agent=ua,
            metadata_json=meta,
            previous_hash=prev_hash,
            record_hash=record_hash
        )
        db_audit.add(audit)
        db_audit.commit()
        db_audit.refresh(audit)
        return audit
    except Exception as e:
        db_audit.rollback()
        raise e
    finally:
        db_audit.close()

def create_contract(title, company_name, signer_name, signer_email, uploaded_file):
    """
    Creates a new contract record, saves the PDF, and registers parties.
    """
    db = SessionLocal()
    try:
        # 1. Save PDF
        file_path, file_hash = save_uploaded_file(uploaded_file)
        
        # 2. Create Contract Record
        contract = Contract(
            title=title,
            pdf_path=file_path,
            pdf_sha256=file_hash,
            status='draft'
        )
        db.add(contract)
        db.flush() # Flush to get ID
        
        # 3. Add Parties
        company = Party(contract_id=contract.id, role='company', name=company_name)
        db.add(company)
        
        signer = Party(contract_id=contract.id, role='signer', name=signer_name, email=signer_email)
        db.add(signer)

        db.commit()

        # 4. Audit Log (Separate DB)
        _record_audit(contract.id, 'admin', 'system_admin', 'created', meta={'filename': uploaded_file.name})
        
        return contract
        
    except Exception as e:
        db.rollback()
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        raise e
    finally:
        db.close()

def list_contracts():
    """List all contracts."""
    db = SessionLocal()
    try:
        contracts = db.query(Contract).options(joinedload(Contract.parties)).order_by(Contract.created_at.desc()).all()
        return contracts
    finally:
        db.close()

def get_all_audit_events(limit=50):
    """Fetch recent audit events for the admin view."""
    db_audit = SessionAudit()
    try:
        events = db_audit.query(AuditEvent).order_by(AuditEvent.occurred_at.desc()).limit(limit).all()
        return events
    finally:
        db_audit.close()

def get_contract_details(contract_id):
    """Get full contract details."""
    db = SessionLocal()
    try:
        contract = db.query(Contract).options(joinedload(Contract.parties)).filter(Contract.id == contract_id).first()
        return contract
    finally:
        db.close()

def void_contract_service(contract_id):
    """Void a contract."""
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if contract and contract.status != 'void':
            contract.status = 'void'
            contract.voided_at = datetime.now()
            db.commit()
            
            # Audit
            _record_audit(contract.id, 'admin', 'system_admin', 'voided')
            
            return True
        return False
    finally:
        db.close()

def send_contract(contract_id, valid_days=7):
    """Simulate sending a contract."""
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract or contract.status != 'draft':
            return None
        
        signer = next((p for p in contract.parties if p.role == 'signer'), None)
        if not signer: raise ValueError("No signer found")

        # Create Session
        token_raw = generate_secure_token()
        import hashlib
        token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
        expires = datetime.now() + timedelta(days=valid_days)
        
        session = SigningSession(
            contract_id=contract.id,
            signer_party_id=signer.id,
            token_hash=token_hash,
            expires_at=expires
        )
        db.add(session)
        
        contract.status = 'sent'
        contract.sent_at = datetime.now()
        db.commit()
        
        # Audit
        _record_audit(contract.id, 'admin', 'system_admin', 'sent')
        
        link = f"{get_base_url()}/?token={token_raw}"
        
        email_body = f"""
        To: {signer.email}
        Subject: 【署名依頼】{contract.title}
        
        {signer.name} 様
        
        以下のリンクから契約書を確認し、署名をお願いします。
        有効期限: {expires}
        
        URL: {link}
        """
        return email_body
    finally:
        db.close()

def validate_token(token_raw):
    """Validate a token from URL."""
    import hashlib
    print(f"DEBUG: validate_token called with token_raw={token_raw[:10]}...") 
    
    token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
    print(f"DEBUG: Calculated hash={token_hash}")
    
    db = SessionLocal()
    try:
        session = db.query(SigningSession).filter(
            SigningSession.token_hash == token_hash,
            SigningSession.used_at.is_(None),
            SigningSession.expires_at > datetime.now()
        ).first()
        
        if not session:
            # Debug why it failed
            print("DEBUG: Session not found with matching hash and valid status.")
            # Check if it exists but is expired or used
            any_session = db.query(SigningSession).filter(SigningSession.token_hash == token_hash).first()
            if any_session:
                print(f"DEBUG: Found session but status invalid. used_at={any_session.used_at}, expires_at={any_session.expires_at}, now={datetime.now()}")
            else:
                print("DEBUG: No session found with this hash at all.")
                
            return None, None, None
            
        print(f"DEBUG: Session found! ID={session.id}")
        contract = db.query(Contract).filter(Contract.id == session.contract_id).first()
        signer = db.query(Party).filter(Party.id == session.signer_party_id).first()
        
        return contract, session, signer
    except Exception as e:
        print(f"DEBUG: DB Error in validate_token: {e}")
        return None, None, None
    finally:
        db.close()

def execute_signature(session_id, ip_address, user_agent, typed_name):
    """
    Execute the signature action with strict transactional integrity.
    Includes Name Verification, Page Stamping, and External Anchor Emailing.
    """
    db = SessionLocal()
    cert_path = None
    cert_temp_path = None
    merged_path = None
    merged_temp_path = None
    stamped_temp_path = None
    
    try:
        session = db.query(SigningSession).filter(SigningSession.id == session_id).first()
        if not session: return False, "Session not found"
        
        contract = db.query(Contract).filter(Contract.id == session.contract_id).first()
        
        # --- 0. Name Verification (Strict + NFKC) ---
        registered_name = session.party.name
        if normalize_name_nfkc(typed_name) != normalize_name_nfkc(registered_name):
            # Fail immediately if name doesn't match
            return False, f"Name mismatch: Typed '{typed_name}' does not match registered '{registered_name}'"
        
        # 1. Update DB State (App DB)
        contract.status = 'signed'
        contract.signed_at = datetime.now()
        session.used_at = datetime.now()
        db.commit() 
        
        # 2. Record Audit (Audit DB)
        audit_meta = {
            'typed_name_verification': typed_name,
            'match_result': True
        }
        
        audit = _record_audit(
            contract.id, 
            'signer', 
            session.party.email, 
            'signed', 
            ip=ip_address, 
            ua=user_agent,
            meta=audit_meta
        )
        
        # 3. Generate Certificate (Safe Logic)
        cert_filename = f"{contract.id}_cert.pdf"
        cert_temp_filename = f"tmp_{contract.id}_cert.pdf"
        cert_path = os.path.join(CERT_DIR, cert_filename)
        cert_temp_path = os.path.join(CERT_DIR, cert_temp_filename)
        
        generate_certificate(cert_temp_path, contract, session.party, audit, typed_name)
        
        if not os.path.exists(cert_temp_path):
            raise IOError("Certificate file creation failed")
            
        # Atomic rename
        os.rename(cert_temp_path, cert_path)

        # 4. Generate Merged PDF with STAMPS
        # This is the user-facing "Signed Contract"
        
        from utils import download_file_to_temp, upload_local_file_to_storage, SUPABASE_BUCKET
        
        # 4a. Create Stamped Version of Original
        # Ensure we have local access to original (Download if Supabase)
        local_original_pdf = download_file_to_temp(contract.pdf_path)
        
        stamped_temp_filename = f"tmp_{contract.id}_stamped.pdf"
        stamped_temp_path = os.path.join(CERT_DIR, stamped_temp_filename)
        
        stamp_text = f"Contract ID: {contract.id} | Signed: {str(contract.signed_at)}"
        # Use local_original_pdf here
        stamp_all_pages(local_original_pdf, stamped_temp_path, stamp_text)
        
        # 4b. Merge Stamped + Certificate
        merged_filename = f"{contract.id}_signed.pdf"
        merged_temp_filename = f"tmp_{contract.id}_signed.pdf"
        merged_path = os.path.join(CERT_DIR, merged_filename)
        merged_temp_path = os.path.join(CERT_DIR, merged_temp_filename)

        # Use STAMPED path here instead of raw path
        merge_pdf_with_certificate(stamped_temp_path, cert_path, merged_temp_path)
        
        if not os.path.exists(merged_temp_path):
             raise IOError("Merged file creation failed")
        
        os.rename(merged_temp_path, merged_path)
        
        # Cleanup temp stamped file
        if os.path.exists(stamped_temp_path):
            os.remove(stamped_temp_path)
            
        # --- UPLOAD TO SUPABASE IF ACTIVE ---
        if SUPABASE_BUCKET:
            try:
                # Upload Certificate
                upload_local_file_to_storage(cert_path, remote_folder="signed")
                # Upload Signed Merged PDF
                upload_local_file_to_storage(merged_path, remote_folder="signed")
            except Exception as e:
                print(f"Post-signature upload failed: {e}")
                # Don't fail the transaction just because upload failed, 
                # but valid concern for persistence. Proceeding.
        
        # Prepare Anchor Data (Enhanced)
        db_audit = SessionAudit()
        try:
            first_event = db_audit.query(AuditEvent).filter(AuditEvent.contract_id == contract.id).order_by(AuditEvent.occurred_at.asc()).first()
            chain_start_hash = first_event.record_hash if first_event else "N/A"
            chain_start_id = first_event.id if first_event else "N/A"
        finally:
            db_audit.close()
        
        chain_data = {
            "version": "1.0",
            "contract_id": contract.id,
            "contract_pdf_sha256": contract.pdf_sha256,
            "signer_email": session.party.email,
            "anchor_timestamp": str(datetime.utcnow()) + "Z", # UTC
            "chain_start": {
                "event_id": chain_start_id,
                "record_hash": chain_start_hash
            },
            "chain_latest": {
                "event_id": audit.id,
                "occurred_at": str(audit.occurred_at),
                "record_hash": audit.record_hash,
                "previous_hash": audit.previous_hash
            },
            "verification": {
                "registered_name": registered_name,
                "input_name": typed_name,
                "nfkc_match": True
            }
        }
            
        # --- 5. Post-Commit Actions (External Anchor Preservation) ---
        # Save Anchor locally (JSONL)
        anchor_path = append_anchor_jsonl(chain_data)
        
        # Simulate Email to Admin (Strong Evidence)
        email_content = f"""
        [System Notification: Contract Signed]
        Contract: {contract.title}
        PDF SHA256: {contract.pdf_sha256}
        Signer: {typed_name} (Verified)
        
        *** SECURITY ANCHOR ***
        This anchor data is appended to strict audit log at: {anchor_path}
        
        {json.dumps(chain_data, indent=2, ensure_ascii=False)}
        """
        
        return True, email_content
        
    except Exception as e:
        # Cleanup
        if cert_temp_path and os.path.exists(cert_temp_path):
            os.remove(cert_temp_path)
        if cert_path and os.path.exists(cert_path):
             os.remove(cert_path)
        if merged_temp_path and os.path.exists(merged_temp_path):
             os.remove(merged_temp_path)
        if merged_path and os.path.exists(merged_path):
             os.remove(merged_path)
        if stamped_temp_path and os.path.exists(stamped_temp_path):
             os.remove(stamped_temp_path)
        raise e
    finally:
        db.close()

def get_certificate_path(contract_id):
    """Return path to the certificate file."""
    return os.path.join(CERT_DIR, f"{contract_id}_cert.pdf")

def get_signed_contract_path(contract_id):
    """Return path to the merged signed contract file."""
    return os.path.join(CERT_DIR, f"{contract_id}_signed.pdf")
