"""User progress tools."""

from typing import Any

from chiron.models import AssessmentResponse
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore


def get_user_progress(
    db: Database,
    vector_store: VectorStore,
    *,
    node_id: int,
) -> dict[str, Any] | None:
    """Get the user's progress on a specific knowledge node.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        node_id: The ID of the knowledge node.

    Returns:
        The user's progress, or None if not recorded.
    """
    # TODO: Implement when Database.get_user_progress exists
    return None


def record_assessment(
    db: Database,
    vector_store: VectorStore,
    *,
    node_id: int,
    question_hash: str,
    response: str,
    correct: bool,
    lesson_id: int | None = None,
) -> dict[str, Any]:
    """Record a user's response to an assessment question.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        node_id: The ID of the knowledge node being assessed.
        question_hash: A hash identifying the specific question.
        response: The user's response text.
        correct: Whether the response was correct.
        lesson_id: Optional ID of the lesson.

    Returns:
        The recorded assessment as a dict.
    """
    assessment = AssessmentResponse(
        node_id=node_id,
        question_hash=question_hash,
        response=response,
        correct=correct,
        lesson_id=lesson_id,
    )
    # TODO: Save to database when method is implemented
    return assessment.model_dump()
