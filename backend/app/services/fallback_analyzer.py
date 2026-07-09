"""
A deterministic, fully open-source fallback analyzer used when Ollama
is not running. Uses spaCy NER + regex heuristics so the platform is
NEVER blocked on an external LLM dependency.
"""
import re
import spacy
from functools import lru_cache

DATE_REGEX = re.compile(
    r"\b(\d{1,2}(st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{4}|"
    r"(January|February|March|April|May|June|July|August|September|October|November|"
    r"December)\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)

CLAUSE_KEYWORDS = {
    "renewal_clause": ["renew", "renewal", "automatically extend", "auto-renew"],
    "confidentiality_clause": ["confidential", "non-disclosure", "nda", "proprietary information"],
    "termination_clause": ["terminate", "termination", "end this agreement", "cancellation"],
    "payment_terms": ["payment", "invoice", "fee", "compensation", "salary", "consideration"],
    "responsibilities": ["shall be responsible", "duties", "obligations", "responsibilities"],
}

CONTRACT_TYPE_KEYWORDS = {
    "Non-Disclosure Agreement": ["non-disclosure", "nda", "confidentiality agreement"],
    "Employment Agreement": ["employment agreement", "employee", "employer", "salary"],
    "Service Agreement": ["services agreement", "service provider", "scope of work"],
    "Lease Agreement": ["lease", "landlord", "tenant", "premises"],
    "Sales/Purchase Agreement": ["purchase agreement", "buyer", "seller", "goods"],
    "Partnership Agreement": ["partnership", "partners agree", "joint venture"],
    "Vendor/Supplier Agreement": ["vendor", "supplier", "procurement"],
}

RED_FLAG_PATTERNS = [
    ("Unilateral termination", r"(sole discretion|at any time without (cause|notice))",
     "High", "One party may terminate without cause or notice, creating an imbalance of power."),
    ("Auto-renewal trap", r"(automatically renew|auto-renew)(?!.*(notice|opt[- ]out))",
     "Medium", "Contract appears to auto-renew without a clearly stated opt-out mechanism."),
    ("Unlimited liability", r"(unlimited liability|no limitation of liability)",
     "Critical", "No cap on liability exposes a party to potentially unbounded financial risk."),
    ("Ambiguous effort standard", r"(reasonable efforts|best efforts)(?!.*defined)",
     "Low", "Vague performance standard without a measurable definition."),
    ("One-sided indemnification", r"(indemnify.*(solely|exclusively)|hold harmless.*at all times)",
     "High", "Indemnification obligations appear to fall on only one party."),
]


@lru_cache(maxsize=1)
def get_nlp():
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        from spacy.cli import download
        download("en_core_web_sm")
        return spacy.load("en_core_web_sm")


def _find_clause(text: str, keywords: list[str]) -> str | None:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    matches = [s.strip() for s in sentences if any(k.lower() in s.lower() for k in keywords)]
    return " ".join(matches[:3]) if matches else None


def _detect_contract_type(text: str) -> str | None:
    lower = text.lower()
    best, best_count = None, 0
    for ctype, kws in CONTRACT_TYPE_KEYWORDS.items():
        count = sum(lower.count(k) for k in kws)
        if count > best_count:
            best, best_count = ctype, count
    return best


def _extract_parties(text: str) -> list[str]:
    nlp = get_nlp()
    doc = nlp(text[:5000])
    orgs = list(dict.fromkeys([ent.text.strip() for ent in doc.ents if ent.label_ in ("ORG", "PERSON")]))
    return orgs[:6]


def _detect_dates(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0) for m in DATE_REGEX.finditer(text)))[:10]


def _detect_risks(text: str) -> list[dict]:
    risks = []
    for name, pattern, severity, explanation in RED_FLAG_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            excerpt_match = re.search(r"[^.]*" + pattern + r"[^.]*\.", text, re.IGNORECASE)
            risks.append({
                "type": name,
                "description": f"Detected pattern matching '{name}'",
                "severity": severity,
                "confidence": 0.65,
                "explanation": explanation,
                "clause_excerpt": excerpt_match.group(0).strip() if excerpt_match else None,
            })

    # Missing clause checks
    for clause_key, kws in CLAUSE_KEYWORDS.items():
        if not _find_clause(text, kws):
            risks.append({
                "type": f"Missing {clause_key.replace('_', ' ').title()}",
                "description": f"No {clause_key.replace('_', ' ')} detected in the document.",
                "severity": "Medium",
                "confidence": 0.55,
                "explanation": "Standard contracts typically include this clause; its absence "
                                "may leave obligations or protections undefined.",
                "clause_excerpt": None,
            })
    return risks


def _risk_score(risks: list[dict]) -> float:
    weights = {"Low": 5, "Medium": 15, "High": 25, "Critical": 40}
    if not risks:
        return 5.0
    score = sum(weights.get(r["severity"], 10) * r.get("confidence", 0.5) for r in risks)
    return round(min(score, 100.0), 2)


def fallback_analyze(text: str) -> dict:
    dates = _detect_dates(text)
    risks = _detect_risks(text)
    return {
        "contract_type": _detect_contract_type(text),
        "parties": _extract_parties(text),
        "effective_date": dates[0] if dates else None,
        "expiry_date": dates[1] if len(dates) > 1 else None,
        "payment_terms": _find_clause(text, CLAUSE_KEYWORDS["payment_terms"]),
        "renewal_clause": _find_clause(text, CLAUSE_KEYWORDS["renewal_clause"]),
        "confidentiality_clause": _find_clause(text, CLAUSE_KEYWORDS["confidentiality_clause"]),
        "termination_clause": _find_clause(text, CLAUSE_KEYWORDS["termination_clause"]),
        "responsibilities": _find_clause(text, CLAUSE_KEYWORDS["responsibilities"]),
        "executive_summary": " ".join(text.split()[:120]) + ("..." if len(text.split()) > 120 else ""),
        "key_obligations": [s for s in re.split(r"(?<=[.!?])\s+", text) if "shall" in s.lower()][:5],
        "important_dates": dates,
        "recommended_actions": [
            "Have a qualified attorney review all flagged High/Critical risks.",
            "Clarify any ambiguous performance standards before signing.",
            "Confirm renewal and termination notice periods in writing.",
        ],
        "compliance_score": max(0, 100 - _risk_score(risks)),
        "risks": risks,
    }
