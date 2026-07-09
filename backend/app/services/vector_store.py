"""
Semantic search & RAG layer using ChromaDB (open-source, embedded vector DB)
with sentence-transformers embeddings (open-source, runs locally — no API key).
"""
import re
import chromadb
from chromadb.utils import embedding_functions
from app.core.config import settings

_client = chromadb.PersistentClient(path=str(settings.CHROMA_DIR))
_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=settings.EMBEDDING_MODEL
)
_collection = _client.get_or_create_collection(
    name="contract_chunks", embedding_function=_embedding_fn
)


def chunk_text(text: str, chunk_size: int = 350, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def index_document(document_id: int, filename: str, owner_id: int, text: str):
    # remove any pre-existing chunks for this doc (e.g. re-upload/reanalyze)
    delete_document(document_id)

    chunks = chunk_text(text)
    if not chunks:
        return
    ids = [f"doc{document_id}_chunk{i}" for i in range(len(chunks))]
    metadatas = [
        {"document_id": document_id, "filename": filename, "owner_id": owner_id, "chunk_index": i}
        for i in range(len(chunks))
    ]
    _collection.add(documents=chunks, ids=ids, metadatas=metadatas)


def delete_document(document_id: int):
    try:
        _collection.delete(where={"document_id": document_id})
    except Exception:
        pass


def semantic_search(query: str, owner_id: int, document_id: int | None = None, top_k: int = 5) -> list[dict]:
    where = {"owner_id": owner_id}
    if document_id:
        where = {"$and": [{"owner_id": owner_id}, {"document_id": document_id}]}

    results = _collection.query(query_texts=[query], n_results=top_k, where=where)
    output = []
    if not results.get("ids") or not results["ids"][0]:
        return output

    for doc_text, meta, dist in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        output.append({
            "document_id": meta["document_id"],
            "filename": meta["filename"],
            "chunk_text": doc_text,
            "score": round(1 - dist, 4),  # convert distance -> similarity-like score
        })
    return output
