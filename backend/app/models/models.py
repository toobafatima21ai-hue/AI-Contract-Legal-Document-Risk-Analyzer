from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="user")  # "user" or "admin"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String(255))
    stored_path = Column(String(500))
    file_type = Column(String(10))
    upload_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String(30), default="uploaded")  # uploaded, processing, analyzed, failed
    raw_text = Column(Text, nullable=True)
    language = Column(String(10), default="en")

    owner = relationship("User", back_populates="documents")
    analysis = relationship("Analysis", back_populates="document", uselist=False, cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    contract_type = Column(String(150), nullable=True)
    parties = Column(Text, nullable=True)          # JSON string
    effective_date = Column(String(50), nullable=True)
    expiry_date = Column(String(50), nullable=True)
    payment_terms = Column(Text, nullable=True)
    renewal_clause = Column(Text, nullable=True)
    confidentiality_clause = Column(Text, nullable=True)
    termination_clause = Column(Text, nullable=True)
    responsibilities = Column(Text, nullable=True)

    executive_summary = Column(Text, nullable=True)
    key_obligations = Column(Text, nullable=True)   # JSON string
    important_dates = Column(Text, nullable=True)   # JSON string
    recommended_actions = Column(Text, nullable=True)  # JSON string

    risk_score = Column(Float, default=0.0)
    risks_json = Column(Text, nullable=True)         # JSON list of risk dicts
    compliance_score = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="analysis")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(255))
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
