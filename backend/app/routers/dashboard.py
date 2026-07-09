import json
from collections import Counter
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, Document, Analysis
from app.models.schemas import DashboardStats, DocumentOut

router = APIRouter(prefix="/api/dashboard", tags=["AI Insights Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    docs = db.query(Document).filter(Document.owner_id == current_user.id).all()
    doc_ids = [d.id for d in docs]
    analyses = db.query(Analysis).filter(Analysis.document_id.in_(doc_ids)).all() if doc_ids else []

    avg_risk = round(sum(a.risk_score for a in analyses) / len(analyses), 2) if analyses else 0.0
    high_risk_count = sum(1 for a in analyses if a.risk_score >= 50)

    risk_type_counter = Counter()
    for a in analyses:
        for r in json.loads(a.risks_json or "[]"):
            risk_type_counter[r.get("type", "Unknown")] += 1

    frequent_risks = [{"type": k, "count": v} for k, v in risk_type_counter.most_common(10)]

    recent = sorted(docs, key=lambda d: d.upload_date, reverse=True)[:10]

    return DashboardStats(
        total_documents=len(docs),
        average_risk_score=avg_risk,
        high_risk_documents=high_risk_count,
        frequently_detected_risks=frequent_risks,
        recent_documents=[DocumentOut.model_validate(d) for d in recent],
    )
