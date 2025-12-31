"""Subject management tools."""

from typing import Any

from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore


def get_active_subject(
    db: Database,
    vector_store: VectorStore,
) -> str | None:
    """Get the currently active learning subject.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).

    Returns:
        The subject_id of the active subject, or None if not set.
    """
    return db.get_setting("active_subject")


def set_active_subject(
    db: Database,
    vector_store: VectorStore,
    *,
    subject_id: str,
) -> dict[str, str]:
    """Set the active learning subject.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        subject_id: The identifier of the subject to make active.

    Returns:
        A confirmation dict.
    """
    db.set_setting("active_subject", subject_id)
    return {"status": "success", "active_subject": subject_id}


def list_subjects(
    db: Database,
    vector_store: VectorStore,
) -> list[dict[str, Any]]:
    """List all subjects with learning goals.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).

    Returns:
        A list of all learning goals as dicts.
    """
    goals = db.list_subjects()
    return [goal.model_dump(mode='json') for goal in goals]
