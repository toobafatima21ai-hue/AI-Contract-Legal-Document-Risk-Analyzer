"""
analysis_orchestrator.py  — FIXED
===================================
KEY FIXES vs original:
1. Entire analysis wrapped in try/except — sets document.status = "failed"
   instead of leaving it stuck on "processing" when anything goes wrong.
2. Exceptions are re-raised as plain RuntimeError so the router can catch
   them and return a clean 500 with a human-readable message.
3. _risk_score() now has its own guard so an empty risks list never throws.
4. compliance_score defaults to 0 if the LLM omits it (was causing
   NullPointerErrors downstream in the report renderer).
5. vector_store.index_document failure is fully silenced — indexing is
   best-effort and must never block an analysis result.
"""

import json
import logging
from sqlalchemy.orm import Session

from app.models.models import Document, Analysis
from app.services import llm_service, fallback_analyzer, vector_store

logger = logging.getLogger(__name__)


def run_full_analysis(db: Session, document: Document) -> Analysis:
    """
    Runs the full AI analysis pipeline on `document`.
    Always leaves document.status as either "analyzed" or "failed".
    Raises RuntimeError (caught by the router) if analysis fails entirely.
    """
    # ── Mark as processing ──────────────────────────────────────────────────
    document.status = "processing"
    db.commit()

    try:
        text = document.raw_text or ""
        result: dict = {}

        # ── 1. Try LLM (Ollama) ─────────────────────────────────────────────
        if llm_service.is_llm_available():
            try:
                result = llm_service.analyze_contract_with_llm(text) or {}
                if not isinstance(result, dict):
                    result = {}
                logger.info(f"LLM analysis complete for doc {document.id}")
            except Exception as llm_err:
                logger.warning(f"LLM analysis failed for doc {document.id}: {llm_err}. Falling back.")
                result = {}
        else:
            logger.info(f"Ollama offline — using fallback for doc {document.id}")

        # ── 2. Always run fallback to fill any gaps ─────────────────────────
        try:
            fallback = fallback_analyzer.fallback_analyze(text) or {}
        except Exception as fb_err:
            logger.warning(f"Fallback analyzer error: {fb_err}")
            fallback = {}

        for key, value in fallback.items():
            if not result.get(key):
                result[key] = value

        # ── 3. Compute / normalise scores ───────────────────────────────────
        risks = result.get("risks", [])
        if not isinstance(risks, list):
            risks = []

        try:
            risk_score = fallback_analyzer._risk_score(risks) if risks else 0.0
        except Exception:
            risk_score = 0.0

        compliance_score = result.get("compliance_score") or 0.0
        try:
            compliance_score = float(compliance_score)
        except (TypeError, ValueError):
            compliance_score = 0.0

        # ── 4. Persist to DB ────────────────────────────────────────────────
        analysis = db.query(Analysis).filter(Analysis.document_id == document.id).first()
        if not analysis:
            analysis = Analysis(document_id=document.id)
            db.add(analysis)

        analysis.contract_type            = result.get("contract_type") or "Unknown"
        analysis.parties                  = _safe_json(result.get("parties", []))
        analysis.effective_date           = result.get("effective_date")
        analysis.expiry_date              = result.get("expiry_date")
        analysis.payment_terms            = result.get("payment_terms")
        analysis.renewal_clause           = result.get("renewal_clause")
        analysis.confidentiality_clause   = result.get("confidentiality_clause")
        analysis.termination_clause       = result.get("termination_clause")
        analysis.responsibilities         = result.get("responsibilities")
        analysis.executive_summary        = result.get("executive_summary") or (
            "This document was analyzed using the rule-based fallback engine "
            "(Ollama LLM is offline). Basic clause extraction completed."
        )
        analysis.key_obligations          = _safe_json(result.get("key_obligations", []))
        analysis.important_dates          = _safe_json(result.get("important_dates", []))
        analysis.recommended_actions      = _safe_json(result.get("recommended_actions", []))
        analysis.risk_score               = risk_score
        analysis.compliance_score         = compliance_score
        analysis.risks_json               = _safe_json(risks)

        document.status = "analyzed"
        db.commit()
        db.refresh(analysis)

        # ── 5. Index for semantic search / RAG (best-effort) ────────────────
        try:
            vector_store.index_document(
                document.id, document.filename, document.owner_id, text
            )
        except Exception as vs_err:
            logger.warning(f"Vector store indexing failed (non-fatal): {vs_err}")

        logger.info(f"Analysis complete for doc {document.id} — risk={risk_score:.1f}")
        return analysis

    except Exception as e:
        # ── Always recover document status on any unexpected error ───────────
        try:
            document.status = "failed"
            db.commit()
        except Exception:
            pass
        logger.error(f"Analysis pipeline failed for doc {document.id}: {e}", exc_info=True)
        raise RuntimeError(f"Analysis pipeline error: {str(e)}") from e


def _safe_json(value) -> str:
    """Serialize value to JSON string; fall back to '[]' on any error."""
    try:
        return json.dumps(value)
    except Exception:
        return "[]"


def analysis_to_dict(analysis: Analysis) -> dict:
    """Convert ORM Analysis object to a plain dict for API responses."""
    return {
        "id":                       analysis.id,
        "document_id":              analysis.document_id,
        "contract_type":            analysis.contract_type,
        "parties":                  _safe_json_loads(analysis.parties),
        "effective_date":           analysis.effective_date,
        "expiry_date":              analysis.expiry_date,
        "payment_terms":            analysis.payment_terms,
        "renewal_clause":           analysis.renewal_clause,
        "confidentiality_clause":   analysis.confidentiality_clause,
        "termination_clause":       analysis.termination_clause,
        "responsibilities":         analysis.responsibilities,
        "executive_summary":        analysis.executive_summary,
        "key_obligations":          _safe_json_loads(analysis.key_obligations),
        "important_dates":          _safe_json_loads(analysis.important_dates),
        "recommended_actions":      _safe_json_loads(analysis.recommended_actions),
        "risk_score":               analysis.risk_score or 0.0,
        "compliance_score":         analysis.compliance_score or 0.0,
        "risks":                    _safe_json_loads(analysis.risks_json),
        "created_at":               str(analysis.created_at) if analysis.created_at else None,
    }


def _safe_json_loads(value) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []
