"""FastMCP server implementation for Chiron."""

from typing import Any

from fastmcp import FastMCP

from chiron.storage import Database, VectorStore


def create_mcp_server(db: Database, vector_store: VectorStore) -> FastMCP:
    """Create and configure a FastMCP server with Chiron tools.

    Args:
        db: The SQLite database instance for persistent storage.
        vector_store: The ChromaDB vector store for semantic search.

    Returns:
        A configured FastMCP server instance with all Chiron tools registered.
    """
    mcp = FastMCP("chiron")

    # Wrap each tool function with MCP decorator
    @mcp.tool
    def vector_search(
        query: str,
        subject_id: str,
        top_k: int = 5,
        min_confidence: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Search for knowledge chunks by semantic similarity."""
        from chiron.tools import vector_search as _vector_search
        return _vector_search(
            db, vector_store,
            query=query,
            subject_id=subject_id,
            top_k=top_k,
            min_confidence=min_confidence,
        )

    @mcp.tool
    def store_knowledge(
        content: str,
        subject_id: str,
        source_url: str,
        source_score: float,
        topic_path: str,
        confidence: float,
        contradictions: list[str] | None = None,
    ) -> dict[str, str]:
        """Store a knowledge chunk in the vector store."""
        from chiron.tools import store_knowledge as _store_knowledge
        return _store_knowledge(
            db, vector_store,
            content=content,
            subject_id=subject_id,
            source_url=source_url,
            source_score=source_score,
            topic_path=topic_path,
            confidence=confidence,
            contradictions=contradictions,
        )

    @mcp.tool
    def get_active_subject() -> str | None:
        """Get the currently active learning subject."""
        from chiron.tools import get_active_subject as _get_active_subject
        return _get_active_subject(db, vector_store)

    @mcp.tool
    def set_active_subject(subject_id: str) -> dict[str, str]:
        """Set the active learning subject."""
        from chiron.tools import set_active_subject as _set_active_subject
        return _set_active_subject(db, vector_store, subject_id=subject_id)

    @mcp.tool
    def list_subjects() -> list[dict[str, Any]]:
        """List all subjects with learning goals."""
        from chiron.tools import list_subjects as _list_subjects
        return _list_subjects(db, vector_store)

    @mcp.tool
    def get_learning_goal(subject_id: str) -> dict[str, Any] | None:
        """Get the learning goal for a specific subject."""
        from chiron.tools import get_learning_goal as _get_learning_goal
        return _get_learning_goal(db, vector_store, subject_id=subject_id)

    @mcp.tool
    def save_learning_goal(
        subject_id: str,
        purpose_statement: str,
        target_depth: str = "practical",
    ) -> dict[str, Any]:
        """Save or update a learning goal for a subject."""
        from chiron.tools import save_learning_goal as _save_learning_goal
        return _save_learning_goal(
            db, vector_store,
            subject_id=subject_id,
            purpose_statement=purpose_statement,
            target_depth=target_depth,
        )

    @mcp.tool
    def get_knowledge_node(node_id: int) -> dict[str, Any] | None:
        """Get a specific knowledge node by its ID."""
        from chiron.tools import get_knowledge_node as _get_knowledge_node
        return _get_knowledge_node(db, vector_store, node_id=node_id)

    @mcp.tool
    def get_knowledge_tree(subject_id: str) -> list[dict[str, Any]]:
        """Get all knowledge nodes for a subject as a tree structure."""
        from chiron.tools import get_knowledge_tree as _get_knowledge_tree
        return _get_knowledge_tree(db, vector_store, subject_id=subject_id)

    @mcp.tool
    def save_knowledge_node(
        subject_id: str,
        title: str,
        description: str | None = None,
        parent_id: int | None = None,
        depth: int = 0,
        is_goal_critical: bool = False,
        prerequisites: list[int] | None = None,
        shared_with_subjects: list[str] | None = None,
    ) -> dict[str, Any]:
        """Save a new knowledge node or update an existing one."""
        from chiron.tools import save_knowledge_node as _save_knowledge_node
        return _save_knowledge_node(
            db, vector_store,
            subject_id=subject_id,
            title=title,
            description=description,
            parent_id=parent_id,
            depth=depth,
            is_goal_critical=is_goal_critical,
            prerequisites=prerequisites,
            shared_with_subjects=shared_with_subjects,
        )

    @mcp.tool
    def get_user_progress(node_id: int) -> dict[str, Any] | None:
        """Get the user's progress on a specific knowledge node."""
        from chiron.tools import get_user_progress as _get_user_progress
        return _get_user_progress(db, vector_store, node_id=node_id)

    @mcp.tool
    def record_assessment(
        node_id: int,
        question_hash: str,
        response: str,
        correct: bool,
        lesson_id: int | None = None,
    ) -> dict[str, Any]:
        """Record a user's response to an assessment question."""
        from chiron.tools import record_assessment as _record_assessment
        return _record_assessment(
            db, vector_store,
            node_id=node_id,
            question_hash=question_hash,
            response=response,
            correct=correct,
            lesson_id=lesson_id,
        )

    return mcp
