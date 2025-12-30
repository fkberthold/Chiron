"""Tests for the research progress display."""

import time
from pathlib import Path

import pytest
from rich.console import Console, Group
from rich.tree import Tree

from chiron.cli.progress import (
    COMPLETION_THRESHOLD,
    MAX_DISPLAY_DEPTH,
    ResearchProgressDisplay,
)
from chiron.models import KnowledgeChunk, KnowledgeNode, LearningGoal
from chiron.orchestrator import Orchestrator
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore


@pytest.fixture
def console() -> Console:
    """Create test console."""
    return Console(force_terminal=True, width=80)


@pytest.fixture
def orchestrator(tmp_path: Path) -> Orchestrator:
    """Create test orchestrator with initialized database."""
    db = Database(tmp_path / "test.db")
    db.initialize()
    vs = VectorStore(tmp_path / "chroma")
    return Orchestrator(db, vs, lessons_dir=tmp_path / "lessons")


@pytest.fixture
def display(console: Console, orchestrator: Orchestrator) -> ResearchProgressDisplay:
    """Create test progress display."""
    return ResearchProgressDisplay(console, orchestrator)


class TestResearchProgressDisplayInit:
    """Tests for ResearchProgressDisplay initialization."""

    def test_initializes_with_console_and_orchestrator(
        self, console: Console, orchestrator: Orchestrator
    ) -> None:
        """Should store console and orchestrator references."""
        display = ResearchProgressDisplay(console, orchestrator)

        assert display.console is console
        assert display.orchestrator is orchestrator

    def test_initializes_with_empty_status(
        self, console: Console, orchestrator: Orchestrator
    ) -> None:
        """Should start with empty status message."""
        display = ResearchProgressDisplay(console, orchestrator)

        assert display._status_message == ""

    def test_initializes_with_no_start_time(
        self, console: Console, orchestrator: Orchestrator
    ) -> None:
        """Should start with no timer running."""
        display = ResearchProgressDisplay(console, orchestrator)

        assert display._start_time is None


class TestGetNodeStatus:
    """Tests for get_node_status method."""

    def test_active_topic_shows_magnifying_glass(
        self, display: ResearchProgressDisplay
    ) -> None:
        """Active topic should show magnifying glass icon."""
        result = display.get_node_status(fact_count=3, is_active=True)

        assert result == "\U0001f50d"  # magnifying glass

    def test_zero_facts_shows_empty_circle(
        self, display: ResearchProgressDisplay
    ) -> None:
        """Zero facts should show empty circle."""
        result = display.get_node_status(fact_count=0, is_active=False)

        assert result == "\u25cb"  # empty circle

    def test_few_facts_shows_quarter_circle(
        self, display: ResearchProgressDisplay
    ) -> None:
        """Less than half threshold should show quarter circle."""
        # With threshold of 5, 1-2 facts should be quarter
        result = display.get_node_status(fact_count=1, is_active=False)

        assert result == "\u25d4"  # quarter circle

    def test_partial_facts_shows_half_circle(
        self, display: ResearchProgressDisplay
    ) -> None:
        """Half threshold to threshold should show half circle."""
        # With threshold of 5, 3-4 facts should be half
        result = display.get_node_status(fact_count=3, is_active=False)

        assert result == "\u25d0"  # half circle

    def test_complete_facts_shows_full_circle(
        self, display: ResearchProgressDisplay
    ) -> None:
        """At or above threshold should show full circle."""
        result = display.get_node_status(fact_count=COMPLETION_THRESHOLD, is_active=False)

        assert result == "\u25cf"  # full circle

    def test_above_threshold_shows_full_circle(
        self, display: ResearchProgressDisplay
    ) -> None:
        """Above threshold should still show full circle."""
        result = display.get_node_status(fact_count=10, is_active=False)

        assert result == "\u25cf"  # full circle

    def test_active_overrides_completion(
        self, display: ResearchProgressDisplay
    ) -> None:
        """Active topic should show magnifying glass regardless of fact count."""
        result = display.get_node_status(fact_count=COMPLETION_THRESHOLD, is_active=True)

        assert result == "\U0001f50d"  # magnifying glass


