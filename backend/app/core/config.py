"""
Central configuration for the Contract & Legal Document Risk Analyzer.
All values can be overridden via environment variables / .env file.
"""
from pydantic_settings import BaseSettings
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "AI Contract & Legal Document Risk Analyzer"
    SECRET_KEY: str = "CHANGE_THIS_SECRET_IN_PRODUCTION_xK9mP2vL"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/app.db"

    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    REPORT_DIR: Path = BASE_DIR / "reports"
    CHROMA_DIR: Path = BASE_DIR / "chroma_store"

    MAX_FILE_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: tuple = (".pdf", ".docx", ".txt")

    # Local, open-source LLM served by Ollama (https://ollama.com)
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "phi3:mini"  # any open-source model pulled into Ollama
     
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # open-source sentence-transformers model

    class Config:
        env_file = ".env"


settings = Settings()

for d in (settings.UPLOAD_DIR, settings.REPORT_DIR, settings.CHROMA_DIR):
    d.mkdir(parents=True, exist_ok=True)
