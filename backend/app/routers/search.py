from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User
from app.models.schemas import (
    SemanticSearchQuery,
    SemanticSearchResult,
    QAQuery,
    QAResponse,
)
from app.services import vector_store, llm_service

router = APIRouter(prefix="/api/search", tags=["Semantic Search & RAG"])


@router.post("/semantic", response_model=list[SemanticSearchResult])
def semantic_search(
    payload: SemanticSearchQuery,
    current_user: User = Depends(get_current_user),
):
    results = vector_store.semantic_search(
        query=payload.query,
        owner_id=current_user.id,
        document_id=payload.document_id,
        top_k=payload.top_k,
    )
    return results


@router.post("/ask", response_model=QAResponse)
def ask_question(
    payload: QAQuery,
    current_user: User = Depends(get_current_user),
):
    """RAG-based Question Answering over the user's document(s)."""

    chunks = vector_store.semantic_search(
        query=payload.question,
        owner_id=current_user.id,
        document_id=payload.document_id,
        top_k=6,
    )

    if not chunks:
        return QAResponse(
            answer="No relevant content found. Make sure the document has been analyzed first.",
            sources=[],
        )

    try:
        if llm_service.is_llm_available():
            answer = llm_service.answer_question_with_context(
                payload.question,
                [c["chunk_text"] for c in chunks],
            )
        else:
            answer = (
                "LLM service is offline. Showing the most relevant document excerpt:\n\n"
                + chunks[0]["chunk_text"][:500]
            )

    except Exception as e:
        print("RAG Error:", str(e))

        answer = (
            f"LLM error: {str(e)}\n\n"
            "Showing the most relevant document excerpt instead:\n\n"
            + chunks[0]["chunk_text"][:500]
        )

    return QAResponse(
        answer=answer,
        sources=chunks,
    )