"""Learning goal tools."""

from typing import Any

from chiron.models import LearningGoal
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore


def get_learning_goal(
    db: Database,
    vector_store: VectorStore,
    *,
    subject_id: str,
) -> dict[str, Any] | None:
    """Get the learning goal for a specific subject.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        subject_id: The identifier of the subject to retrieve.

    Returns:
        The learning goal as a dict, or None if not found.
    """
    goal = db.get_learning_goal(subject_id)
    return goal.model_dump(mode='json') if goal else None


def save_learning_goal(
    db: Database,
    vector_store: VectorStore,
    *,
    subject_id: str,
    purpose_statement: str,
    target_depth: str = "practical",
) -> dict[str, Any]:
    """Save or update a learning goal for a subject.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        subject_id: The unique identifier for this subject.
        purpose_statement: Why the user wants to learn this subject.
        target_depth: Desired depth of learning.

    Returns:
        The saved learning goal as a dict with its ID.
    """
    goal = LearningGoal(
        subject_id=subject_id,
        purpose_statement=purpose_statement,
        target_depth=target_depth,
    )
    saved_id = db.save_learning_goal(goal)
    goal.id = saved_id
    return goal.model_dump(mode='json')
