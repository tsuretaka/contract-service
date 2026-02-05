# Implementation Plan - Minimal e-Contract Service

This plan outlines the development steps for the Minimal e-Contract Service using Python and Streamlit.

## 1. Technology Stack
- **Framework**: Streamlit (Single Page Application structure)
- **Database**: SQLite (managed via SQLAlchemy ORM for future scalability)
- **PDF Handling**: `PyPDF2` (reading/hashing), `reportlab` (generating completion certificates)
- **Time/Security**: `bcrypt` (password hashing), `secrets` (token generation)

## 2. Project Structure
```
contract_service/
├── app.py                  # Main application entry point
├── requirements.txt        # Dependencies
├── models.py               # Database Connection & SQLAlchemy Models
├── utils.py                # Helper functions (Hashing, PDF handling, Token logic)
├── services.py             # Business logic (Contract ops, Signing ops)
├── contracts/              # Storage for PDF files
│   ├── uploads/            # Original uploaded contracts
│   └── signed/             # Signed contracts & certificates
└── database/
    └── app.db              # SQLite Database file
```

## 3. Development Phases

### Phase 1: Foundation & Database
- [x] Initialize Project & Git
- [x] Install dependencies (`streamlit`, `sqlalchemy`, `pypdf`, `reportlab`, `bcrypt`)
- [x] Define Database Models (`Contract`, `Party`, `SigningSession`, `AuditEvent`) as per Specification
- [x] Setup Database initialization script

### Phase 2: Admin Dashboard (Contract Creation)
- [x] Implement Admin Login (Simple ID/PW check)
- [x] Create "Contract List" view (Draft, Sent, Signed, Void)
- [x] Create "New Contract" form:
    - Upload PDF
    - Enter Title
    - Register Signer Info (Name, Email)
    - Save to DB & File System

### Phase 3: Signing Workflow Engine
- [x] Implement "Send Contract" logic:
    - Generate secure Token
    - Simulate Email Sending (Display "Email Content" in Admin view for MVP)
    - Update Status to 'Sent'
- [x] Implement Signer View (Routing via `?token=...`):
    - Validate Token
    - Display Contract PDF (Embedded)
    - Checkbox & "Sign" button

### Phase 4: Signature Execution & Security
- [x] Implement Signing Logic:
    - Verify integrity (PDF Hash)
    - Record Audit Event (IP, User-Agent)
    - Update Status to 'Signed'
    - Invalidate Token
- [x] Generate "Completion Certificate" PDF (using `reportlab`)
- [x] Merge Certificate with Original PDF

### Phase 5: Finalize & Download
- [x] Admin: View Signed Contracts & Download (PDF + Certificate)
- [x] Signer: Download immediately after signing
- [x] Audit Log Viewer for Admin

## 4. Immediate Next Steps
All Phase 1-5 tasks are completed.
Potential next steps:
1.  **Deployment**: Prepare for cloud deployment (e.g., Streamlit Community Cloud, Render).
2.  **Email Integration**: Replace simulated email with SendGrid or Gmail SMTP.
3.  **UI Polish**: Improve styling and user feedback.

## 5. Persistence Migration (Supabase)
- [ ] Configure `DATABASE_URL` to point to Supabase PostgreSQL in `models.py`.
- [ ] Replace local file storage with Supabase Storage Bucket logic in `utils.py`.
- [ ] Update `services.py` to use Storage Bucket for PDF URIs.
