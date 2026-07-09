from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, Document
from app.models.schemas import CompareRequest
from app.services import llm_service

router = APIRouter(
    prefix="/api/compare",
    tags=["AI Clause / Version Comparison (Bonus)"]
)


@router.post("/")
def compare_documents(
    payload: CompareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc_a = db.query(Document).filter(
        Document.id == payload.document_id_a
    ).first()

    doc_b = db.query(Document).filter(
        Document.id == payload.document_id_b
    ).first()

    for d in (doc_a, doc_b):
        if not d or (
            d.owner_id != current_user.id
            and current_user.role != "admin"
        ):
            raise HTTPException(
                status_code=404,
                detail="One or both documents not found"
            )

    # Try LLM comparison first
    try:
        if llm_service.is_llm_available():
            result = llm_service.compare_contracts_with_llm(
                doc_a.raw_text or "",
                doc_b.raw_text or ""
            )

            if result:
                return result

    except Exception as e:
        print("Compare error:", e)

    # Fallback comparison if LLM fails
    import difflib

    a_lines = (doc_a.raw_text or "").split("\n")
    b_lines = (doc_b.raw_text or "").split("\n")

    diff = list(
        difflib.unified_diff(
            a_lines,
            b_lines,
            lineterm="",
            n=0
        )
    )

    added = [
        line[1:].strip()
        for line in diff
        if line.startswith("+") and not line.startswith("+++")
    ]

    removed = [
        line[1:].strip()
        for line in diff
        if line.startswith("-") and not line.startswith("---")
    ]

    return {
        "summary_of_changes": (
            f"{len(added)} line(s) added, "
            f"{len(removed)} line(s) removed "
            "(LLM unavailable — raw diff shown)."
        ),
        "added_clauses": added[:20],
        "removed_clauses": removed[:20],
        "risk_differences": [],
        "recommendation": (
            "Run with Ollama online for a deeper legal comparison."
        ),
    }