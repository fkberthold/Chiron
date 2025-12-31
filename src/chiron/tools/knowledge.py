"""Knowledge storage and search tools."""

from datetime import datetime
from typing import Any

from chiron.models import KnowledgeChunk
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore


def store_knowledge(
    db: Database,
    vector_store: VectorStore,
    *,
    content: str,
    subject_id: str,
    source_url: str,
    source_score: float,
    topic_path: str,
    confidence: float,
    contradictions: list[str] | None = None,
) -> dict[str, str]:
    """Store a knowledge chunk in the vector store.

    Args:
        db: Database instance (unused but kept for consistent signature).
        vector_store: VectorStore instance for semantic search.
        content: The text content of the knowledge chunk.
        subject_id: The subject this knowledge belongs to.
        source_url: URL of the source where this knowledge came from.
        source_score: Dependability score of the source (0.0 to 1.0).
        topic_path: Hierarchical path of the topic.
        confidence: Confidence level in this knowledge (0.0 to 1.0).
        contradictions: List of any known contradicting information.

    Returns:
        A confirmation dict with status, subject_id, and topic_path.
    """
    chunk = KnowledgeChunk(
        content=content,
        subject_id=subject_id,
        source_url=source_url,
        source_score=source_score,
        topic_path=topic_path,
        confidence=confidence,
        contradictions=contradictions or [],
        last_validated=datetime.now(),
    )
    vector_store.store_knowledge(chunk)
    return {"status": "stored", "subject_id": subject_id, "topic_path": topic_path}


def vector_search(
    db: Database,
    vector_store: VectorStore,
    *,
    query: str,
    subject_id: str,
    top_k: int = 5,
    min_confidence: float = 0.0,
) -> list[dict[str, Any]]:
    """Search for knowledge chunks by semantic similarity.

    Args:
        db: Database instance (unused but kept for consistent signature).
        vector_store: VectorStore instance for semantic search.
        query: The search query text.
        subject_id: Filter results to this subject only.
        top_k: Maximum number of results to return.
        min_confidence: Minimum confidence score for results.

    Returns:
        A list of matching knowledge chunks as dicts.
    """
    chunks = vector_store.search(
        query=query,
        subject_id=subject_id,
        top_k=top_k,
        min_confidence=min_confidence,
    )
    return [chunk.model_dump(mode='json') for chunk in chunks]
