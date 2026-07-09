"""
HTTP client for all backend endpoints.
All timeouts are explicitly set — heavy AI operations get 10 minutes.
All requests are wrapped in _safe() so ConnectionError never crashes Streamlit.
"""
import requests
import streamlit as st

BASE = "http://localhost:8000/api"

# Timeout constants (seconds)
T_FAST   = 30    # simple DB reads
T_UPLOAD = 60    # file upload + text extraction
T_AI     = 600   # AI analysis (Ollama can be slow on CPU)
T_RAG    = 400   # RAG Q&A  
T_CMP    = 400   # contract comparison
T_REPORT = 60    # PDF/DOCX generation


def _headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _handle(resp: requests.Response):
    """Parse response → (data, None) on success, (None, error_str) on failure."""
    if resp.status_code in (200, 201):
        try:
            return resp.json(), None
        except Exception:
            return {}, None
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text
    return None, str(detail)


def _safe(fn):
    """
    Wraps any requests call.
    Catches ConnectionError, Timeout, and any other exception
    so Streamlit never shows an unhandled crash.
    """
    try:
        return fn()
    except requests.exceptions.ConnectionError:
        return (
            None,
            "❌ Cannot reach backend. Make sure FastAPI is running:\n"
            "cd backend → python run.py",
        )
    except requests.exceptions.ReadTimeout:
        return (
            None,
            "⏱️ Request timed out. The AI is still processing — "
            "try again with a shorter document, or switch to a faster model "
            "(e.g. ollama pull phi3:mini).",
        )
    except requests.exceptions.Timeout:
        return (
            None,
            "⏱️ Request timed out. Try a faster Ollama model: phi3:mini or mistral:7b",
        )
    except Exception as e:
        return None, f"❌ Unexpected error: {str(e)}"


# ── Auth ──────────────────────────────────────────────────────────────────────
def register(full_name, email, password):
    return _safe(lambda: _handle(requests.post(
        f"{BASE}/auth/register",
        json={"full_name": full_name, "email": email, "password": password},
        timeout=T_FAST,
    )))

def login(email, password):
    return _safe(lambda: _handle(requests.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": password},
        timeout=T_FAST,
    )))

def get_me():
    return _safe(lambda: _handle(requests.get(
        f"{BASE}/auth/me", headers=_headers(), timeout=T_FAST,
    )))

def update_profile(data: dict):
    return _safe(lambda: _handle(requests.put(
        f"{BASE}/auth/me", json=data, headers=_headers(), timeout=T_FAST,
    )))


# ── Documents ─────────────────────────────────────────────────────────────────
def upload_document(file_bytes, filename, mime):
    return _safe(lambda: _handle(requests.post(
        f"{BASE}/documents/upload",
        headers=_headers(),
        files={"file": (filename, file_bytes, mime)},
        timeout=T_UPLOAD,
    )))

def list_documents():
    return _safe(lambda: _handle(requests.get(
        f"{BASE}/documents/", headers=_headers(), timeout=T_FAST,
    )))

def get_document(doc_id):
    return _safe(lambda: _handle(requests.get(
        f"{BASE}/documents/{doc_id}", headers=_headers(), timeout=T_FAST,
    )))

def analyze_document(doc_id):
    # AI analysis — give it the full 10 minutes
    return _safe(lambda: _handle(requests.post(
        f"{BASE}/documents/{doc_id}/analyze",
        headers=_headers(),
        timeout=T_AI,
    )))

def get_analysis(doc_id):
    return _safe(lambda: _handle(requests.get(
        f"{BASE}/documents/{doc_id}/analysis", headers=_headers(), timeout=T_FAST,
    )))

def delete_document(doc_id):
    return _safe(lambda: _handle(requests.delete(
        f"{BASE}/documents/{doc_id}", headers=_headers(), timeout=T_FAST,
    )))


# ── Dashboard ─────────────────────────────────────────────────────────────────
def get_dashboard_stats():
    return _safe(lambda: _handle(requests.get(
        f"{BASE}/dashboard/stats", headers=_headers(), timeout=T_FAST,
    )))


# ── Search & RAG ──────────────────────────────────────────────────────────────
def semantic_search(query, doc_id=None, top_k=5):
    return _safe(lambda: _handle(requests.post(
        f"{BASE}/search/semantic",
        json={"query": query, "document_id": doc_id, "top_k": top_k},
        headers=_headers(),
        timeout=T_FAST,   # semantic search is fast (no LLM)
    )))

