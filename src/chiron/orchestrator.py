"""Workflow orchestrator with state machine for Chiron learning sessions."""

from enum import Enum
from pathlib import Path

from chiron.agents import (
    AssessmentAgent,
    CurriculumAgent,
    LessonAgent,
    ResearchAgent,
)
from chiron.models import LearningGoal
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore


class WorkflowState(str, Enum):
    """States for the learning workflow state machine."""

    IDLE = "idle"
    INITIALIZING = "initializing"
    RESEARCHING = "researching"
    ASSESSING = "assessing"
    GENERATING_LESSON = "generating_lesson"
    DELIVERING_LESSON = "delivering_lesson"
    EXERCISING = "exercising"


class Orchestrator:
    """Orchestrates the learning workflow between agents."""

    def __init__(
        self,
        db: Database,
        vector_store: VectorStore,
        lessons_dir: Path,
        mcp_server_url: str | None = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            db: Database instance for structured data.
            vector_store: VectorStore instance for semantic search.
            lessons_dir: Directory for storing lesson files.
            mcp_server_url: Optional URL for MCP server connection.
        """
        self.db = db
        self.vector_store = vector_store
        self.lessons_dir = lessons_dir
        self.mcp_server_url = mcp_server_url

        self._state = WorkflowState.IDLE
        self._active_subject_id: str | None = None

        # Lazy-loaded agents
        self._curriculum_agent: CurriculumAgent | None = None
        self._research_agent: ResearchAgent | None = None
        self._lesson_agent: LessonAgent | None = None
        self._assessment_agent: AssessmentAgent | None = None

    @property
    def state(self) -> WorkflowState:
        """Get the current workflow state."""
        return self._state

    @state.setter
    def state(self, value: WorkflowState) -> None:
        """Set the workflow state."""
        self._state = value

    @property
    def curriculum_agent(self) -> CurriculumAgent:
        """Get or create the curriculum agent."""
        if self._curriculum_agent is None:
            self._curriculum_agent = CurriculumAgent(
                mcp_server_url=self.mcp_server_url
            )
        return self._curriculum_agent

    @property
    def research_agent(self) -> ResearchAgent:
        """Get or create the research agent."""
        if self._research_agent is None:
            self._research_agent = ResearchAgent(mcp_server_url=self.mcp_server_url)
        return self._research_agent

    @property
    def lesson_agent(self) -> LessonAgent:
        """Get or create the lesson agent."""
        if self._lesson_agent is None:
            self._lesson_agent = LessonAgent(mcp_server_url=self.mcp_server_url)
        return self._lesson_agent

    @property
    def assessment_agent(self) -> AssessmentAgent:
        """Get or create the assessment agent."""
        if self._assessment_agent is None:
            self._assessment_agent = AssessmentAgent(
                mcp_server_url=self.mcp_server_url
            )
        return self._assessment_agent

    def get_active_subject(self) -> str | None:
        """Get the currently active subject ID.

        Returns:
            The active subject ID or None if no subject is active.
        """
        if self._active_subject_id is not None:
            return self._active_subject_id

        # Check database for persisted active subject
        active = self.db.get_setting("active_subject")
        if active is not None:
            self._active_subject_id = active
        return self._active_subject_id

    def set_active_subject(self, subject_id: str) -> None:
        """Set the active subject.

        Args:
            subject_id: The subject ID to make active.

        Raises:
            ValueError: If the subject does not exist.
        """
        # Verify subject exists
        goal = self.db.get_learning_goal(subject_id)
        if goal is None:
            raise ValueError(f"Subject '{subject_id}' does not exist")

        self._active_subject_id = subject_id
        self.db.set_setting("active_subject", subject_id)

    def list_subjects(self) -> list[LearningGoal]:
        """List all available subjects.

        Returns:
            List of all learning goals.
        """
        return self.db.list_subjects()

    def initialize_subject(
        self, subject_id: str, purpose_statement: str
    ) -> LearningGoal:
        """Initialize a new learning subject.

        Args:
            subject_id: Unique identifier for the subject.
            purpose_statement: Why the user wants to learn this.

        Returns:
            The created learning goal.
        """
        self.state = WorkflowState.INITIALIZING

        goal = LearningGoal(
            subject_id=subject_id,
            purpose_statement=purpose_statement,
        )
        self.db.save_learning_goal(goal)
        self.set_active_subject(subject_id)

        self.state = WorkflowState.IDLE
        return goal

    def start_curriculum_design(self) -> str:
        """Start curriculum design for the active subject.

        Returns:
            The curriculum agent's initial response.

        Raises:
            ValueError: If no active subject is set.
        """
        subject_id = self.get_active_subject()
        if subject_id is None:
            raise ValueError("No active subject set")

        goal = self.db.get_learning_goal(subject_id)
        if goal is None:
            raise ValueError(f"Subject '{subject_id}' not found")

        self.state = WorkflowState.INITIALIZING
        return self.curriculum_agent.design_curriculum(
            purpose_statement=goal.purpose_statement,
            subject=subject_id,
        )

    def continue_curriculum_design(self, user_response: str) -> str:
        """Continue curriculum design with user feedback.

        Args:
            user_response: User's answer to questions or feedback.

        Returns:
            The curriculum agent's response.
        """
        return self.curriculum_agent.continue_design(user_response)

    def start_lesson(self) -> str:
        """Start a new lesson for the active subject.

        Returns:
            The assessment agent's opening message.

        Raises:
            ValueError: If no active subject is set.
        """
        subject_id = self.get_active_subject()
        if subject_id is None:
            raise ValueError("No active subject set")

        self.state = WorkflowState.ASSESSING

        # Get topics to cover for assessment context
        nodes = self.db.get_knowledge_tree(subject_id)
        topics = [node.title for node in nodes[:5]]

        return self.assessment_agent.start_assessment(
            subject_id=subject_id,
            upcoming_topics=topics if topics else None,
        )

    def continue_assessment(self, user_response: str) -> str:
        """Continue the assessment with a user response.

        Args:
            user_response: The user's answer to the assessment question.

        Returns:
            The assessment agent's response.
        """
        return self.assessment_agent.evaluate_response(user_response)

    def generate_lesson(self) -> str:
        """Generate a lesson based on assessment results.

        Returns:
            The generated lesson content.

        Raises:
            ValueError: If no active subject is set.
        """
        subject_id = self.get_active_subject()
        if subject_id is None:
            raise ValueError("No active subject set")

        self.state = WorkflowState.GENERATING_LESSON

        # Get assessment summary
        assessment_summary = self.assessment_agent.get_assessment_summary()

        # Get knowledge tree for topics
        nodes = self.db.get_knowledge_tree(subject_id)
        topics = [node.title for node in nodes[:5]]  # Limit to first 5 topics

        self.state = WorkflowState.DELIVERING_LESSON
        return self.lesson_agent.generate_lesson(
            subject_id=subject_id,
            topics=topics if topics else ["Introduction"],
            assessment_summary=assessment_summary,
        )
