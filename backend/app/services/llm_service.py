"""
llm_service.py
Gemini-powered LLM service for:

- Contract Analysis
- RAG Question Answering
- Contract Comparison

Falls back safely if Gemini is unavailable.
"""

import json
import logging
import google.generativeai as genai

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Gemini Setup
# ---------------------------------------------------------------------

genai.configure(api_key=settings.GEMINI_API_KEY)

model = genai.GenerativeModel(settings.GEMINI_MODEL)

SYSTEM_PROMPT = """
You are an expert legal contract analyst AI.

Return STRICT VALID JSON ONLY.

No markdown.
No code fences.
No explanations outside JSON.

Be precise, conservative, and never hallucinate.
"""


# ---------------------------------------------------------------------
# Gemini Call
# ---------------------------------------------------------------------

def _call_gemini(prompt: str) -> str:
    try:
        response = model.generate_content(prompt)
        return response.text if response.text else ""
    except Exception as e:
        logger.warning(f"Gemini request failed: {e}")
        return ""


# ---------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------

def is_llm_available() -> bool:
    try:
        response = model.generate_content("Hello")
        return bool(response.text)
    except Exception:
        return False


# ---------------------------------------------------------------------
# JSON Parsing
# ---------------------------------------------------------------------

def safe_json_parse(raw: str) -> dict:
    if not raw:
        return {}

    raw = raw.strip()

    if raw.startswith("```"):
        raw = raw.replace("```json", "")
        raw = raw.replace("```", "")
        raw = raw.strip()

    try:
        return json.loads(raw)

    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")

        if start != -1 and end != -1:
            try:
                return json.loads(raw[start:end + 1])
            except Exception:
                pass

    return {}


# ---------------------------------------------------------------------
# Contract Analysis
# ---------------------------------------------------------------------

def analyze_contract_with_llm(document_text: str) -> dict:

    truncated = document_text[:6000]

    prompt = f"""
Analyze the following legal contract.

Return ONLY JSON.

Schema:

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
  "compliance_score": number,
  "risks": [
    {{
      "type": string,
      "description": string,
      "severity": string,
      "confidence": number,
      "explanation": string,
      "clause_excerpt": string
    }}
  ]
}}

DOCUMENT:

{truncated}
"""

    raw = _call_gemini(prompt)

    if not raw:
        return {}

    result = safe_json_parse(raw)

    if isinstance(result, dict):
        return result

    return {}


# ---------------------------------------------------------------------
# RAG Question Answering
# ---------------------------------------------------------------------

def answer_question_with_context(
    question: str,
    context_chunks: list[str]
) -> str:

    context = "\n---\n".join(context_chunks[:6])

    prompt = f"""
Using ONLY the supplied context,
answer the user's question.

CONTEXT:

{context}

QUESTION:

{question}

Return JSON:

{{
  "answer": "..."
}}
"""

    raw = _call_gemini(prompt)

    if not raw:
        return _keyword_answer(question, context_chunks)

    parsed = safe_json_parse(raw)

    answer = parsed.get("answer")

    if answer:
        return answer

    return _keyword_answer(question, context_chunks)


# ---------------------------------------------------------------------
# Keyword Fallback
# ---------------------------------------------------------------------

def _keyword_answer(
    question: str,
    chunks: list[str]
) -> str:

    if not chunks:
        return "No relevant content found."

    keywords = [
        w.lower()
        for w in question.split()
        if len(w) > 3
    ]

    best_chunk = chunks[0]
    best_score = 0

    for chunk in chunks:

        score = 0

        lower_chunk = chunk.lower()

        for kw in keywords:
            if kw in lower_chunk:
                score += 1

        if score > best_score:
            best_score = score
            best_chunk = chunk

    return (
        "Gemini unavailable. "
        "Most relevant passage found:\n\n"
        + best_chunk[:1000]
    )


# ---------------------------------------------------------------------
# Contract Comparison
# ---------------------------------------------------------------------

def compare_contracts_with_llm(
    text_a: str,
    text_b: str
) -> dict:

    fallback = {
        "summary_of_changes":
            "Gemini comparison unavailable.",
        "added_clauses": [],
        "removed_clauses": [],
        "risk_differences": [],
        "recommendation":
            "Verify your Gemini API key and internet connection."
    }

    prompt = f"""
Compare these two contract versions.

Return ONLY JSON.

Schema:

{{
  "summary_of_changes": string,
  "added_clauses": [string],
  "removed_clauses": [string],
  "risk_differences": [string],
  "recommendation": string
}}

CONTRACT A:

{text_a[:3000]}

CONTRACT B:

{text_b[:3000]}
"""

    raw = _call_gemini(prompt)

    if not raw:
        return fallback

    result = safe_json_parse(raw)

    if not isinstance(result, dict):
        return fallback

    for key in fallback:
        if key not in result:
            result[key] = fallback[key]

    return result