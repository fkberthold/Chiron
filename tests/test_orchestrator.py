"""Tests for the workflow orchestrator."""

from pathlib import Path

import pytest

from chiron.models import KnowledgeChunk, KnowledgeNode, LearningGoal
from chiron.orchestrator import Orchestrator, WorkflowState
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore


@pytest.fixture
def orchestrator(tmp_path: Path) -> Orchestrator:
    """Create test orchestrator."""
    db = Database(tmp_path / "test.db")
    db.initialize()
    vs = VectorStore(tmp_path / "chroma")
    return Orchestrator(db, vs, lessons_dir=tmp_path / "lessons")


def test_workflow_states_exist() -> None:
    """WorkflowState should have all required states."""
    assert WorkflowState.IDLE
    assert WorkflowState.INITIALIZING
    assert WorkflowState.RESEARCHING
    assert WorkflowState.ASSESSING
    assert WorkflowState.GENERATING_LESSON
    assert WorkflowState.DELIVERING_LESSON
    assert WorkflowState.EXERCISING


def test_orchestrator_starts_idle(orchestrator: Orchestrator) -> None:
    """Orchestrator should start in IDLE state."""
    assert orchestrator.state == WorkflowState.IDLE


def test_orchestrator_has_active_subject(orchestrator: Orchestrator) -> None:
    """Orchestrator should track active subject."""
    assert orchestrator.get_active_subject() is None


def test_orchestrator_can_set_active_subject(orchestrator: Orchestrator) -> None:
    """Orchestrator should allow setting active subject."""
    # First need to create a subject
    orchestrator.db.save_learning_goal(LearningGoal(
        subject_id="test",
        purpose_statement="Test purpose",
    ))

    orchestrator.set_active_subject("test")
    assert orchestrator.get_active_subject() == "test"


def test_orchestrator_creates_tool_executor(orchestrator: Orchestrator) -> None:
    """Orchestrator should create tool executor bound to db/vector_store."""
    executor = orchestrator._create_tool_executor()

    assert callable(executor)


def test_orchestrator_research_agent_has_tools(orchestrator: Orchestrator) -> None:
    """research_agent should have tools configured."""
    agent = orchestrator.research_agent

    assert agent.tools is not None
    assert len(agent.tools) > 0
    assert agent.tool_executor is not None


class TestGetResearchProgress:
    """Tests for get_research_progress method."""

    def test_returns_progress_for_active_subject(
        self, orchestrator: Orchestrator
    ) -> None:
        """Should return progress dict for active subject when no subject_id passed."""
        # Setup: create subject with knowledge nodes and facts
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="kubernetes",
            purpose_statement="Learn K8s",
        ))
        orchestrator.set_active_subject("kubernetes")

        # Add knowledge nodes
        orchestrator.db.save_knowledge_node(KnowledgeNode(
            subject_id="kubernetes",
            title="Pods",
            depth=0,
        ))
        orchestrator.db.save_knowledge_node(KnowledgeNode(
            subject_id="kubernetes",
            title="Containers",
            depth=1,
        ))

        # Add facts to vector store
        orchestrator.vector_store.store_knowledge(KnowledgeChunk(
            content="Pods are the smallest deployable units",
            subject_id="kubernetes",
            source_url="https://k8s.io/docs",
            source_score=0.9,
            topic_path="Pods",
            confidence=0.8,
        ))
        orchestrator.vector_store.store_knowledge(KnowledgeChunk(
            content="Containers run inside pods",
            subject_id="kubernetes",
            source_url="https://k8s.io/docs",
            source_score=0.9,
            topic_path="Containers",
            confidence=0.8,
        ))

        # Test
        result = orchestrator.get_research_progress()

        # Verify structure
        assert result["subject_id"] == "kubernetes"
        assert isinstance(result["nodes"], list)
        assert len(result["nodes"]) == 2
        assert result["total_facts"] == 2

        # Verify node structure
        pods_node = next(n for n in result["nodes"] if n["title"] == "Pods")
        assert pods_node["fact_count"] == 1
        assert pods_node["depth"] == 0
        assert "id" in pods_node

    def test_returns_progress_for_explicit_subject(
        self, orchestrator: Orchestrator
    ) -> None:
        """Should return progress for specified subject_id."""
        # Setup
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="python",
            purpose_statement="Learn Python",
        ))
        orchestrator.db.save_knowledge_node(KnowledgeNode(
            subject_id="python",
            title="Functions",
            depth=0,
        ))

        # Test with explicit subject_id
        result = orchestrator.get_research_progress("python")

        assert result["subject_id"] == "python"
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["title"] == "Functions"

    def test_raises_when_no_active_subject(self, orchestrator: Orchestrator) -> None:
        """Should raise ValueError when no subject_id provided and no active subject."""
        with pytest.raises(ValueError, match="No active subject"):
            orchestrator.get_research_progress()

    def test_nodes_without_facts_have_zero_count(
        self, orchestrator: Orchestrator
    ) -> None:
        """Nodes without matching facts should have fact_count of 0."""
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="rust",
            purpose_statement="Learn Rust",
        ))
        orchestrator.set_active_subject("rust")
        orchestrator.db.save_knowledge_node(KnowledgeNode(
            subject_id="rust",
            title="Ownership",
            depth=0,
        ))

        result = orchestrator.get_research_progress()

        assert result["nodes"][0]["fact_count"] == 0
        assert result["total_facts"] == 0

    def test_empty_knowledge_tree_returns_empty_nodes(
        self, orchestrator: Orchestrator
    ) -> None:
        """Should return empty nodes list when no knowledge nodes exist."""
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="empty",
            purpose_statement="Empty subject",
        ))
        orchestrator.set_active_subject("empty")

        result = orchestrator.get_research_progress()

        assert result["subject_id"] == "empty"
        assert result["nodes"] == []
        assert result["total_facts"] == 0
