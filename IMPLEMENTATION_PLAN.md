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
- [ ] Initialize Project & Git
- [ ] Install dependencies (`streamlit`, `sqlalchemy`, `pypdf`, `reportlab`, `bcrypt`)
- [ ] Define Database Models (`Contract`, `Party`, `SigningSession`, `AuditEvent`) as per Specification
- [ ] Setup Database initialization script

### Phase 2: Admin Dashboard (Contract Creation)
- [ ] Implement Admin Login (Simple ID/PW check)
- [ ] Create "Contract List" view (Draft, Sent, Signed, Void)
- [ ] Create "New Contract" form:
    - Upload PDF
    - Enter Title
    - Register Signer Info (Name, Email)
    - Save to DB & File System

### Phase 3: Signing Workflow Engine
- [ ] Implement "Send Contract" logic:
    - Generate secure Token
    - Simulate Email Sending (Display "Email Content" in Admin view for MVP)
    - Update Status to 'Sent'
- [ ] Implement Signer View (Routing via `?token=...`):
    - Validate Token
    - Display Contract PDF (Embedded)
    - Checkbox & "Sign" button

### Phase 4: Signature Execution & Security
- [ ] Implement Signing Logic:
    - Verify integrity (PDF Hash)
    - Record Audit Event (IP, User-Agent)
    - Update Status to 'Signed'
    - Invalidate Token
- [ ] Generate "Completion Certificate" PDF (using `reportlab`)

### Phase 5: Finalize & Download
- [ ] Admin: View Signed Contracts & Download (PDF + Certificate)
- [ ] Signer: Download immediately after signing
- [ ] Audit Log Viewer for Admin

## 4. Immediate Next Steps
1. Create `requirements.txt`
2. Create `models.py` and initialize the database.
