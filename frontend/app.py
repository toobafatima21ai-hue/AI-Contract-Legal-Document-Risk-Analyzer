"""
AI-Powered Contract & Legal Document Risk Analyzer
Streamlit Frontend — FIXED VERSION
Run: streamlit run app.py

FIXES vs original:
1. CSS updated for two-tone light/dark theme (light main area, dark sidebar).
2. Feature 4 (OCR) now has a real file uploader — users can actually test OCR
   by uploading a scanned PDF directly from the Bonus Features page.
3. Email UI: shows clear App Password instructions, adds SSL toggle,
   maps parameters correctly to the fixed backend /email endpoint.
4. api.bonus_email_report() now passes use_ssl instead of use_tls so it
   matches the fixed backend query parameter.
"""

import streamlit as st

st.set_page_config(
    page_title="AI Contract Analyzer",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

import json
import api_client as api

# ─── Global CSS — TWO-TONE: dark sidebar + light main area ────────────────────
st.markdown("""
<style>
/* ── Sidebar: keep dark navy ─────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #0f172a !important;
    border-right: 1px solid #1e3a5f;
}
[data-testid="stSidebar"] *,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div {
    color: #e2e8f0 !important;
}
[data-testid="stSidebar"] .stButton button {
    background: #1e293b !important;
    color: #e2e8f0 !important;
    border: 1px solid #334155 !important;
    border-radius: 8px;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: #2563eb !important;
    border-color: #3b82f6 !important;
}
[data-testid="stSidebar"] .stButton [data-baseweb="button"][kind="primary"] button,
[data-testid="stSidebar"] button[kind="primary"] {
    background: #2563eb !important;
    border-color: #3b82f6 !important;
}

/* ── Main area: light / white ────────────────────────────────────────────── */
.main .block-container {
    background: #f0f4f8;
    padding-top: 1.5rem;
}
h1, h2, h3, h4, h5, h6 { color: #0f172a !important; }
p, li, span, label       { color: #1e293b; }

/* ── Branding ────────────────────────────────────────────────────────────── */
.brand-title { font-size:1.4rem; font-weight:800; color:#60a5fa !important; letter-spacing:1px; }
.brand-sub   { font-size:.75rem; color:#94a3b8 !important; margin-top:-6px; }

/* ── Severity badges ─────────────────────────────────────────────────────── */
.badge          { display:inline-block; padding:2px 10px; border-radius:99px; font-size:.75rem; font-weight:700; }
.badge-low      { background:#d1fae5; color:#065f46; }
.badge-medium   { background:#fef3c7; color:#92400e; }
.badge-high     { background:#fee2e2; color:#991b1b; }
.badge-critical { background:#7f1d1d; color:#fca5a5; }

/* ── Stat cards: white with colored numbers ──────────────────────────────── */
.stat-card { background:#ffffff; border:1px solid #e2e8f0; border-radius:12px;
             padding:1.2rem 1.5rem; text-align:center; margin-bottom:8px;
             box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.stat-num  { font-size:2.2rem; font-weight:800; color:#2563eb; }
.stat-lbl  { font-size:.8rem; color:#64748b; margin-top:2px; }

/* ── Risk colours ────────────────────────────────────────────────────────── */
.risk-low  { color:#16a34a; }
.risk-med  { color:#d97706; }
.risk-high { color:#dc2626; }
.risk-crit { color:#991b1b; font-weight:800; }

/* ── Bonus feature cards ─────────────────────────────────────────────────── */
.bonus-card  { background:#ffffff; border:1px solid #dde3ea; border-radius:12px;
               padding:1.4rem; margin-bottom:1.2rem;
               box-shadow: 0 1px 4px rgba(0,0,0,.06); }
.bonus-title { font-size:1.1rem; font-weight:700; color:#1d4ed8; margin-bottom:.3rem; }
.bonus-desc  { font-size:.85rem; color:#475569; margin-bottom:1rem; }

/* ── Grade badge ─────────────────────────────────────────────────────────── */
.grade-badge { font-size:3rem; font-weight:900; }

/* ── Tab bar ─────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab"] { font-weight:600; color:#1e293b; }

/* ── Alert / info boxes use consistent light styling ────────────────────── */
div[data-testid="stAlert"] { border-radius:8px; }
</style>
""", unsafe_allow_html=True)

# ─── Session state defaults ────────────────────────────────────────────────────
for k, v in [
    ("token", None), ("user", None), ("page", "🏠 Dashboard"),
    ("selected_doc_id", None), ("upload_success_msg", None),
    ("upload_error_msg", None), ("file_bytes", None),
    ("file_name", None), ("file_mime", None),
]:
    if k not in st.session_state:
        st.session_state[k] = v


# ─── Helper functions ──────────────────────────────────────────────────────────
def severity_badge(sev):
    cls = {"Low":"low","Medium":"medium","High":"high","Critical":"critical"}.get(sev,"low")
    return f'<span class="badge badge-{cls}">{sev}</span>'


def risk_color(score):
    if score < 25: return "risk-low"
    if score < 50: return "risk-med"
    if score < 75: return "risk-high"
    return "risk-crit"


def show_analysis(analysis):
    risk   = analysis.get("risk_score", 0) or 0
    comply = analysis.get("compliance_score", 0) or 0

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(
        f'<div class="stat-card"><div class="stat-num {risk_color(risk)}">'
        f'{risk:.0f}</div><div class="stat-lbl">Risk Score / 100</div></div>',
        unsafe_allow_html=True,
    )
    c2.markdown(
        f'<div class="stat-card"><div class="stat-num">'
        f'{comply:.0f}</div><div class="stat-lbl">Compliance Score / 100</div></div>',
        unsafe_allow_html=True,
    )
    c3.markdown(
        f'<div class="stat-card"><div class="stat-num">'
        f'{len(analysis.get("risks",[]))}</div><div class="stat-lbl">Issues Detected</div></div>',
        unsafe_allow_html=True,
    )
    c4.markdown(
        f'<div class="stat-card"><div class="stat-num" style="font-size:1rem">'
        f'{analysis.get("contract_type","—")}</div><div class="stat-lbl">Contract Type</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    t1, t2, t3, t4 = st.tabs(["📋 Summary", "⚠️ Risks", "📜 Clauses", "✅ Obligations"])

    with t1:
        st.subheader("Executive Summary")
        st.info(analysis.get("executive_summary") or "_No summary generated._")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Parties Involved**")
            for p in (analysis.get("parties") or []):
                st.markdown(f"- {p}")
            st.markdown(f"**Effective Date:** {analysis.get('effective_date') or 'N/A'}")
            st.markdown(f"**Expiry Date:** {analysis.get('expiry_date') or 'N/A'}")
        with col2:
            st.markdown("**Important Dates**")
            for d in (analysis.get("important_dates") or []):
                st.markdown(f"- {d}")

    with t2:
        st.subheader("AI Risk Assessment")
        risks = analysis.get("risks") or []
        if not risks:
            st.success("✅ No significant risks detected.")
        else:
            for r in sorted(
                risks,
                key=lambda x: {"Critical":0,"High":1,"Medium":2,"Low":3}.get(x.get("severity","Low"),4),
            ):
                conf = int(float(r.get("confidence", 0)) * 100)
                sev  = r.get("severity","Low")
                with st.container(border=True):
                    col_badge, col_conf = st.columns([3, 1])
                    with col_badge:
                        st.markdown(
                            f"{severity_badge(sev)} &nbsp; **{r.get('type','')}**",
                            unsafe_allow_html=True,
                        )
                    with col_conf:
                        st.markdown(f"`confidence: {conf}%`")
                    st.markdown(f"**Description:** {r.get('description','')}")
                    st.markdown(f"**Explanation:** {r.get('explanation','')}")
                    if r.get("clause_excerpt"):
                        st.code(r["clause_excerpt"], language=None)
                    st.progress(conf / 100)

    with t3:
        st.subheader("Key Clause Extraction")
        for label, val in [
            ("💳 Payment Terms",    analysis.get("payment_terms")),
            ("🔄 Renewal Clause",   analysis.get("renewal_clause")),
            ("🔒 Confidentiality",  analysis.get("confidentiality_clause")),
            ("🛑 Termination",      analysis.get("termination_clause")),
            ("📋 Responsibilities", analysis.get("responsibilities")),
        ]:
            with st.container(border=True):
                if val:
                    st.markdown(f"**{label}** ✅")
                    st.write(val)
                else:
                    st.markdown(f"**{label}** ⚠️")
                    st.warning("Not found in document — this may be a risk.")

    with t4:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Key Obligations")
            for ob in (analysis.get("key_obligations") or []):
                st.markdown(f"• {ob}")
            if not analysis.get("key_obligations"):
                st.info("No specific obligations extracted.")
        with col2:
            st.subheader("Recommended Actions")
            for act in (analysis.get("recommended_actions") or []):
                st.markdown(f"✅ {act}")
            if not analysis.get("recommended_actions"):
                st.info("No recommended actions.")


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: LOGIN / REGISTER
# ═══════════════════════════════════════════════════════════════════════════════
def page_login():
    st.markdown(
        '<h1 style="text-align:center;color:#0f172a">⚖️ AI Contract Analyzer</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="text-align:center;color:#64748b">Intelligent Legal Document Risk Analysis</p>',
        unsafe_allow_html=True,
    )
    col = st.columns([1, 2, 1])[1]
    with col:
        t1, t2 = st.tabs(["🔑 Login", "📝 Register"])
        with t1:
            email = st.text_input("Email", key="li_email")
            pw    = st.text_input("Password", type="password", key="li_pw")
            if st.button("Sign In", use_container_width=True, type="primary"):
                if not email or not pw:
                    st.error("Please fill in all fields.")
                else:
                    data, err = api.login(email, pw)
                    if err:
                        st.error(f"Login failed: {err}")
                    else:
                        st.session_state["token"] = data["access_token"]
                        st.session_state["user"]  = data["user"]
                        st.rerun()
        with t2:
            name = st.text_input("Full Name", key="reg_name")
            em   = st.text_input("Email", key="reg_email")
            pw1  = st.text_input("Password", type="password", key="reg_pw")
            pw2  = st.text_input("Confirm Password", type="password", key="reg_pw2")
            if st.button("Create Account", use_container_width=True, type="primary"):
                if not all([name, em, pw1, pw2]):
                    st.error("All fields are required.")
                elif pw1 != pw2:
                    st.error("Passwords do not match.")
                else:
                    data, err = api.register(name, em, pw1)
                    if err:
                        st.error(f"Registration failed: {err}")
                    else:
                        st.session_state["token"] = data["access_token"]
                        st.session_state["user"]  = data["user"]
                        st.success("Account created!")
                        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
def page_dashboard():
    st.title("📊 AI Insights Dashboard")
    health = api.health_check()
    llm_status =f"LLM: {'🟢 Gemini API Online' if llm_ok else '🔴 Gemini Offline — rule-based fallback active'}"
    st.caption(f"API: {health.get('status','?')} | LLM: {llm_status}")

    stats, err = api.get_dashboard_stats()
    if err:
        st.error(f"Could not load stats: {err}")
        return

    c1, c2, c3 = st.columns(3)
    c1.markdown(
        f'<div class="stat-card"><div class="stat-num">{stats["total_documents"]}</div>'
        f'<div class="stat-lbl">Total Documents</div></div>',
        unsafe_allow_html=True,
    )
    c2.markdown(
        f'<div class="stat-card"><div class="stat-num {risk_color(stats["average_risk_score"])}">'
        f'{stats["average_risk_score"]:.1f}</div><div class="stat-lbl">Average Risk Score</div></div>',
        unsafe_allow_html=True,
    )
    c3.markdown(
        f'<div class="stat-card"><div class="stat-num risk-high">{stats["high_risk_documents"]}</div>'
        f'<div class="stat-lbl">High-Risk Documents (≥50)</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🔥 Most Frequently Detected Risks")
        freq = stats.get("frequently_detected_risks") or []
        if freq:
            import pandas as pd
            st.bar_chart(pd.DataFrame(freq).set_index("type")["count"])
        else:
            st.info("Analyze documents to populate risk data.")
    with col2:
        st.subheader("🕐 Recent Documents")
        recent = stats.get("recent_documents") or []
        if recent:
            for d in recent:
                icon = {"uploaded":"📄","processing":"⏳","analyzed":"✅","failed":"❌"}.get(d["status"],"📄")
                if st.button(f"{icon} {d['filename']}", key=f"dd_{d['id']}"):
                    st.session_state["selected_doc_id"] = d["id"]
                    st.session_state["page"] = "📄 My Documents"
                    st.rerun()
        else:
            st.info("No documents yet. Upload one to get started!")


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: MY DOCUMENTS
# ═══════════════════════════════════════════════════════════════════════════════
def page_documents():
    st.title("📄 My Documents")

    health = api.health_check()
    if health.get("status") == "unreachable":
        st.error(
            "❌ **Cannot connect to the backend server.**\n\n"
            "Open a new terminal and run:\n\n"
            "```\ncd backend\n"
            ".venv\\Scripts\\activate    # Windows\n"
            "source .venv/bin/activate  # Mac/Linux\n"
            "python run.py\n```"
        )
        return

    st.subheader("⬆️ Upload New Document")
    with st.container(border=True):
        if st.session_state.get("upload_success_msg"):
            st.success(st.session_state["upload_success_msg"])
            st.session_state["upload_success_msg"] = None
        if st.session_state.get("upload_error_msg"):
            st.error(st.session_state["upload_error_msg"])
            st.session_state["upload_error_msg"] = None

        mime_map = {
            "pdf":  "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt":  "text/plain",
        }
        uploaded = st.file_uploader(
            "Drag & drop or click to upload",
            type=["pdf", "docx", "txt"],
            help="Max 25 MB — PDF, DOCX, TXT supported. Scanned PDFs auto-trigger OCR if Tesseract is installed.",
        )
        if uploaded is not None:
            ext = uploaded.name.rsplit(".", 1)[-1].lower()
            if st.session_state.get("file_name") != uploaded.name:
                st.session_state["file_bytes"] = uploaded.read()
                st.session_state["file_name"]  = uploaded.name
                st.session_state["file_mime"]  = mime_map.get(ext, "application/octet-stream")
            size_kb = len(st.session_state["file_bytes"]) // 1024
            st.info(f"📄 Ready: **{uploaded.name}** ({size_kb} KB)")
            if st.button("📤 Upload Document", type="primary", use_container_width=True):
                with st.spinner("Uploading and extracting text…"):
                    data, err = api.upload_document(
                        st.session_state["file_bytes"],
                        st.session_state["file_name"],
                        st.session_state["file_mime"],
                    )
                if err:
                    st.session_state["upload_error_msg"] = f"Upload failed: {err}"
                else:
                    st.session_state["upload_success_msg"] = (
                        f"✅ Uploaded: **{data['filename']}** (ID {data['id']}) "
                        f"— click 🤖 Analyze below to run AI analysis."
                    )
                    st.session_state["selected_doc_id"] = data["id"]
                    st.session_state["file_bytes"] = None
                    st.session_state["file_name"]  = None
                    st.session_state["file_mime"]  = None
                st.rerun()

    docs, err = api.list_documents()
    if err:
        st.error(f"Failed to load documents: {err}")
        return
    if not docs:
        st.info("📭 No documents yet. Upload one above to get started!")
        return

    st.markdown("---")
    st.subheader(f"📁 Your Documents ({len(docs)})")

    sel = st.session_state.get("selected_doc_id")
    doc_names = {f"{d['filename']} [{d['status'].upper()}]": d["id"] for d in docs}
    default_ix = 0
    if sel:
        ids = list(doc_names.values())
        if sel in ids:
            default_ix = ids.index(sel)

    chosen_label = st.selectbox(
        "Select a document to view / analyze",
        list(doc_names.keys()),
        index=default_ix,
        key="doc_selector",
    )
    doc_id = doc_names[chosen_label]
    doc    = next(d for d in docs if d["id"] == doc_id)
    st.session_state["selected_doc_id"] = doc_id

    with st.container(border=True):
        ca, cb, cc = st.columns(3)
        with ca:
            if st.button("🤖 Analyze with AI", use_container_width=True, type="primary"):
                with st.spinner("Running AI analysis… (30–90 s on first run)"):
                    _, err = api.analyze_document(doc["id"])
                if err:
                    st.error(f"Analysis failed: {err}")
                else:
                    st.success("✅ Analysis complete!")
                    st.rerun()
        with cb:
            if doc["status"] == "analyzed":
                pdf_bytes = api.download_pdf(doc["id"])
                if pdf_bytes:
                    st.download_button(
                        "⬇️ PDF Report", data=pdf_bytes,
                        file_name=f"report_{doc['id']}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{doc['id']}", use_container_width=True,
                    )
        with cc:
            if st.button("🗑️ Delete Document", use_container_width=True):
                _, err = api.delete_document(doc["id"])
                if err:
                    st.error(f"Delete failed: {err}")
                else:
                    st.session_state["selected_doc_id"] = None
                    st.rerun()

        st.caption(
            f"📅 Uploaded: {doc['upload_date'][:19]}  |  "
            f"🌐 Language: {doc['language'].upper()}  |  "
            f"📎 Type: {doc['file_type'].upper()}  |  Status: {doc['status'].upper()}"
        )

    if doc["status"] == "analyzed":
        analysis, aerr = api.get_analysis(doc["id"])
        if aerr:
            st.warning(f"Could not load analysis: {aerr}")
        elif analysis:
            show_analysis(analysis)
            st.markdown("---")
            st.markdown("##### 📥 Download Reports")
            r1, r2 = st.columns(2)
            with r1:
                docx_b = api.download_docx(doc["id"])
                if docx_b:
                    st.download_button(
                        "📝 DOCX Report", data=docx_b,
                        file_name=f"report_{doc['id']}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"docx_{doc['id']}", use_container_width=True,
                    )
            with r2:
                st.caption("👉 Voice, Translation & Email → ✨ Bonus Features")
    elif doc["status"] == "processing":
        st.info("⏳ Analysis in progress… refresh in a few seconds.")
    elif doc["status"] == "uploaded":
        st.info("📄 Click **🤖 Analyze with AI** above to start.")
    elif doc["status"] == "failed":
        st.error("❌ Analysis failed. Try clicking Analyze again.")


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: SEARCH & Q&A
# ═══════════════════════════════════════════════════════════════════════════════
def page_search():
    st.title("🔍 Semantic Search & RAG Q&A")
    st.caption("Search your contracts with natural language or ask the AI a question.")

    docs, _ = api.list_documents()
    analyzed = [d for d in (docs or []) if d["status"] == "analyzed"]
    if not analyzed:
        st.warning("⚠️ Analyze at least one document first to use search.")
        return

    doc_options = {"All my documents": None} | {d["filename"]: d["id"] for d in analyzed}
    chosen_name = st.selectbox("Scope search to:", list(doc_options.keys()))
    chosen_id   = doc_options[chosen_name]

    t1, t2 = st.tabs(["🔎 Semantic Search", "🤖 Ask the AI (RAG)"])
    with t1:
        st.markdown(
            "**Example queries:** `Show payment terms` · "
            "`Find confidentiality clauses` · "
            "`What are the termination conditions?` · "
            "`Show renewal policy`"
        )
        query = st.text_input("Search query", placeholder="e.g. automatic renewal notice period")
        top_k = st.slider("Number of results", 1, 10, 5)
        if st.button("🔍 Search", type="primary"):
            if not query:
                st.warning("Enter a search query.")
            else:
                with st.spinner("Searching…"):
                    results, err = api.semantic_search(query, chosen_id, top_k)
                if err:
                    st.error(err)
                elif not results:
                    st.info("No matching content found.")
                else:
                    for i, r in enumerate(results, 1):
                        with st.container(border=True):
                            st.markdown(f"**#{i} 📄 {r['filename']}** — similarity `{r['score']:.2f}`")
                            st.markdown(r["chunk_text"])

    with t2:
        st.markdown("Ask the AI a question — it retrieves relevant passages then generates a grounded answer **(RAG)**.")
        question = st.text_input(
            "Your question",
            placeholder="Can either party terminate this agreement without cause?",
        )
        if st.button("🤖 Ask AI", type="primary"):
            if not question:
                st.warning("Enter a question.")
            else:
                with st.spinner("Searching document + generating answer…"):
                    result, err = api.ask_question(question, chosen_id)
                if err:
                    st.error(err)
                else:
                    st.success("**AI Answer:**")
                    st.write(result.get("answer", ""))
                    st.markdown("**📚 Sources the AI used:**")
                    for s in result.get("sources", []):
                        with st.container(border=True):
                            st.caption(f"📄 {s['filename']} — relevance: {s['score']:.2f}")
                            st.code(s["chunk_text"], language=None)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: COMPARE CONTRACTS
# ═══════════════════════════════════════════════════════════════════════════════
def page_compare():
    st.title("🔀 AI Contract Version Comparison")
    st.caption("Select two contracts — AI identifies added/removed clauses and risk changes.")

    docs, _ = api.list_documents()
    doc_map  = {d["filename"]: d["id"] for d in (docs or [])}
    if len(doc_map) < 2:
        st.warning("⚠️ Upload at least 2 documents to use the comparison feature.")
        return

    col1, col2 = st.columns(2)
    with col1:
        name_a = st.selectbox("📄 Contract A", list(doc_map.keys()), key="cmp_a")
    with col2:
        remaining = [n for n in doc_map if n != name_a]
        name_b = st.selectbox("📄 Contract B", remaining, key="cmp_b")

    if st.button("⚖️ Compare Contracts", type="primary"):
        with st.spinner("AI is comparing contracts…"):
            result, err = api.compare_documents(doc_map[name_a], doc_map[name_b])
        if err:
            st.error(err)
        else:
            st.subheader("📝 Summary of Changes")
            st.info(result.get("summary_of_changes", ""))
            rc1, rc2 = st.columns(2)
            with rc1:
                st.markdown("**✅ Added / Changed Clauses**")
                for x in (result.get("added_clauses") or []):
                    st.markdown(f"+ {x}")
            with rc2:
                st.markdown("**❌ Removed Clauses**")
                for x in (result.get("removed_clauses") or []):
                    st.markdown(f"- {x}")
            for rd in (result.get("risk_differences") or []):
                st.warning(f"⚠️ {rd}")
            if result.get("recommendation"):
                st.success(f"💡 {result['recommendation']}")


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: ✨ BONUS FEATURES
# ═══════════════════════════════════════════════════════════════════════════════
def page_bonus():
    st.title("✨ Bonus Features")
    st.markdown("All 9 bonus features in one place.")

    docs, _     = api.list_documents()
    analyzed    = [d for d in (docs or []) if d["status"] == "analyzed"]
    all_docs    = docs or []
    doc_map     = {d["filename"]: d["id"] for d in analyzed}
    all_doc_map = {d["filename"]: d["id"] for d in all_docs}

    health      = api.health_check()
    ocr_info, _ = api.bonus_ocr_status()

    col1, col2, col3 = st.columns(3)
    col1.metric("LLM (Ollama)",      "🟢 Online" if health.get("llm_online")              else "🔴 Offline")
    col2.metric("OCR (Tesseract)",   "🟢 Ready"  if (ocr_info or {}).get("ocr_available") else "🔴 Not installed")
    col3.metric("Translation / TTS", "🟢 Ready")

    st.markdown("---")

    # ── FEATURE 1: RAG Q&A ────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<div class="bonus-title">🤖 Feature 1 — RAG-Based Question Answering</div>', unsafe_allow_html=True)
        st.markdown('<div class="bonus-desc">Ask any question about your contracts. AI retrieves relevant passages from ChromaDB then generates a grounded answer using the local LLM.</div>', unsafe_allow_html=True)
        if not analyzed:
            st.warning("Analyze a document first.")
        else:
            rag_doc_name = st.selectbox("Document scope", ["All my documents"] + list(doc_map.keys()), key="rag_doc")
            rag_doc_id   = None if rag_doc_name == "All my documents" else doc_map[rag_doc_name]
            rag_q = st.text_input("Your question", placeholder="What happens if payment is late?", key="rag_q")
            if st.button("🤖 Ask AI", key="rag_ask", type="primary"):
                if not rag_q:
                    st.warning("Enter a question.")
                else:
                    with st.spinner("Searching document + generating answer…"):
                        result, err = api.ask_question(rag_q, rag_doc_id)
                    if err:
                        st.error(err)
                    else:
                        st.success("**Answer:**")
                        st.write(result.get("answer", ""))
                        for s in result.get("sources", []):
                            with st.container(border=True):
                                st.caption(f"📄 {s['filename']} — relevance: {s['score']:.2f}")
                                st.code(s["chunk_text"], language=None)

    # ── FEATURE 2: Multi-Language ─────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<div class="bonus-title">🌐 Feature 2 — Multi-Language Document Analysis</div>', unsafe_allow_html=True)
        st.markdown('<div class="bonus-desc">Translate any extracted clause or summary into 13+ languages using open-source deep-translator. No API key required.</div>', unsafe_allow_html=True)
        LANGUAGES = {
            "Spanish":"es","French":"fr","German":"de","Arabic":"ar","Urdu":"ur",
            "Hindi":"hi","Chinese (Simplified)":"zh-CN","Portuguese":"pt",
            "Italian":"it","Turkish":"tr","Russian":"ru","Japanese":"ja","Korean":"ko",
        }
        FIELDS = {
            "Executive Summary":"executive_summary","Payment Terms":"payment_terms",
            "Renewal Clause":"renewal_clause","Confidentiality Clause":"confidentiality_clause",
            "Termination Clause":"termination_clause",
        }
        if not analyzed:
            st.warning("Analyze a document first.")
        else:
            ml_c1, ml_c2, ml_c3 = st.columns(3)
            with ml_c1: ml_doc  = st.selectbox("Document", list(doc_map.keys()), key="ml_doc")
            with ml_c2: ml_lang = st.selectbox("Translate to", list(LANGUAGES.keys()), key="ml_lang")
            with ml_c3: ml_fld  = st.selectbox("Field", list(FIELDS.keys()), key="ml_fld")
            if st.button("🌐 Translate", key="ml_go", type="primary"):
                with st.spinner("Translating…"):
                    result, err = api.bonus_translate(doc_map[ml_doc], LANGUAGES[ml_lang], FIELDS[ml_fld])
                if err:
                    st.error(err)
                else:
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("**Original (English)**")
                        st.info(result.get("original", ""))
                    with col_b:
                        st.markdown(f"**{ml_lang} Translation**")
                        st.success(result.get("translated", ""))

    # ── FEATURE 3: AI Clause Comparison ──────────────────────────────────────
    with st.container(border=True):
        st.markdown('<div class="bonus-title">🔀 Feature 3 — AI Clause Comparison & Version Comparison</div>', unsafe_allow_html=True)
        st.markdown('<div class="bonus-desc">Compare two contract versions. AI identifies added clauses, removed clauses, risk changes, and gives a legal recommendation.</div>', unsafe_allow_html=True)
        if len(all_doc_map) < 2:
            st.warning("Upload at least 2 documents to compare.")
        else:
            cmp_c1, cmp_c2 = st.columns(2)
            with cmp_c1: cmp_a = st.selectbox("📄 Contract A", list(all_doc_map.keys()), key="cmp_bonus_a")
            with cmp_c2:
                rem   = [n for n in all_doc_map if n != cmp_a]
                cmp_b = st.selectbox("📄 Contract B", rem, key="cmp_bonus_b")
            if st.button("⚖️ Run AI Comparison", key="cmp_go", type="primary"):
                with st.spinner("AI is comparing contracts…"):
                    result, err = api.compare_documents(all_doc_map[cmp_a], all_doc_map[cmp_b])
                if err:
                    st.error(err)
                else:
                    st.subheader("📝 AI Summary")
                    st.info(result.get("summary_of_changes", ""))
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        st.markdown("**✅ Added**")
                        for x in (result.get("added_clauses") or []): st.markdown(f"+ {x}")
                    with rc2:
                        st.markdown("**❌ Removed**")
                        for x in (result.get("removed_clauses") or []): st.markdown(f"- {x}")
                    for rd in (result.get("risk_differences") or []): st.warning(f"⚠️ {rd}")
                    if result.get("recommendation"): st.success(f"💡 {result['recommendation']}")

    # ── FEATURE 4: OCR — FIXED (actual file uploader added) ──────────────────
    with st.container(border=True):
        st.markdown('<div class="bonus-title">📷 Feature 4 — OCR for Scanned Documents</div>', unsafe_allow_html=True)
        st.markdown('<div class="bonus-desc">Upload a scanned or image-based PDF. The system automatically falls back to Tesseract OCR when normal text extraction returns < 30 characters.</div>', unsafe_allow_html=True)

        ocr_data = ocr_info or {}
        if ocr_data.get("ocr_available"):
            st.success(f"✅ OCR is ready! Tesseract version: {ocr_data.get('tesseract_version','?')}")
        else:
            st.warning("⚠️ Tesseract not installed — OCR fallback disabled. Install instructions below.")

        # ── Actual scanned PDF uploader (this was missing in the original) ──
        st.markdown("#### 📤 Upload & Analyze a Scanned PDF")
        st.caption(
            "Upload any image-based / scanned PDF here. "
            "If Tesseract is installed, OCR runs automatically. "
            "If not, the raw extraction result is saved with a note."
        )

        ocr_file = st.file_uploader(
            "Choose a scanned PDF file",
            type=["pdf"],
            key="ocr_scanned_upload",
            help="Image-based PDFs (scanned pages) — Tesseract OCR extracts text from each page.",
        )

        if ocr_file is not None:
            ocr_bytes = ocr_file.read()
            size_kb   = len(ocr_bytes) // 1024
            st.info(f"📄 Selected: **{ocr_file.name}** ({size_kb} KB)")

            if st.button("🔍 Run OCR + Analyze", key="ocr_run_btn", type="primary", use_container_width=True):
                # Step 1: Upload
                with st.spinner("📤 Uploading and running OCR text extraction…"):
                    upload_data, upload_err = api.upload_document(
                        ocr_bytes, ocr_file.name, "application/pdf"
                    )

                if upload_err:
                    st.error(f"❌ Upload failed: {upload_err}")
                else:
                    ocr_doc_id = upload_data["id"]
                    st.success(f"✅ Uploaded (Document ID: {ocr_doc_id})")

                    # Step 2: Analyze
                    with st.spinner("🤖 Running AI analysis on OCR text…"):
                        _, analyze_err = api.analyze_document(ocr_doc_id)

                    if analyze_err:
                        st.error(f"❌ Analysis failed: {analyze_err}")
                        st.info(
                            "The document was uploaded. You can retry analysis from "
                            "📄 My Documents → select the file → click 🤖 Analyze with AI."
                        )
                    else:
                        st.success("✅ OCR + AI Analysis complete!")
                        st.session_state["selected_doc_id"] = ocr_doc_id
                        # Show the analysis results inline on this page
                        analysis, aerr = api.get_analysis(ocr_doc_id)
                        if aerr:
                            st.warning(f"Analysis done but could not load results: {aerr}")
                            st.info("👉 Go to **📄 My Documents** to view the full report.")
                        elif analysis:
                            st.markdown("---")
                            st.markdown("#### 📊 Analysis Results")
                            show_analysis(analysis)
                            # Download buttons
                            dl1, dl2 = st.columns(2)
                            with dl1:
                                pdf_b = api.download_pdf(ocr_doc_id)
                                if pdf_b:
                                    st.download_button(
                                        "⬇️ PDF Report", data=pdf_b,
                                        file_name=f"ocr_report_{ocr_doc_id}.pdf",
                                        mime="application/pdf",
                                        key=f"ocr_pdf_{ocr_doc_id}",
                                        use_container_width=True,
                                    )
                            with dl2:
                                docx_b = api.download_docx(ocr_doc_id)
                                if docx_b:
                                    st.download_button(
                                        "📝 DOCX Report", data=docx_b,
                                        file_name=f"ocr_report_{ocr_doc_id}.docx",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        key=f"ocr_docx_{ocr_doc_id}",
                                        use_container_width=True,
                                    )
                        # Navigate to My Documents with this doc selected
                        st.session_state["selected_doc_id"] = ocr_doc_id
                        st.session_state["page"] = "📄 My Documents"
                        st.rerun()

        st.markdown("---")

        # ── Install instructions (collapsed by default) ───────────────────
        if not ocr_data.get("ocr_available"):
            st.markdown("**How to enable OCR:**")
            tab_py, tab_win, tab_linux, tab_mac = st.tabs(["Python packages", "Windows", "Linux", "Mac"])
            with tab_py:
                st.code("pip install pytesseract pdf2image", language="bash")
            with tab_win:
                st.code(
                    "# 1. Download Tesseract installer:\n"
                    "#    https://github.com/UB-Mannheim/tesseract/wiki\n"
                    "# 2. Install to e.g. C:\\Program Files\\Tesseract-OCR\n"
                    "# 3. Add that folder to your Windows PATH\n"
                    "# 4. Download poppler for Windows:\n"
                    "#    https://github.com/oschwartz10612/poppler-windows/releases\n"
                    "# 5. Add poppler/bin to your Windows PATH\n"
                    "# 6. Restart your backend (python run.py)",
                    language="bash",
                )
            with tab_linux:
                st.code(
                    "sudo apt update\n"
                    "sudo apt install tesseract-ocr poppler-utils",
                    language="bash",
                )
            with tab_mac:
                st.code("brew install tesseract poppler", language="bash")
            st.caption("After installing, restart the backend and refresh this page.")

    # ── FEATURE 5: Voice Summary ──────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<div class="bonus-title">🔊 Feature 5 — Voice Summary Generation</div>', unsafe_allow_html=True)
        st.markdown('<div class="bonus-desc">Converts the AI executive summary into an MP3 audio file using gTTS (free, no API key). Supports 7 languages.</div>', unsafe_allow_html=True)
        VOICE_LANGS = {"English":"en","Spanish":"es","French":"fr","German":"de","Arabic":"ar","Urdu":"ur","Chinese":"zh-CN"}
        if not analyzed:
            st.warning("Analyze a document first.")
        else:
            v_c1, v_c2 = st.columns(2)
            with v_c1: v_doc  = st.selectbox("Document", list(doc_map.keys()), key="v_doc")
            with v_c2: v_lang = st.selectbox("Language", list(VOICE_LANGS.keys()), key="v_lang")
            if st.button("🎙️ Generate Voice Summary", key="v_go", type="primary"):
                with st.spinner("Generating audio…"):
                    audio_bytes = api.bonus_voice(doc_map[v_doc], VOICE_LANGS[v_lang])
                if audio_bytes:
                    st.success("✅ Voice summary ready!")
                    st.audio(audio_bytes, format="audio/mp3")
                    st.download_button(
                        "⬇️ Download MP3", data=audio_bytes,
                        file_name="voice_summary.mp3", mime="audio/mpeg", key="v_dl",
                    )
                else:
                    st.error("Failed to generate audio. Ensure gTTS is installed: `pip install gTTS`")

    # ── FEATURE 6: Email — FIXED ──────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<div class="bonus-title">📧 Feature 6 — Email Report Delivery</div>', unsafe_allow_html=True)
        st.markdown('<div class="bonus-desc">Send the AI risk report (PDF or DOCX) to any email address. Works with Gmail App Passwords, Outlook, and any SMTP server.</div>', unsafe_allow_html=True)

        # Gmail App Password instructions — always visible
        with st.expander("ℹ️ Gmail App Password setup (required — read before filling the form)", expanded=False):
            st.markdown("""
**Why App Password?** Google blocked regular password login for SMTP in May 2022.
You MUST use a 16-character App Password instead.

**Steps (takes ~2 minutes):**
1. Go to **myaccount.google.com** → **Security**
2. Enable **2-Step Verification** (if not already on)
3. Search for **"App Passwords"** in the Security page
4. Click App Passwords → choose App: *Mail*, Device: *Other* → name it "ContractAI"
5. Google gives you a **16-character password** (e.g. `abcd efgh ijkl mnop`)
6. **Remove the spaces** and paste it in the *App Password* field below

**Outlook:** Use your normal password but enable SMTP access under Account Settings → Apps & Devices.
**Port guide:** 587 + STARTTLS (most common) or 465 + SSL.
            """)

        if not analyzed:
            st.warning("Analyze a document first.")
        else:
            em_c1, em_c2 = st.columns(2)
            with em_c1:
                em_doc = st.selectbox("Document to send", list(doc_map.keys()), key="em_doc")
                em_to  = st.text_input("Recipient email", placeholder="receiver@example.com", key="em_to")
                em_fmt = st.radio("Report format", ["PDF", "DOCX"], horizontal=True, key="em_fmt")
            with em_c2:
                st.markdown("**Your SMTP Settings**")
                em_host = st.text_input("SMTP Host",           value="smtp.gmail.com",  key="em_host")
                em_port = st.number_input("SMTP Port",          value=587, min_value=1,  key="em_port", step=1)
                em_user = st.text_input("Your sender email",                             key="em_user")
                em_pass = st.text_input("App Password",         type="password",         key="em_pass",
                                         help="Gmail: 16-char App Password (NO spaces). NOT your login password.")
                em_ssl  = st.checkbox("Use direct SSL (port 465)", value=False,          key="em_ssl",
                                       help="Uncheck for port 587 STARTTLS (Gmail default). Check for port 465 SSL.")

            if st.button("📤 Send Report by Email", key="em_go", type="primary"):
                if not all([em_to, em_host, em_user, em_pass]):
                    st.error("❌ Fill in all SMTP fields before sending.")
                elif "@" not in em_to:
                    st.error("❌ Enter a valid recipient email address.")
                else:
                    with st.spinner("Sending email…"):
                        result, err = api.bonus_email_report(
                            document_id=doc_map[em_doc],
                            recipient=em_to,
                            fmt=em_fmt.lower(),
                            smtp_host=em_host,
                            smtp_port=int(em_port),
                            smtp_user=em_user,
                            smtp_password=em_pass,
                            use_ssl=em_ssl,          # ← FIXED: was use_tls, now use_ssl
                        )
                    if err:
                        st.error(f"❌ {err}")
                        if "535" in str(err) or "Authentication" in str(err):
                            st.info(
                                "💡 Gmail fix: use an **App Password** (not your login password). "
                                "See the setup instructions above."
                            )
                    else:
                        st.success(f"✅ {result.get('detail','Email sent successfully!')}")

    # ── FEATURE 7: AI Compliance Score ───────────────────────────────────────
    with st.container(border=True):
        st.markdown('<div class="bonus-title">📊 Feature 7 — AI Compliance Score</div>', unsafe_allow_html=True)
        st.markdown('<div class="bonus-desc">Detailed compliance breakdown: letter grade A–F, clause coverage %, severity counts, and overall health score.</div>', unsafe_allow_html=True)
        if not analyzed:
            st.warning("Analyze a document first.")
        else:
            cs_doc = st.selectbox("Document", list(doc_map.keys()), key="cs_doc")
            if st.button("📊 Get Compliance Score", key="cs_go", type="primary"):
                with st.spinner("Calculating…"):
                    result, err = api.bonus_compliance(doc_map[cs_doc])
                if err:
                    st.error(err)
                else:
                    grade       = result.get("grade","?")
                    grade_color = {"A":"#16a34a","B":"#65a30d","C":"#d97706","D":"#ea580c","F":"#dc2626"}.get(grade,"#64748b")
                    cs_c1, cs_c2, cs_c3 = st.columns(3)
                    with cs_c1:
                        st.markdown(
                            f'<div class="stat-card"><div class="grade-badge" style="color:{grade_color}">{grade}</div>'
                            f'<div class="stat-lbl">Compliance Grade</div></div>', unsafe_allow_html=True)
                    with cs_c2:
                        st.markdown(
                            f'<div class="stat-card"><div class="stat-num">{result.get("overall_compliance_score",0):.0f}</div>'
                            f'<div class="stat-lbl">Compliance Score / 100</div></div>', unsafe_allow_html=True)
                    with cs_c3:
                        st.markdown(
                            f'<div class="stat-card"><div class="stat-num">{result.get("clause_coverage_percent",0)}%</div>'
                            f'<div class="stat-lbl">Clause Coverage</div></div>', unsafe_allow_html=True)
                    st.markdown("**Severity Breakdown**")
                    sev = result.get("severity_breakdown",{})
                    sc1,sc2,sc3,sc4 = st.columns(4)
                    sc1.metric("🔴 Critical", sev.get("Critical",0))
                    sc2.metric("🟠 High",     sev.get("High",0))
                    sc3.metric("🟡 Medium",   sev.get("Medium",0))
                    sc4.metric("🟢 Low",      sev.get("Low",0))
                    st.markdown(f"**Clauses Found:** {result.get('clauses_found',0)} / {result.get('clauses_total',5)}")
                    st.progress(result.get("clause_coverage_percent",0) / 100)

    # ── FEATURE 8: Document Version History ───────────────────────────────────
    with st.container(border=True):
        st.markdown('<div class="bonus-title">📋 Feature 8 — Document Version History</div>', unsafe_allow_html=True)
        st.markdown('<div class="bonus-desc">Complete history of every upload and analysis with timestamps, file types, language detected, and processing status.</div>', unsafe_allow_html=True)
        if all_docs:
            import pandas as pd
            st.dataframe(pd.DataFrame([{
                "ID":d["id"],"Filename":d["filename"],"Type":d["file_type"],
                "Language":d["language"],"Status":d["status"],"Upload Date":d["upload_date"][:19],
            } for d in all_docs]), use_container_width=True)
        else:
            st.info("No documents uploaded yet.")

    # ── FEATURE 9: Docker Deployment ──────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<div class="bonus-title">🐳 Feature 9 — Docker Deployment</div>', unsafe_allow_html=True)
        st.markdown('<div class="bonus-desc">The entire stack ships as a single Docker Compose file. One command starts Ollama + FastAPI + Streamlit.</div>', unsafe_allow_html=True)
        st.code(
            "docker compose up --build\n"
            "docker exec -it contract_ollama ollama pull llama3.1:8b\n\n"
            "# Frontend → http://localhost:8501\n"
            "# API Docs → http://localhost:8000/api/docs",
            language="bash",
        )
        col_a, col_b, col_c = st.columns(3)
        col_a.info("🦙 **contract_ollama**\nLocal LLM\nPort 11434")
        col_b.info("⚙️ **contract_backend**\nFastAPI + AI\nPort 8000")
        col_c.info("🖥️ **contract_frontend**\nStreamlit UI\nPort 8501")


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: PROFILE
# ═══════════════════════════════════════════════════════════════════════════════
def page_profile():
    st.title("👤 My Profile")
    user = st.session_state.get("user", {})
    with st.form("profile_form"):
        full_name = st.text_input("Full Name", value=user.get("full_name",""))
        st.text_input("Email", value=user.get("email",""), disabled=True)
        st.text_input("Role",  value=user.get("role","user"), disabled=True)
        new_pw  = st.text_input("New Password (blank = keep current)", type="password")
        new_pw2 = st.text_input("Confirm New Password", type="password")
        if st.form_submit_button("💾 Save Changes", type="primary"):
            if new_pw and new_pw != new_pw2:
                st.error("Passwords do not match.")
            else:
                payload = {"full_name": full_name}
                if new_pw:
                    payload["password"] = new_pw
                data, err = api.update_profile(payload)
                if err:
                    st.error(f"Update failed: {err}")
                else:
                    st.session_state["user"] = data
                    st.success("Profile updated successfully!")


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: ADMIN PANEL
# ═══════════════════════════════════════════════════════════════════════════════
def page_admin():
    st.title("🛡️ Admin Panel")
    if st.session_state.get("user",{}).get("role") != "admin":
        st.error("❌ Admin privileges required.")
        return

    t1, t2, t3 = st.tabs(["👥 Users", "📊 System Stats", "📋 Audit Logs"])
    with t1:
        users, err = api.admin_list_users()
        if err:
            st.error(err)
        else:
            for u in users:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3,2,2,2])
                    c1.markdown(f"**{u['full_name']}**  \n{u['email']}")
                    c2.markdown(f"Role: `{u['role']}`")
                    c3.markdown(f"Active: {'✅' if u['is_active'] else '❌'}")
                    with c4:
                        if st.button("Toggle Active", key=f"tog_{u['id']}"):
                            api.admin_toggle_active(u["id"]); st.rerun()
                        nr = "admin" if u["role"] == "user" else "user"
                        if st.button(f"→ Make {nr}", key=f"role_{u['id']}"):
                            api.admin_change_role(u["id"], nr); st.rerun()
    with t2:
        stats, err = api.admin_system_stats()
        if err:
            st.error(err)
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Users",    stats.get("total_users",0))
            c2.metric("Documents",      stats.get("total_documents",0))
            c3.metric("Analyses",       stats.get("total_analyses",0))
            c4.metric("High-Risk Docs", stats.get("high_risk_documents",0))
    with t3:
        logs, err = api.admin_system_logs()
        if err:
            st.error(err)
        else:
            import pandas as pd
            if logs:
                st.dataframe(pd.DataFrame([{
                    "Time":l["timestamp"][:19],"User":l["user_id"],
                    "Action":l["action"],"Details":l.get("details",""),
                } for l in logs]), use_container_width=True)
            else:
                st.info("No audit logs yet.")


# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════════
def sidebar():
    with st.sidebar:
        st.markdown('<div class="brand-title">⚖️ Contract AI</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-sub">Legal Document Risk Analyzer</div>', unsafe_allow_html=True)
        st.markdown("---")
        user = st.session_state.get("user", {})
        st.markdown(f"👤 **{user.get('full_name','User')}**")
        st.markdown(f"<small>🏷️ {user.get('role','user').title()}</small>", unsafe_allow_html=True)
        st.markdown("---")
        pages = [
            "🏠 Dashboard", "📄 My Documents", "🔍 Search & Q&A",
            "🔀 Compare Contracts", "✨ Bonus Features", "👤 Profile",
        ]
        if user.get("role") == "admin":
            pages.append("🛡️ Admin Panel")
        for p in pages:
            active = st.session_state["page"] == p
            if st.button(p, use_container_width=True, type="primary" if active else "secondary"):
                st.session_state["page"] = p
                st.rerun()
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN ROUTER
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    if not st.session_state.get("token"):
        page_login()
        return
    sidebar()
    page = st.session_state.get("page", "🏠 Dashboard")
    if   page == "🏠 Dashboard":        page_dashboard()
    elif page == "📄 My Documents":      page_documents()
    elif page == "🔍 Search & Q&A":      page_search()
    elif page == "🔀 Compare Contracts": page_compare()
    elif page == "✨ Bonus Features":    page_bonus()
    elif page == "👤 Profile":           page_profile()
    elif page == "🛡️ Admin Panel":       page_admin()


if __name__ == "__main__":
    main()