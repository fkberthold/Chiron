"""Data models for Chiron."""

from datetime import date, datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class SubjectStatus(str, Enum):
    """Status of a learning subject."""

    INITIALIZING = "initializing"
    RESEARCHING = "researching"
    READY = "ready"
    PAUSED = "paused"


class LearningGoal(BaseModel):
    """A learning goal for a subject."""

    id: int | None = None
    subject_id: str
    purpose_statement: str
    target_depth: str = "practical"
    created_date: datetime = Field(default_factory=datetime.now)
    research_complete: bool = False
    status: SubjectStatus = SubjectStatus.INITIALIZING


class KnowledgeNode(BaseModel):
    """A node in the knowledge/skill tree."""

    id: int | None = None
    subject_id: str
    parent_id: int | None = None
    title: str
    description: str | None = None
    depth: int = 0
    is_goal_critical: bool = False
    prerequisites: list[int] = Field(default_factory=list)
    shared_with_subjects: list[str] = Field(default_factory=list)


class UserProgress(BaseModel):
    """User's progress on a knowledge node."""

    node_id: int
    mastery_level: float = 0.0
    last_assessed: datetime | None = None
    next_review_date: datetime | None = None
    assessment_history: list[float] = Field(default_factory=list)
    ease_factor: float = 2.5  # SM-2 ease factor

    @field_validator("mastery_level")
    @classmethod
    def validate_mastery(cls, v: float) -> float:
        """Ensure mastery is between 0 and 1."""
        return max(0.0, min(1.0, v))


class Source(BaseModel):
    """A source of information."""

    id: int | None = None
    url: str
    source_type: str  # academic, official_docs, expert_blog, etc.
    base_dependability_score: float
    validation_count: int = 0
    last_checked: datetime | None = None
    notes: str | None = None

    @field_validator("base_dependability_score")
    @classmethod
    def validate_score(cls, v: float) -> float:
        """Ensure score is between 0 and 1."""
        return max(0.0, min(1.0, v))


class Lesson(BaseModel):
    """A generated lesson."""

    id: int | None = None
    subject_id: str
    date: date
    node_ids_covered: list[int] = Field(default_factory=list)
    audio_path: str | None = None
    materials_path: str | None = None
    duration_minutes: int | None = None


class AssessmentResponse(BaseModel):
    """A user's response to an assessment question."""

    id: int | None = None
    lesson_id: int | None = None
    node_id: int
    question_hash: str
    response: str
    correct: bool
    timestamp: datetime = Field(default_factory=datetime.now)
    next_review: datetime = Field(
        default_factory=lambda: datetime.now() + timedelta(days=1)
    )


class KnowledgeChunk(BaseModel):
    """A chunk of validated knowledge for vector storage."""

    content: str
    subject_id: str
    source_url: str
    source_score: float
    topic_path: str
    confidence: float
    contradictions: list[str] = Field(default_factory=list)
    last_validated: datetime = Field(default_factory=datetime.now)


class CoverageMapNode(BaseModel):
    """A node in the coverage map (curriculum structure)."""

    id: str
    title: str
    description: str | None = None
    children: list["CoverageMapNode"] = Field(default_factory=list)
    research_status: str = "pending"  # pending, in_progress, complete
    confidence: float = 0.0


# Enable forward references
CoverageMapNode.model_rebuild()
