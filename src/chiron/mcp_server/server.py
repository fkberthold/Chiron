"""FastMCP server implementation for Chiron."""

from datetime import datetime
from typing import Any

from fastmcp import FastMCP

from chiron.models import (
    AssessmentResponse,
    KnowledgeChunk,
    KnowledgeNode,
    LearningGoal,
)
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

    # --- Vector Store Tools ---

    @mcp.tool
    def vector_search(
        query: str,
        subject_id: str,
        top_k: int = 5,
        min_confidence: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Search for knowledge chunks by semantic similarity.

        Args:
            query: The search query text to find relevant knowledge.
            subject_id: Filter results to this subject only.
            top_k: Maximum number of results to return (default: 5).
            min_confidence: Minimum confidence score for results (default: 0.0).

        Returns:
            A list of matching knowledge chunks with their content and metadata.
        """
        chunks = vector_store.search(
            query=query,
            subject_id=subject_id,
            top_k=top_k,
            min_confidence=min_confidence,
        )
        return [chunk.model_dump() for chunk in chunks]

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
        """Store a knowledge chunk in the vector store.

        Args:
            content: The text content of the knowledge chunk.
            subject_id: The subject this knowledge belongs to.
            source_url: URL of the source where this knowledge came from.
            source_score: Dependability score of the source (0.0 to 1.0).
            topic_path: Hierarchical path of the topic (e.g., "kubernetes/pods/lifecycle").
            confidence: Confidence level in this knowledge (0.0 to 1.0).
            contradictions: List of any known contradicting information.

        Returns:
            A confirmation message with the stored chunk details.
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

    # --- Subject Management Tools ---

    @mcp.tool
    def get_active_subject() -> str | None:
        """Get the currently active learning subject.

        Returns:
            The subject_id of the active subject, or None if no subject is active.
        """
        return db.get_setting("active_subject")

    @mcp.tool
    def set_active_subject(subject_id: str) -> dict[str, str]:
        """Set the active learning subject.

        Args:
            subject_id: The identifier of the subject to make active.

        Returns:
            A confirmation message with the new active subject.
        """
        db.set_setting("active_subject", subject_id)
        return {"status": "success", "active_subject": subject_id}

    @mcp.tool
    def list_subjects() -> list[dict[str, Any]]:
        """List all subjects with learning goals.

        Returns:
            A list of all learning goals with their details including
            subject_id, purpose_statement, status, and progress.
        """
        goals = db.list_subjects()
        return [goal.model_dump() for goal in goals]

    # --- Learning Goal Tools ---

    @mcp.tool
    def get_learning_goal(subject_id: str) -> dict[str, Any] | None:
        """Get the learning goal for a specific subject.

        Args:
            subject_id: The identifier of the subject to retrieve.

        Returns:
            The learning goal details, or None if the subject doesn't exist.
        """
        goal = db.get_learning_goal(subject_id)
        return goal.model_dump() if goal else None

    @mcp.tool
    def save_learning_goal(
        subject_id: str,
        purpose_statement: str,
        target_depth: str = "practical",
    ) -> dict[str, Any]:
        """Save or update a learning goal for a subject.

        Args:
            subject_id: The unique identifier for this subject.
            purpose_statement: Why the user wants to learn this subject.
            target_depth: Desired depth of learning (e.g., "practical", "deep", "expert").

        Returns:
            The saved learning goal with its assigned ID.
        """
        goal = LearningGoal(
            subject_id=subject_id,
            purpose_statement=purpose_statement,
            target_depth=target_depth,
        )
        saved_id = db.save_learning_goal(goal)
        goal.id = saved_id
        return goal.model_dump()

    # --- Knowledge Node Tools ---

    @mcp.tool
    def get_knowledge_node(node_id: int) -> dict[str, Any] | None:
        """Get a specific knowledge node by its ID.

        Args:
            node_id: The database ID of the knowledge node.

        Returns:
            The knowledge node details, or None if not found.
        """
        node = db.get_knowledge_node(node_id)
        return node.model_dump() if node else None

    @mcp.tool
    def get_knowledge_tree(subject_id: str) -> list[dict[str, Any]]:
        """Get all knowledge nodes for a subject as a tree structure.

        Args:
            subject_id: The subject identifier to get the tree for.

        Returns:
            A list of all knowledge nodes for the subject, ordered by depth.
        """
        nodes = db.get_knowledge_tree(subject_id)
        return [node.model_dump() for node in nodes]

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
        """Save a new knowledge node or update an existing one.

        Args:
            subject_id: The subject this node belongs to.
            title: The title/name of this knowledge node.
            description: Optional detailed description of the node.
            parent_id: ID of the parent node (None for root nodes).
            depth: Depth in the tree (0 for root, increases with depth).
            is_goal_critical: Whether this node is critical for the learning goal.
            prerequisites: List of node IDs that must be learned first.
            shared_with_subjects: List of other subjects that share this node.

        Returns:
            The saved knowledge node with its assigned ID.
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
        return node.model_dump()

    # --- User Progress Tools ---

    @mcp.tool
    def get_user_progress(node_id: int) -> dict[str, Any] | None:
        """Get the user's progress on a specific knowledge node.

        Args:
            node_id: The ID of the knowledge node to get progress for.

        Returns:
            The user's progress including mastery level, last assessment,
            and next review date. Returns None if no progress recorded.
        """
        # TODO: Implement when Database has get_user_progress method
        # For now, return None to indicate no progress recorded
        return None

    @mcp.tool
    def record_assessment(
        node_id: int,
        question_hash: str,
        response: str,
        correct: bool,
        lesson_id: int | None = None,
    ) -> dict[str, Any]:
        """Record a user's response to an assessment question.

        Args:
            node_id: The ID of the knowledge node being assessed.
            question_hash: A hash identifying the specific question.
            response: The user's response text.
            correct: Whether the response was correct.
            lesson_id: Optional ID of the lesson this assessment is part of.

        Returns:
            The recorded assessment response with calculated next review date.
        """
        assessment = AssessmentResponse(
            node_id=node_id,
            question_hash=question_hash,
            response=response,
            correct=correct,
            lesson_id=lesson_id,
        )
        # TODO: Save to database when method is implemented
        # For now, return the assessment data
        return assessment.model_dump()

    return mcp
