"""Tests for SQLite database layer."""

import tempfile
from pathlib import Path

import pytest

from chiron.models import KnowledgeNode, LearningGoal, SubjectStatus
from chiron.storage import Database


@pytest.fixture
def db() -> Database:
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        database = Database(db_path)
        database.initialize()
        yield database


def test_database_creates_tables(db: Database) -> None:
    """Database should create all required tables on initialize."""
    tables = db.get_tables()
    expected_tables = [
        "learning_goals",
        "knowledge_nodes",
        "user_progress",
        "sources",
        "lessons",
        "responses",
        "settings",
    ]
    for table in expected_tables:
        assert table in tables, f"Missing table: {table}"


def test_save_and_get_learning_goal(db: Database) -> None:
    """Should save and retrieve learning goals."""
    goal = LearningGoal(
        subject_id="kubernetes",
        purpose_statement="Maintain K8S repos in my organization",
        target_depth="practical",
    )
    saved_id = db.save_learning_goal(goal)
    assert saved_id is not None

    retrieved = db.get_learning_goal("kubernetes")
    assert retrieved is not None
    assert retrieved.subject_id == "kubernetes"
    assert retrieved.purpose_statement == "Maintain K8S repos in my organization"
    assert retrieved.target_depth == "practical"
    assert retrieved.id == saved_id


def test_save_and_get_knowledge_node(db: Database) -> None:
    """Should save and retrieve knowledge nodes."""
    node = KnowledgeNode(
        subject_id="kubernetes",
        title="Pod Architecture",
        description="Understanding Kubernetes pods",
        depth=0,
        is_goal_critical=True,
    )
    saved_id = db.save_knowledge_node(node)
    assert saved_id is not None

    retrieved = db.get_knowledge_node(saved_id)
    assert retrieved is not None
    assert retrieved.subject_id == "kubernetes"
    assert retrieved.title == "Pod Architecture"
    assert retrieved.description == "Understanding Kubernetes pods"
    assert retrieved.is_goal_critical is True


def test_get_knowledge_tree(db: Database) -> None:
    """Should retrieve all nodes for a subject as a tree."""
    # Create parent node
    parent = KnowledgeNode(
        subject_id="kubernetes",
        title="Architecture",
        depth=0,
    )
    parent_id = db.save_knowledge_node(parent)

    # Create child nodes
    child1 = KnowledgeNode(
        subject_id="kubernetes",
        parent_id=parent_id,
        title="Pods",
        depth=1,
    )
    child2 = KnowledgeNode(
        subject_id="kubernetes",
        parent_id=parent_id,
        title="Services",
        depth=1,
    )
    db.save_knowledge_node(child1)
    db.save_knowledge_node(child2)

    # Also create a node for a different subject
    other = KnowledgeNode(
        subject_id="python",
        title="Basics",
        depth=0,
    )
    db.save_knowledge_node(other)

    # Get tree for kubernetes only
    tree = db.get_knowledge_tree("kubernetes")
    assert len(tree) == 3
    titles = [n.title for n in tree]
    assert "Architecture" in titles
    assert "Pods" in titles
    assert "Services" in titles
    assert "Basics" not in titles


def test_active_subject_setting(db: Database) -> None:
    """Should get and set the active subject."""
    # Initially no active subject
    active = db.get_setting("active_subject")
    assert active is None

    # Set active subject
    db.set_setting("active_subject", "kubernetes")
    active = db.get_setting("active_subject")
    assert active == "kubernetes"

    # Change active subject
    db.set_setting("active_subject", "python")
    active = db.get_setting("active_subject")
    assert active == "python"


def test_list_subjects(db: Database) -> None:
    """Should list all subjects with learning goals."""
    # Create multiple learning goals
    goal1 = LearningGoal(
        subject_id="kubernetes",
        purpose_statement="Learn K8S",
    )
    goal2 = LearningGoal(
        subject_id="python",
        purpose_statement="Learn Python",
        status=SubjectStatus.READY,
    )
    db.save_learning_goal(goal1)
    db.save_learning_goal(goal2)

    subjects = db.list_subjects()
    assert len(subjects) == 2
    subject_ids = [s.subject_id for s in subjects]
    assert "kubernetes" in subject_ids
    assert "python" in subject_ids