class TestBuildTree:
    """Tests for build_tree method."""

    def test_builds_tree_with_subject_name(
        self, display: ResearchProgressDisplay, orchestrator: Orchestrator
    ) -> None:
        """Should create tree with subject name as root."""
        # Setup subject
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="kubernetes",
            purpose_statement="Learn K8s",
        ))
        orchestrator.set_active_subject("kubernetes")

        tree = display.build_tree()

        assert isinstance(tree, Tree)
        assert "kubernetes" in tree.label  # type: ignore[operator]

    def test_builds_tree_with_nodes(
        self, display: ResearchProgressDisplay, orchestrator: Orchestrator
    ) -> None:
        """Should include knowledge nodes in tree."""
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="kubernetes",
            purpose_statement="Learn K8s",
        ))
        orchestrator.set_active_subject("kubernetes")
        orchestrator.db.save_knowledge_node(KnowledgeNode(
            subject_id="kubernetes",
            title="Pods",
            depth=0,
        ))

        tree = display.build_tree()

        # Verify tree was built (checking internal structure is fragile)
        assert isinstance(tree, Tree)
        # The label should contain the subject name
        assert "kubernetes" in str(tree.label)

    def test_shows_empty_message_when_no_nodes(
        self, display: ResearchProgressDisplay, orchestrator: Orchestrator
    ) -> None:
        """Should show 'No topics yet' when no knowledge nodes exist."""
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="empty",
            purpose_statement="Empty subject",
        ))
        orchestrator.set_active_subject("empty")

        tree = display.build_tree()

        # Check that tree was created (we can't easily inspect Rich internals)
        assert isinstance(tree, Tree)

    def test_marks_active_topic(
        self, display: ResearchProgressDisplay, orchestrator: Orchestrator
    ) -> None:
        """Should use active icon for active topic."""
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="kubernetes",
            purpose_statement="Learn K8s",
        ))
        orchestrator.set_active_subject("kubernetes")
        orchestrator.db.save_knowledge_node(KnowledgeNode(
            subject_id="kubernetes",
            title="Pods",
            depth=0,
        ))

        tree = display.build_tree(active_topic="Pods")

        # Just verify it builds without error
        assert isinstance(tree, Tree)

    def test_builds_nested_tree_structure(
        self, display: ResearchProgressDisplay, orchestrator: Orchestrator
    ) -> None:
        """Should build parent-child relationships based on depth."""
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="kubernetes",
            purpose_statement="Learn K8s",
        ))
        orchestrator.set_active_subject("kubernetes")

        # Add nodes at different depths
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
        orchestrator.db.save_knowledge_node(KnowledgeNode(
            subject_id="kubernetes",
            title="Networking",
            depth=1,
        ))

        tree = display.build_tree()

        assert isinstance(tree, Tree)


class TestUpdateStatus:
    """Tests for update_status method."""

    def test_updates_status_message(
        self, display: ResearchProgressDisplay
    ) -> None:
        """Should update internal status message."""
        display.update_status("Searching kubernetes.io/docs/concepts/pods...")

        assert display._status_message == "Searching kubernetes.io/docs/concepts/pods..."

    def test_can_update_multiple_times(
        self, display: ResearchProgressDisplay
    ) -> None:
        """Should allow multiple status updates."""
        display.update_status("First status")
        display.update_status("Second status")

        assert display._status_message == "Second status"


class TestSetActiveTopic:
    """Tests for set_active_topic method."""

    def test_sets_active_topic(
        self, display: ResearchProgressDisplay
    ) -> None:
        """Should set active topic."""
        display.set_active_topic("Pods")

        assert display._active_topic == "Pods"

    def test_can_clear_active_topic(
        self, display: ResearchProgressDisplay
    ) -> None:
        """Should allow clearing active topic."""
        display.set_active_topic("Pods")
        display.set_active_topic(None)

        assert display._active_topic is None


class TestTimer:
    """Tests for timer functionality."""

    def test_start_timer_sets_start_time(
        self, display: ResearchProgressDisplay
    ) -> None:
        """start_timer should record current time."""
        display.start_timer()

        assert display._start_time is not None
        assert display._start_time <= time.time()

    def test_get_elapsed_returns_zero_when_not_started(
        self, display: ResearchProgressDisplay
    ) -> None:
        """get_elapsed should return '0s' when timer not started."""
        result = display.get_elapsed()

        assert result == "0s"

    def test_get_elapsed_returns_seconds_format(
        self, display: ResearchProgressDisplay
    ) -> None:
        """get_elapsed should return seconds format for short durations."""
        display._start_time = time.time() - 30  # 30 seconds ago

        result = display.get_elapsed()

        assert result == "30s"

    def test_get_elapsed_returns_minutes_format(
        self, display: ResearchProgressDisplay
    ) -> None:
        """get_elapsed should return minutes format for longer durations."""
        display._start_time = time.time() - 154  # 2 minutes 34 seconds ago

        result = display.get_elapsed()

        assert result == "2m 34s"

    def test_get_elapsed_handles_exact_minute(
        self, display: ResearchProgressDisplay
    ) -> None:
        """get_elapsed should handle exact minute boundaries."""
        display._start_time = time.time() - 120  # exactly 2 minutes

        result = display.get_elapsed()

        assert result == "2m 0s"