def ask_question(question, doc_id=None):
    # RAG Q&A calls the LLM — needs long timeout
    return _safe(lambda: _handle(requests.post(
        f"{BASE}/search/ask",
        json={"question": question, "document_id": doc_id},
        headers=_headers(),
        timeout=T_RAG,
    )))


# ── Reports ───────────────────────────────────────────────────────────────────
def download_pdf(doc_id):
    try:
        r = requests.get(
            f"{BASE}/reports/{doc_id}/pdf",
            headers=_headers(), timeout=T_REPORT,
        )
        return r.content if r.status_code == 200 else None
    except Exception:
        return None

def download_docx(doc_id):
    try:
        r = requests.get(
            f"{BASE}/reports/{doc_id}/docx",
            headers=_headers(), timeout=T_REPORT,
        )
        return r.content if r.status_code == 200 else None
    except Exception:
        return None


# ── Compare ───────────────────────────────────────────────────────────────────
def compare_documents(doc_id_a, doc_id_b):
    # Comparison calls LLM — needs long timeout
    return _safe(lambda: _handle(requests.post(
        f"{BASE}/compare/",
        json={"document_id_a": doc_id_a, "document_id_b": doc_id_b},
        headers=_headers(),
        timeout=T_CMP,
    )))


# ── Admin ─────────────────────────────────────────────────────────────────────
def admin_list_users():
    return _safe(lambda: _handle(requests.get(
        f"{BASE}/admin/users", headers=_headers(), timeout=T_FAST,
    )))

def admin_toggle_active(user_id):
    return _safe(lambda: _handle(requests.put(
        f"{BASE}/admin/users/{user_id}/toggle-active",
        headers=_headers(), timeout=T_FAST,
    )))

def admin_change_role(user_id, role):
    return _safe(lambda: _handle(requests.put(
        f"{BASE}/admin/users/{user_id}/role?role={role}",
        headers=_headers(), timeout=T_FAST,
    )))

def admin_system_stats():
    return _safe(lambda: _handle(requests.get(
        f"{BASE}/admin/stats", headers=_headers(), timeout=T_FAST,
    )))

def admin_system_logs():
    return _safe(lambda: _handle(requests.get(
        f"{BASE}/admin/logs", headers=_headers(), timeout=T_FAST,
    )))

def admin_delete_document(doc_id):
    return _safe(lambda: _handle(requests.delete(
        f"{BASE}/admin/documents/{doc_id}", headers=_headers(), timeout=T_FAST,
    )))


# ── Health ────────────────────────────────────────────────────────────────────
def health_check():
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        return r.json()
    except Exception:
        return {"status": "unreachable", "llm_online": False}


# ── Bonus Features ────────────────────────────────────────────────────────────
def bonus_translate(document_id: int, target_lang: str, field: str = "executive_summary"):
    return _safe(lambda: _handle(requests.post(
        f"{BASE}/bonus/translate",
        json={"document_id": document_id, "target_lang": target_lang, "field": field},
        headers=_headers(), timeout=T_FAST,
    )))

def bonus_voice(document_id: int, lang: str = "en"):
    try:
        r = requests.get(
            f"{BASE}/bonus/voice/{document_id}?lang={lang}",
            headers=_headers(), timeout=60,
        )
        return r.content if r.status_code == 200 else None
    except Exception:
        return None

def bonus_email_report(document_id, recipient, fmt,
                       smtp_host, smtp_port, smtp_user, smtp_password, use_tls=True):
    return _safe(lambda: _handle(requests.post(
        f"{BASE}/bonus/email-report",
        json={
            "document_id": document_id, "recipient_email": recipient,
            "report_format": fmt, "smtp_host": smtp_host,
            "smtp_port": smtp_port, "smtp_user": smtp_user,
            "smtp_password": smtp_password, "use_tls": use_tls,
        },
        headers=_headers(), timeout=60,
    )))

def bonus_ocr_status():
    return _safe(lambda: _handle(requests.get(
        f"{BASE}/bonus/ocr-status", headers=_headers(), timeout=T_FAST,
    )))

def bonus_compliance(document_id: int):
    return _safe(lambda: _handle(requests.get(
        f"{BASE}/bonus/compliance/{document_id}", headers=_headers(), timeout=T_FAST,
    )))