"""Knowledge node tools."""

from typing import Any

from chiron.models import KnowledgeNode
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore


def get_knowledge_node(
    db: Database,
    vector_store: VectorStore,
    *,
    node_id: int,
) -> dict[str, Any] | None:
    """Get a specific knowledge node by its ID.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        node_id: The database ID of the knowledge node.

    Returns:
        The knowledge node as a dict, or None if not found.
    """
    node = db.get_knowledge_node(node_id)
    return node.model_dump(mode='json') if node else None


def get_knowledge_tree(
    db: Database,
    vector_store: VectorStore,
    *,
    subject_id: str,
) -> list[dict[str, Any]]:
    """Get all knowledge nodes for a subject as a tree structure.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        subject_id: The subject identifier.

    Returns:
        A list of all knowledge nodes for the subject.
    """
    nodes = db.get_knowledge_tree(subject_id)
    return [node.model_dump(mode='json') for node in nodes]


def save_knowledge_node(
    db: Database,
    vector_store: VectorStore,
    *,
    subject_id: str,
    title: str,
    description: str | None = None,
    parent_id: int | None = None,
    depth: int = 0,
    is_goal_critical: bool = False,
    prerequisites: list[int] | None = None,
    shared_with_subjects: list[str] | None = None,
) -> dict[str, Any]:
    """Save a new knowledge node or update an existing one.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        subject_id: The subject this node belongs to.
        title: The title/name of this knowledge node.
        description: Optional detailed description.
        parent_id: ID of the parent node (None for root nodes).
        depth: Depth in the tree (0 for root).
        is_goal_critical: Whether critical for the learning goal.
        prerequisites: List of node IDs that must be learned first.
        shared_with_subjects: List of other subjects sharing this node.

    Returns:
        The saved knowledge node as a dict with its ID.
    """
    node = KnowledgeNode(
        subject_id=subject_id,
        title=title,
        description=description,
        parent_id=parent_id,
        depth=depth,
        is_goal_critical=is_goal_critical,
        prerequisites=prerequisites or [],
        shared_with_subjects=shared_with_subjects or [],
    )
    saved_id = db.save_knowledge_node(node)
    node.id = saved_id
    return node.model_dump(mode='json')
