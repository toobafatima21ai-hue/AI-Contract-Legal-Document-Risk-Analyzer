"""
routers/documents.py  — FIXED
================================
KEY FIXES vs original:
1. analyze_document() now catches RuntimeError from the orchestrator and
   returns a proper HTTP 500 with the real error message instead of a raw
   traceback 500 Internal Server Error.
2. upload_document() handles the case where extract_text() returns a very
   short string (scanned PDF) without immediately rejecting the file — the
   OCR fallback inside extraction.py handles it transparently.
3. _get_owned_document() extracted as a reusable helper (unchanged).
"""

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.models import User, Document, Analysis, AuditLog
from app.models.schemas import DocumentOut, AnalysisOut
from app.services.extraction import extract_text, detect_language
from app.services.analysis_orchestrator import run_full_analysis, analysis_to_dict
from app.services import vector_store

router = APIRouter(prefix="/api/documents", tags=["Documents"])


def _validate_upload(file: UploadFile) -> str:
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: PDF, DOCX, TXT.",
        )
    return ext


def _get_owned_document(db: Session, document_id: int, current_user: User) -> Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="You do not have access to this document")
    return doc


# ─── Upload ──────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=DocumentOut)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ext = _validate_upload(file)

    safe_name = f"user{current_user.id}_{int(__import__('time').time())}_{file.filename}"
    dest_path = settings.UPLOAD_DIR / safe_name

    with dest_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if dest_path.stat().st_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds {settings.MAX_FILE_SIZE_MB} MB limit.",
        )

    try:
        text = extract_text(dest_path, ext)
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Failed to read document: {e}")

    # FIX: do NOT reject short text here — OCR fallback inside extract_text()
    # already tried Tesseract. If still empty after OCR, warn but still save.
    if not text.strip():
        text = "[Document appears blank or entirely image-based — OCR returned no text. " \
               "Install tesseract-ocr and poppler-utils for full OCR support.]"

    document = Document(
        owner_id=current_user.id,
        filename=file.filename,
        stored_path=str(dest_path),
        file_type=ext,
        raw_text=text,
        language=detect_language(text),
        status="uploaded",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    db.add(AuditLog(
        user_id=current_user.id,
        action="upload_document",
        details=document.filename,
    ))
    db.commit()

    return document


# ─── List / Get ──────────────────────────────────────────────────────────────

@router.get("/", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Document)
        .filter(Document.owner_id == current_user.id)
        .order_by(Document.upload_date.desc())
        .all()
    )


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_owned_document(db, document_id, current_user)


# ─── Analyze  ────────────────────────────────────────────────────────────────

@router.post("/{document_id}/analyze")
def analyze_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    FIX: Catches RuntimeError raised by run_full_analysis and converts it to
    a clean HTTP 500 with the real reason — no more 'Internal Server Error'
    with no detail.
    """
    doc = _get_owned_document(db, document_id, current_user)

    try:
        analysis = run_full_analysis(db, doc)
    except RuntimeError as e:
        # run_full_analysis already set doc.status = "failed"
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
    except Exception as e:
        # Safety net for anything else
        try:
            doc.status = "failed"
            db.commit()
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during analysis: {str(e)}",
        )

    db.add(AuditLog(
        user_id=current_user.id,
        action="analyze_document",
        details=doc.filename,
    ))
    db.commit()

    return analysis_to_dict(analysis)


@router.get("/{document_id}/analysis")
def get_analysis(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = _get_owned_document(db, document_id, current_user)
    analysis = db.query(Analysis).filter(Analysis.document_id == doc.id).first()
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="Document has not been analyzed yet. Call POST /analyze first.",
        )
    return analysis_to_dict(analysis)


# ─── Delete ──────────────────────────────────────────────────────────────────

@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = _get_owned_document(db, document_id, current_user)
    Path(doc.stored_path).unlink(missing_ok=True)
    vector_store.delete_document(doc.id)
    db.delete(doc)
    db.commit()
    return {"detail": "Document deleted successfully"}