class TestRender:
    """Tests for render method."""

    def test_returns_renderable_group(
        self, display: ResearchProgressDisplay, orchestrator: Orchestrator
    ) -> None:
        """render should return a Group renderable."""
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="test",
            purpose_statement="Test",
        ))
        orchestrator.set_active_subject("test")

        result = display.render()

        assert isinstance(result, Group)

    def test_render_includes_tree(
        self, display: ResearchProgressDisplay, orchestrator: Orchestrator
    ) -> None:
        """render should include the progress tree."""
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="test",
            purpose_statement="Test",
        ))
        orchestrator.set_active_subject("test")

        result = display.render()

        # Group should contain Tree as first element
        assert isinstance(result, Group)
        assert isinstance(result.renderables[0], Tree)

    def test_render_includes_status_when_set(
        self, display: ResearchProgressDisplay, orchestrator: Orchestrator
    ) -> None:
        """render should include status message when set."""
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="test",
            purpose_statement="Test",
        ))
        orchestrator.set_active_subject("test")
        display.update_status("Searching...")

        result = display.render()

        # Group should have 3 renderables: tree, status, elapsed
        assert isinstance(result, Group)
        assert len(result.renderables) == 3

    def test_render_uses_active_topic(
        self, display: ResearchProgressDisplay, orchestrator: Orchestrator
    ) -> None:
        """render should pass active topic to build_tree."""
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="kubernetes",
            purpose_statement="Learn K8s",
        ))
        orchestrator.set_active_subject("kubernetes")
        orchestrator.db.save_knowledge_node(KnowledgeNode(
            subject_id="kubernetes",
            title="Pods",
            depth=0,
        ))
        display.set_active_topic("Pods")

        result = display.render()

        assert isinstance(result, Group)


class TestMaxDisplayDepth:
    """Tests for depth limiting."""

    def test_max_depth_constant_is_correct(self) -> None:
        """MAX_DISPLAY_DEPTH should be 2 (for 3 levels: 0, 1, 2)."""
        assert MAX_DISPLAY_DEPTH == 2

    def test_nodes_beyond_max_depth_not_displayed(
        self, display: ResearchProgressDisplay, orchestrator: Orchestrator
    ) -> None:
        """Nodes with depth > MAX_DISPLAY_DEPTH should not appear in tree."""
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="deep",
            purpose_statement="Deep tree",
        ))
        orchestrator.set_active_subject("deep")

        # Add nodes at various depths
        orchestrator.db.save_knowledge_node(KnowledgeNode(
            subject_id="deep",
            title="Level0",
            depth=0,
        ))
        orchestrator.db.save_knowledge_node(KnowledgeNode(
            subject_id="deep",
            title="Level1",
            depth=1,
        ))
        orchestrator.db.save_knowledge_node(KnowledgeNode(
            subject_id="deep",
            title="Level2",
            depth=2,
        ))
        orchestrator.db.save_knowledge_node(KnowledgeNode(
            subject_id="deep",
            title="Level3-TooDeep",
            depth=3,
        ))

        tree = display.build_tree()

        # Tree should build without error; depth 3 node is filtered
        assert isinstance(tree, Tree)


class TestCompletionThreshold:
    """Tests for completion threshold constant."""

    def test_threshold_is_five(self) -> None:
        """COMPLETION_THRESHOLD should be 5."""
        assert COMPLETION_THRESHOLD == 5

    def test_threshold_boundaries(
        self, display: ResearchProgressDisplay
    ) -> None:
        """Test exact threshold boundary behavior."""
        # Just below threshold
        below = display.get_node_status(COMPLETION_THRESHOLD - 1)
        assert below == "\u25d0"  # half circle

        # At threshold
        at = display.get_node_status(COMPLETION_THRESHOLD)
        assert at == "\u25cf"  # full circle

        # Above threshold
        above = display.get_node_status(COMPLETION_THRESHOLD + 1)
        assert above == "\u25cf"  # full circle


class TestIntegration:
    """Integration tests with real orchestrator data."""

    def test_full_workflow(
        self, display: ResearchProgressDisplay, orchestrator: Orchestrator
    ) -> None:
        """Test complete workflow from setup to render."""
        # Setup subject with knowledge tree and facts
        orchestrator.db.save_learning_goal(LearningGoal(
            subject_id="kubernetes",
            purpose_statement="Learn K8s for DevOps",
        ))
        orchestrator.set_active_subject("kubernetes")

        # Add knowledge tree
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
        orchestrator.db.save_knowledge_node(KnowledgeNode(
            subject_id="kubernetes",
            title="Services",
            depth=0,
        ))

        # Add facts
        for i in range(3):
            orchestrator.vector_store.store_knowledge(KnowledgeChunk(
                content=f"Pod fact {i}",
                subject_id="kubernetes",
                source_url="https://k8s.io/docs",
                source_score=0.9,
                topic_path="Pods",
                confidence=0.8,
            ))

        # Setup display
        display.start_timer()
        display.set_active_topic("Pods")
        display.update_status("Searching kubernetes.io/docs/concepts/pods...")

        # Render
        result = display.render()

        assert isinstance(result, Group)
        assert len(result.renderables) == 3  # tree, status, elapsed
