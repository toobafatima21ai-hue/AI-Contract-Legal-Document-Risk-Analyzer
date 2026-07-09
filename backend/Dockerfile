FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_TIMEOUT=600 \
    PIP_RETRIES=10 \
    PIP_PREFER_BINARY=1

# System packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN pip install --upgrade pip

# ── Layer 1: Web framework (small, fast) ──────────────────────────────────
RUN pip install \
    fastapi==0.111.0 \
    "uvicorn[standard]==0.30.1" \
    python-multipart==0.0.9 \
    aiofiles==23.2.1

# ── Layer 2: Database + Auth (small, fast) ────────────────────────────────
RUN pip install \
    sqlalchemy==2.0.30 \
    "passlib[bcrypt]==1.7.4" \
    "python-jose[cryptography]==3.3.0" \
    pydantic==2.7.1 \
    pydantic-settings==2.2.1 \
    python-dotenv==1.0.1

# ── Layer 3: Document parsing (medium) ────────────────────────────────────
RUN pip install \
    pdfplumber==0.11.1 \
    python-docx==1.1.2 \
    reportlab==4.2.0

# ── Layer 4: CPU-only PyTorch — MUST come before sentence-transformers ─────
# Without this, pip pulls CUDA packages (nvidia_cusolver = 200MB+)
RUN pip install \
    torch==2.2.2 \
    --index-url https://download.pytorch.org/whl/cpu

# ── Layer 5: sentence-transformers (now binds to CPU torch above) ──────────
RUN pip install sentence-transformers==2.7.0

# ── Layer 6: spaCy ────────────────────────────────────────────────────────
RUN pip install spacy==3.7.4
RUN python -m spacy download en_core_web_sm

# ── Layer 7: Vector DB ────────────────────────────────────────────────────
RUN pip install chromadb==0.5.0

# ── Layer 8: Google Gemini API ────────────────────────────────────────────
RUN pip install google-generativeai==0.7.2

# ── Layer 9: Bonus features ───────────────────────────────────────────────
RUN pip install \
    gTTS==2.5.1 \
    langdetect==1.0.9 \
    deep-translator==1.11.4 \
    pytesseract==0.3.10 \
    pdf2image==1.17.0

# ── Layer 10: HTTP + NLP utils ────────────────────────────────────────────
RUN pip install \
    requests==2.32.3

# Copy application code last (so code changes don't invalidate pip layers)
COPY . .

# Create runtime directories
RUN mkdir -p /app/uploads /app/reports /app/chroma_store

EXPOSE 8000

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1"]