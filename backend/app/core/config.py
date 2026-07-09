"""
Central configuration for the Contract & Legal Document Risk Analyzer.
All values can be overridden via environment variables / .env file.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "AI Contract & Legal Document Risk Analyzer"

    SECRET_KEY: str = "CHANGE_THIS_SECRET_IN_PRODUCTION_xK9mP2vL"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/app.db"

    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    REPORT_DIR: Path = BASE_DIR / "reports"
    CHROMA_DIR: Path = BASE_DIR / "chroma_store"

    MAX_FILE_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: tuple = (".pdf", ".docx", ".txt")

    # Gemini Configuration
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Embedding Model (for ChromaDB / RAG)
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Debug (temporary)
print(
    "Gemini Key Loaded:",
    settings.GEMINI_API_KEY[:10] + "..."
    if settings.GEMINI_API_KEY
    else "EMPTY"
)

# Create required directories automatically
for d in (
    settings.UPLOAD_DIR,
    settings.REPORT_DIR,
    settings.CHROMA_DIR,
):
    d.mkdir(parents=True, exist_ok=True)