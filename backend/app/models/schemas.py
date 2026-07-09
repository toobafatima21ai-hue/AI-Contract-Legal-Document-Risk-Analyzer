from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime


# ---------- Auth ----------
class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = None


# ---------- Documents ----------
class DocumentOut(BaseModel):
    id: int
    filename: str
    file_type: str
    upload_date: datetime
    status: str
    language: str

    class Config:
        from_attributes = True


class RiskItem(BaseModel):
    type: str
    description: str
    severity: str  # Low / Medium / High / Critical
    confidence: float
    explanation: str
    clause_excerpt: Optional[str] = None


class AnalysisOut(BaseModel):
    id: int
    document_id: int
    contract_type: Optional[str]
    parties: Optional[List[str]] = []
    effective_date: Optional[str]
    expiry_date: Optional[str]
    payment_terms: Optional[str]
    renewal_clause: Optional[str]
    confidentiality_clause: Optional[str]
    termination_clause: Optional[str]
    responsibilities: Optional[str]
    executive_summary: Optional[str]
    key_obligations: Optional[List[str]] = []
    important_dates: Optional[List[str]] = []
    recommended_actions: Optional[List[str]] = []
    risk_score: float
    risks: Optional[List[RiskItem]] = []
    compliance_score: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class SemanticSearchQuery(BaseModel):
    document_id: Optional[int] = None  # search a specific doc or all of the user's docs
    query: str
    top_k: int = 5


class SemanticSearchResult(BaseModel):
    document_id: int
    filename: str
    chunk_text: str
    score: float


class QAQuery(BaseModel):
    document_id: Optional[int] = None
    question: str


class QAResponse(BaseModel):
    answer: str
    sources: List[SemanticSearchResult]


class DashboardStats(BaseModel):
    total_documents: int
    average_risk_score: float
    high_risk_documents: int
    frequently_detected_risks: List[Any]
    recent_documents: List[DocumentOut]


class CompareRequest(BaseModel):
    document_id_a: int
    document_id_b: int
