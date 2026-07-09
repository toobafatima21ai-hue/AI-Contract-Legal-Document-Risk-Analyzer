"""
llm_service.py  — FIXED
=========================
KEY FIXES vs original:
1. _call_ollama() now catches ALL HTTP errors and returns "" instead of
   raising. A 400 "Bad Request" from Ollama means the requested model is
   not pulled yet — it is treated the same as Ollama being offline so the
   fallback analyzer takes over silently.
2. analyze_contract_with_llm() returns {} on any failure instead of raising,
   so run_full_analysis() always gets a dict and always uses the fallback to
   fill missing fields.
3. answer_question_with_context() returns a readable string on failure
   instead of propagating the HTTP error to the RAG router.
4. compare_contracts_with_llm() returns a safe default dict on failure
   instead of propagating the HTTP error to the compare router.

ROOT CAUSE of the 400 errors:
  Ollama is running but the model configured in settings.OLLAMA_MODEL has
  not been pulled. Fix by running in a terminal:
      ollama pull llama3.1:8b
  Until then the app works correctly using the rule-based fallback.
"""

import json
import logging
import requests
from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert legal contract analyst AI. You read legal documents and
return STRICT, VALID JSON ONLY — no markdown, no commentary, no code fences.
You are precise, conservative, and always explain your reasoning briefly in the
"explanation" fields. If information is not present in the document, use null or an
empty list/string instead of guessing."""


def _call_ollama(prompt: str, system: str = SYSTEM_PROMPT, max_tokens: int = 2048) -> str:
    """
    Call the Ollama /api/generate endpoint.

    NEVER raises — returns "" on any error so callers always get a string
    they can safely pass to safe_json_parse(), which returns {} for empty
    input, which triggers the rule-based fallback everywhere.

    Specific 400 handling: Ollama returns 400 when the model name in
    OLLAMA_MODEL does not exist locally. We log a clear actionable message
    instead of a confusing HTTP traceback.
    """
    url = f"{settings.OLLAMA_HOST}/api/generate"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": max_tokens},
    }
    try:
        resp = requests.post(url, json=payload, timeout=120)

        if resp.status_code == 400:
            # Model not pulled — give the user a clear fix in the logs
            logger.warning(
                f"Ollama returned 400 for model '{settings.OLLAMA_MODEL}'. "
                f"The model is not downloaded yet. Fix: open a terminal and run: "
                f"ollama pull {settings.OLLAMA_MODEL}  "
                f"Until then the rule-based fallback analyzer is used automatically."
            )
            return ""

        resp.raise_for_status()
        return resp.json().get("response", "")

    except requests.exceptions.ConnectionError:
        logger.info("Ollama unreachable (connection refused) — using fallback analyzer.")
        return ""
    except requests.exceptions.Timeout:
        logger.warning("Ollama request timed out after 120 s — using fallback analyzer.")
        return ""
    except requests.exceptions.HTTPError as e:
        logger.warning(f"Ollama HTTP error {e} — using fallback analyzer.")
        return ""
    except Exception as e:
        logger.warning(f"Ollama unexpected error: {e} — using fallback analyzer.")
        return ""


def is_llm_available() -> bool:
    """
    Returns True only if Ollama is reachable AND the configured model exists.
    A 3-second timeout prevents this check from blocking the upload flow.
    """
    try:
        r = requests.get(f"{settings.OLLAMA_HOST}/api/tags", timeout=3)
        if r.status_code != 200:
            return False
        # Check the model is actually pulled
        tags = r.json()
        models = [m.get("name", "") for m in tags.get("models", [])]
        model = settings.OLLAMA_MODEL
        # Ollama stores models as "name:tag" — check both exact and base-name match
        return any(
            m == model or m.startswith(model.split(":")[0])
            for m in models
        )
    except Exception:
        return False


def safe_json_parse(raw: str) -> dict:
    if not raw:
        return {}
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").replace("json\n", "", 1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
    return {}


# ─── Core analysis ───────────────────────────────────────────────────────────

def analyze_contract_with_llm(document_text: str) -> dict:
    """Returns {} on any failure — callers must always handle an empty dict."""
    truncated = document_text[:3500]

    prompt = f"""Analyze the following legal/contract document and return JSON with EXACTLY
this schema:

