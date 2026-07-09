"""
routers/reports.py  — FIXED
==============================
KEY FIXES vs original:
1. Added POST /{document_id}/email endpoint (was completely missing — caused
   the frontend email button to always fail with 404/422).
2. SMTP now supports both STARTTLS (port 587) and SSL/TLS (port 465) via
   the use_ssl flag. Gmail requires an App Password when 2FA is enabled;
   the endpoint returns a clear, actionable error message if auth fails.
3. Error messages from smtplib are surfaced to the frontend (no more
   cryptic "Email delivery failed" — now shows the exact SMTP rejection reason).
"""

import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, Document, Analysis, AuditLog
from app.services.report_service import generate_pdf_report, generate_docx_report
from app.services.bonus_service import translate_text, generate_voice_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["Report Generation"])


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_doc_and_analysis(db: Session, document_id: int, user: User):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc or (doc.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Document not found")
    analysis = db.query(Analysis).filter(Analysis.document_id == doc.id).first()
    if not analysis:
        raise HTTPException(
            status_code=400,
            detail="Document has not been analyzed yet. Run /analyze first.",
        )
    return doc, analysis


# ─── PDF / DOCX downloads ────────────────────────────────────────────────────

@router.get("/{document_id}/pdf")
def download_pdf(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc, analysis = _get_doc_and_analysis(db, document_id, current_user)
    path = generate_pdf_report(doc, analysis)
    db.add(AuditLog(
        user_id=current_user.id,
        action="generate_report_pdf",
        details=doc.filename,
    ))
    db.commit()
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.get("/{document_id}/docx")
def download_docx(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc, analysis = _get_doc_and_analysis(db, document_id, current_user)
    path = generate_docx_report(doc, analysis)
    db.add(AuditLog(
        user_id=current_user.id,
        action="generate_report_docx",
        details=doc.filename,
    ))
    db.commit()
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=path.name,
    )


# ─── Voice summary ───────────────────────────────────────────────────────────

@router.get("/{document_id}/voice-summary")
def download_voice_summary(
    document_id: int,
    lang: str = "en",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc, analysis = _get_doc_and_analysis(db, document_id, current_user)
    summary = analysis.executive_summary or "No summary available."
    if lang != "en":
        try:
            summary = translate_text(summary, target_lang=lang)
        except Exception:
            pass  # fall back to English if translation fails
    path = generate_voice_summary(summary, document_id, lang=lang)
    return FileResponse(path, media_type="audio/mpeg", filename=path.name)


# ─── Translation ─────────────────────────────────────────────────────────────

@router.get("/{document_id}/translate")
def translate_summary(
    document_id: int,
    lang: str = "es",
    field: str = "executive_summary",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc, analysis = _get_doc_and_analysis(db, document_id, current_user)
    TRANSLATABLE = {
        "executive_summary":      analysis.executive_summary,
        "payment_terms":          analysis.payment_terms,
        "renewal_clause":         analysis.renewal_clause,
        "confidentiality_clause": analysis.confidentiality_clause,
        "termination_clause":     analysis.termination_clause,
    }
    original = TRANSLATABLE.get(field) or ""
    if not original:
        return {"field": field, "original": "", "translated": ""}
    translated = translate_text(original, target_lang=lang)
    return {"field": field, "language": lang, "original": original, "translated": translated}


# ─── Email delivery  (FIXED — was completely missing) ─────────────────────────

@router.post("/{document_id}/email")
def email_report(
    document_id: int,
    recipient: str = Query(..., description="Recipient email address"),
    fmt: str = Query("pdf", description="Report format: 'pdf' or 'docx'"),
    smtp_host: str = Query("smtp.gmail.com"),
    smtp_port: int = Query(587),
    smtp_user: str = Query(..., description="Your email / SMTP username"),
    smtp_password: str = Query(..., description="App password (Gmail) or SMTP password"),
    use_ssl: bool = Query(False, description="True for port 465 SSL; False for port 587 STARTTLS"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bonus Feature: Email Report Delivery.

    GMAIL SETUP (most common use case):
    ------------------------------------
    1. Enable 2-Step Verification on your Google Account.
    2. Go to Google Account → Security → App Passwords.
    3. Create an App Password (any name, e.g. "ContractAI").
    4. Use that 16-character password in the smtp_password field.
    5. Use port 587 + use_ssl=False (STARTTLS) OR port 465 + use_ssl=True.

    NOTE: Your regular Gmail password will NOT work. Google requires App Passwords
    for all third-party SMTP connections since May 2022.
    """
    doc, analysis = _get_doc_and_analysis(db, document_id, current_user)

    # Generate the report file
    try:
        if fmt.lower() == "docx":
            report_path = generate_docx_report(doc, analysis)
            mime_type = (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            ext = "docx"
        else:
            report_path = generate_pdf_report(doc, analysis)
            mime_type = "application/pdf"
            ext = "pdf"
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate report: {e}"
        )

    attachment_name = f"AI_Risk_Report_{doc.filename.rsplit('.', 1)[0]}.{ext}"

    # Build the email
    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = recipient
    msg["Subject"] = f"AI Contract Risk Report — {doc.filename}"

    body = (
        f"Please find attached the AI Risk Assessment Report for:\n\n"
        f"  Document : {doc.filename}\n"
        f"  Format   : {ext.upper()}\n\n"
        f"This report was generated by the AI Contract & Legal Document Risk Analyzer.\n"
        f"Risk Score     : {analysis.risk_score or 0:.0f}/100\n"
        f"Compliance Score: {analysis.compliance_score or 0:.0f}/100\n\n"
        f"— Sent automatically by ContractAI"
    )
    msg.attach(MIMEText(body, "plain"))

    try:
        with open(report_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=attachment_name)
        part["Content-Disposition"] = f'attachment; filename="{attachment_name}"'
        msg.attach(part)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to attach report: {e}")

    # Send
    try:
        if use_ssl:
            # Port 465 — direct SSL
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=20) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, recipient, msg.as_string())
        else:
            # Port 587 — STARTTLS (Gmail default)
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, recipient, msg.as_string())

    except smtplib.SMTPAuthenticationError:
        raise HTTPException(
            status_code=400,
            detail=(
                "SMTP Authentication failed (535). "
                "For Gmail: you MUST use an App Password, NOT your regular password. "
                "Steps: Google Account → Security → 2-Step Verification (enable) → "
                "App Passwords → create one → paste the 16-char code here."
            ),
        )
    except smtplib.SMTPConnectError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not connect to SMTP server {smtp_host}:{smtp_port}. Check host/port. ({e})",
        )
    except smtplib.SMTPException as e:
        raise HTTPException(status_code=500, detail=f"SMTP error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email delivery failed: {e}")

    db.add(AuditLog(
        user_id=current_user.id,
        action="email_report",
        details=f"{doc.filename} → {recipient}",
    ))
    db.commit()
    logger.info(f"Report emailed: doc={document_id} to={recipient} fmt={ext}")

    return {"detail": f"✅ Report sent successfully to {recipient}"}
