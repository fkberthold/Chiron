"""Tests for the workflow orchestrator."""

from pathlib import Path

import pytest

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
    from chiron.models import LearningGoal
    orchestrator.db.save_learning_goal(LearningGoal(
        subject_id="test",
        purpose_statement="Test purpose",
    ))

    orchestrator.set_active_subject("test")
    assert orchestrator.get_active_subject() == "test"