{{
  "contract_type": string or null,
  "parties": [string],
  "effective_date": string or null,
  "expiry_date": string or null,
  "payment_terms": string or null,
  "renewal_clause": string or null,
  "confidentiality_clause": string or null,
  "termination_clause": string or null,
  "responsibilities": string or null,
  "executive_summary": string,
  "key_obligations": [string],
  "important_dates": [string],
  "recommended_actions": [string],
  "compliance_score": number (0-100),
  "risks": [
    {{
      "type": string,
      "description": string,
      "severity": "Low" | "Medium" | "High" | "Critical",
      "confidence": number (0-1),
      "explanation": string,
      "clause_excerpt": string or null
    }}
  ]
}}

Look specifically for: missing clauses (no termination clause, no confidentiality
clause), high-risk conditions (unilateral termination, auto-renewal traps, unlimited
liability), ambiguous statements, unusual payment terms, and legal red flags.

DOCUMENT:
\"\"\"{truncated}\"\"\"

Return ONLY the JSON object."""

    try:
        raw    = _call_ollama(prompt)
        result = safe_json_parse(raw)
        return result if isinstance(result, dict) else {}
    except Exception as e:
        logger.warning(f"analyze_contract_with_llm unexpected error: {e}")
        return {}


# ─── RAG Q&A ─────────────────────────────────────────────────────────────────

def answer_question_with_context(question: str, context_chunks: list) -> str:
    """
    Returns a plain-text answer string.
    On any LLM failure returns a readable fallback string (never raises).
    """
    context = "\n---\n".join(context_chunks[:6])

    prompt = f"""Using ONLY the context below from a legal document, answer the user's
question concisely and accurately. If the answer isn't in the context, say so clearly.

CONTEXT:
{context}

QUESTION: {question}

Return JSON: {{"answer": string}}"""

    try:
        raw    = _call_ollama(prompt)
        if not raw:
            return _keyword_answer(question, context_chunks)
        parsed = safe_json_parse(raw)
        answer = parsed.get("answer", "")
        if answer:
            return answer
        # LLM returned JSON but no "answer" key — return raw if it looks like prose
        if raw.strip() and not raw.strip().startswith("{"):
            return raw.strip()
        return _keyword_answer(question, context_chunks)
    except Exception as e:
        logger.warning(f"answer_question_with_context error: {e}")
        return _keyword_answer(question, context_chunks)


def _keyword_answer(question: str, chunks: list) -> str:
    """
    Simple keyword-match fallback for when the LLM is unavailable.
    Returns the most relevant chunk as a quoted passage.
    """
    if not chunks:
        return "No relevant content found in the document for your question."

    q_lower = question.lower()
    keywords = [w for w in q_lower.split() if len(w) > 3]

    best_chunk  = chunks[0]
    best_score  = 0
    for chunk in chunks:
        chunk_lower = chunk.lower()
        score = sum(1 for kw in keywords if kw in chunk_lower)
        if score > best_score:
            best_score = score
            best_chunk = chunk

    return (
        f"[Answer generated by keyword search — LLM offline. "
        f"Most relevant passage found:]\n\n{best_chunk[:800]}"
    )


# ─── Contract comparison ──────────────────────────────────────────────────────

def compare_contracts_with_llm(text_a: str, text_b: str) -> dict:
    """
    Returns a comparison dict.
    On any LLM failure returns a safe default dict with a clear message
    (never raises).
    """
    _FALLBACK = {
        "summary_of_changes": (
            "LLM comparison unavailable — Ollama is offline or the model is not pulled. "
            f"Run: ollama pull {settings.OLLAMA_MODEL}"
        ),
        "added_clauses":    [],
        "removed_clauses":  [],
        "risk_differences": [],
        "recommendation":   (
            "Install and start Ollama, pull the model, then retry for a full AI comparison."
        ),
    }

    prompt = f"""Compare these two contract versions. Return JSON:
{{
  "summary_of_changes": string,
  "added_clauses": [string],
  "removed_clauses": [string],
  "risk_differences": [string],
  "recommendation": string
}}

CONTRACT A:
\"\"\"{text_a[:1500]}\"\"\"

CONTRACT B:
\"\"\"{text_b[:1500]}\"\"\"

Return ONLY JSON."""

    try:
        raw    = _call_ollama(prompt, max_tokens=1024)
        result = safe_json_parse(raw)
        if not result or not isinstance(result, dict):
            return _FALLBACK
        # Ensure all expected keys exist
        for key in _FALLBACK:
            if key not in result:
                result[key] = _FALLBACK[key]
        return result
    except Exception as e:
        logger.warning(f"compare_contracts_with_llm error: {e}")
        return _FALLBACK