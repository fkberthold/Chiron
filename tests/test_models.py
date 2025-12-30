"""Tests for data models."""

from datetime import datetime

from chiron.models import (
    AssessmentResponse,
    KnowledgeNode,
    LearningGoal,
    Lesson,
    Source,
    SubjectStatus,
    UserProgress,
)


def test_learning_goal_creation() -> None:
    """LearningGoal should store subject and purpose."""
    goal = LearningGoal(
        subject_id="kubernetes",
        purpose_statement="Maintain K8S repos in my organization",
        target_depth="practical",
    )
    assert goal.subject_id == "kubernetes"
    assert goal.purpose_statement == "Maintain K8S repos in my organization"
    assert goal.research_complete is False


def test_knowledge_node_hierarchy() -> None:
    """KnowledgeNode should support parent-child relationships."""
    parent = KnowledgeNode(
        id=1,
        subject_id="kubernetes",
        title="Architecture",
        depth=0,
    )
    child = KnowledgeNode(
        id=2,
        subject_id="kubernetes",
        parent_id=1,
        title="Pods",
        depth=1,
    )
    assert child.parent_id == parent.id
    assert child.depth == parent.depth + 1


def test_knowledge_node_prerequisites() -> None:
    """KnowledgeNode should track prerequisites."""
    node = KnowledgeNode(
        id=1,
        subject_id="kubernetes",
        title="Deployments",
        depth=1,
        prerequisites=[2, 3],
    )
    assert 2 in node.prerequisites
    assert 3 in node.prerequisites


def test_user_progress_mastery_bounds() -> None:
    """Mastery level should be between 0 and 1."""
    progress = UserProgress(
        node_id=1,
        mastery_level=0.75,
    )
    assert 0.0 <= progress.mastery_level <= 1.0


def test_source_types() -> None:
    """Source should categorize by type."""
    academic = Source(
        url="https://arxiv.org/paper",
        source_type="academic",
        base_dependability_score=0.9,
    )
    blog = Source(
        url="https://blog.example.com/post",
        source_type="expert_blog",
        base_dependability_score=0.6,
    )
    assert academic.base_dependability_score > blog.base_dependability_score


def test_lesson_has_paths() -> None:
    """Lesson should track file paths for materials."""
    lesson = Lesson(
        subject_id="kubernetes",
        date=datetime.now().date(),
        node_ids_covered=[1, 2, 3],
        audio_path="/path/to/audio.mp3",
        materials_path="/path/to/materials/",
    )
    assert lesson.audio_path is not None
    assert len(lesson.node_ids_covered) == 3


def test_assessment_response_srs() -> None:
    """AssessmentResponse should track SRS scheduling."""
    response = AssessmentResponse(
        lesson_id=1,
        node_id=1,
        question_hash="abc123",
        response="The answer",
        correct=True,
    )
    assert response.next_review is not None


def test_subject_status_enum() -> None:
    """SubjectStatus should have expected values."""
    assert SubjectStatus.INITIALIZING.value == "initializing"
    assert SubjectStatus.RESEARCHING.value == "researching"
    assert SubjectStatus.READY.value == "ready"
    assert SubjectStatus.PAUSED.value == "paused"
