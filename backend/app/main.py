from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.models import models  # noqa: F401
from app.routers import auth, documents, search, dashboard, reports, compare, admin, bonus

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered contract analysis platform — fully open-source.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(compare.router)
app.include_router(admin.router)
app.include_router(bonus.router)

@app.get("/api/health", tags=["Health"])
def health():
    from app.services.llm_service import is_llm_available
    return {"status": "ok", "llm_online": is_llm_available(), "app": settings.APP_NAME}