import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Database Path
DB_DIR = "database"
DB_FILE_APP = "app.db"
DB_FILE_AUDIT = "audit.db"

# Default to SQLite
DB_PATH_APP = os.path.join(DB_DIR, DB_FILE_APP)
DB_PATH_AUDIT = os.path.join(DB_DIR, DB_FILE_AUDIT)

os.makedirs(DB_DIR, exist_ok=True)

# Connection Strings
# Check for DATABASE_URL (PostgreSQL) or fallback to SQLite
_env_db_url = os.environ.get("DATABASE_URL")

# Try obtaining from Streamlit secrets if not in env
if not _env_db_url:
    try:
        import streamlit as st
        # secrets might differ in structure, checking root or general section
        if hasattr(st, "secrets"):
            if "DATABASE_URL" in st.secrets:
                _env_db_url = st.secrets["DATABASE_URL"]
            elif "general" in st.secrets and "DATABASE_URL" in st.secrets["general"]:
                _env_db_url = st.secrets["general"]["DATABASE_URL"]
    except Exception:
        pass

if _env_db_url:
    # Use the same Postgres DB for both App and Audit for simplicity in migration
    # Ensure it starts with postgresql:// instead of postgres:// (SQLAlchemy compat)
    if _env_db_url.startswith("postgres://"):
        _env_db_url = _env_db_url.replace("postgres://", "postgresql://", 1)
        
    DATABASE_URL_APP = _env_db_url
    DATABASE_URL_AUDIT = _env_db_url
else:
    DATABASE_URL_APP = f"sqlite:///{DB_PATH_APP}"
    DATABASE_URL_AUDIT = f"sqlite:///{DB_PATH_AUDIT}"

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

class Contract(Base):
    __tablename__ = 'contracts'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(Text, nullable=False)
    status = Column(String(20), default='draft') # draft, sent, signed, void
    pdf_path = Column(Text, nullable=False)
    pdf_sha256 = Column(String(64), nullable=True)
    
    created_at = Column(DateTime, default=datetime.now)
    sent_at = Column(DateTime, nullable=True)
    signed_at = Column(DateTime, nullable=True)
    voided_at = Column(DateTime, nullable=True)

    # Relationships
    parties = relationship("Party", back_populates="contract", cascade="all, delete-orphan")
    signing_sessions = relationship("SigningSession", back_populates="contract", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="contract", cascade="all, delete-orphan")

class Party(Base):
    __tablename__ = 'parties'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(String(36), ForeignKey('contracts.id'), nullable=False)
    role = Column(String(20), nullable=False) # company, signer
    name = Column(Text, nullable=False)
    email = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    contract = relationship("Contract", back_populates="parties")

class SigningSession(Base):
    __tablename__ = 'signing_sessions'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(String(36), ForeignKey('contracts.id'), nullable=False)
    signer_party_id = Column(String(36), ForeignKey('parties.id'), nullable=False)
    token_hash = Column(String(64), nullable=False) # SHA-256 of the token from URL
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    contract = relationship("Contract", back_populates="signing_sessions")
    party = relationship("Party")

class AuditEvent(Base):
    __tablename__ = 'audit_events'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(String(36), ForeignKey('contracts.id'), nullable=True)
    actor_type = Column(String(20), nullable=False) # admin, signer, system
    actor_reference = Column(Text, nullable=True) # Admin ID or Signer Email/Name
    event_type = Column(Text, nullable=False) # created, sent, viewed, signed, voided
    occurred_at = Column(DateTime, default=datetime.now)
    ip_address = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    # Hash Chaining Fields
    previous_hash = Column(String(64), nullable=True) # Hash of the previous record
    record_hash = Column(String(64), nullable=True)  # Hash of this record including previous_hash

    contract = relationship("Contract", back_populates="audit_events")

# Engine Setup - We need routing or 2 engines.
# For simplicity in this setup, we will use separate engines/session-makers in services.
# Or use SQLAlchemy "binds". Binds is cleaner for Declarative.

engine = create_engine(DATABASE_URL_APP, echo=False)
# Special engine for Audit
audit_engine = create_engine(DATABASE_URL_AUDIT, echo=False)

# SessionLocal is default for App
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# SessionAudit is custom for Audit
SessionAudit = sessionmaker(autocommit=False, autoflush=False, bind=audit_engine)

def init_db():
    # We must manually map tables to engines for creation if using binds, 
    # OR create them separately.
    
    # 1. Create App Tables
    # Filter Base.metadata.tables to those NOT AuditEvent
    # A bit complex to filter dynamically. 
    # Easier way: Just create all on both (harmless for SQLite if unused) 
    # OR explicitly bind metadata.
    
    # Correct approach:
    # Contract, Party, SigningSession -> app.db
    Contract.__table__.create(bind=engine, checkfirst=True)
    Party.__table__.create(bind=engine, checkfirst=True)
    SigningSession.__table__.create(bind=engine, checkfirst=True)
    
    # AuditEvent -> audit.db
    AuditEvent.__table__.create(bind=audit_engine, checkfirst=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
