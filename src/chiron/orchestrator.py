"""Workflow orchestrator with state machine for Chiron learning sessions."""

from enum import Enum
from pathlib import Path
from typing import Any, Callable

from chiron.agents import (
    AssessmentAgent,
    CurriculumAgent,
    LessonAgent,
    ResearchAgent,
)
from chiron.models import LearningGoal
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore
from chiron.tools import TOOL_REGISTRY, get_all_tool_definitions


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
    ) -> None:
        """Initialize the orchestrator.

        Args:
            db: Database instance for structured data.
            vector_store: VectorStore instance for semantic search.
            lessons_dir: Directory for storing lesson files.
        """
        self.db = db
        self.vector_store = vector_store
        self.lessons_dir = lessons_dir

        self._state = WorkflowState.IDLE
        self._active_subject_id: str | None = None

        # Tool infrastructure
        self._tool_executor = self._create_tool_executor()
        self._tool_definitions = get_all_tool_definitions()

        # Lazy-loaded agents
        self._curriculum_agent: CurriculumAgent | None = None
        self._research_agent: ResearchAgent | None = None
        self._lesson_agent: LessonAgent | None = None
        self._assessment_agent: AssessmentAgent | None = None

    def _create_tool_executor(self) -> Callable[[str, dict[str, Any]], dict[str, Any]]:
        """Create tool executor bound to this orchestrator's db/vector_store."""

        def execute(name: str, args: dict[str, Any]) -> dict[str, Any]:
            func = TOOL_REGISTRY.get(name)
            if func is None:
                return {"error": f"Unknown tool: {name}"}
            try:
                return func(self.db, self.vector_store, **args)
            except Exception as e:
                return {"error": str(e)}

        return execute

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
                tools=self._tool_definitions,
                tool_executor=self._tool_executor,
            )
        return self._curriculum_agent

    @property
    def research_agent(self) -> ResearchAgent:
        """Get or create the research agent."""
        if self._research_agent is None:
            self._research_agent = ResearchAgent(
                tools=self._tool_definitions,
                tool_executor=self._tool_executor,
            )
        return self._research_agent

    @property
    def lesson_agent(self) -> LessonAgent:
        """Get or create the lesson agent."""
        if self._lesson_agent is None:
            self._lesson_agent = LessonAgent(
                tools=self._tool_definitions,
                tool_executor=self._tool_executor,
            )
        return self._lesson_agent

    @property
    def assessment_agent(self) -> AssessmentAgent:
        """Get or create the assessment agent."""
        if self._assessment_agent is None:
            self._assessment_agent = AssessmentAgent(
                tools=self._tool_definitions,
                tool_executor=self._tool_executor,
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

    def delete_subject(self, subject_id: str) -> bool:
        """Delete a subject and all associated data.

        Args:
            subject_id: The subject ID to delete.

        Returns:
            True if deleted, False if subject didn't exist.
        """
        # Also delete from vector store
        self.vector_store.delete_subject(subject_id)

        # Clear active subject if it was this one
        if self._active_subject_id == subject_id:
            self._active_subject_id = None

        return self.db.delete_subject(subject_id)

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

    def start_research(self) -> str:
        """Start research for the active subject.

        Returns:
            The research agent's initial response.

        Raises:
            ValueError: If no active subject is set.
        """
        subject_id = self.get_active_subject()
        if subject_id is None:
            raise ValueError("No active subject set")

        goal = self.db.get_learning_goal(subject_id)
        if goal is None:
            raise ValueError(f"Subject '{subject_id}' not found")

        self.state = WorkflowState.RESEARCHING

        # Get knowledge tree to find topics to research
        nodes = self.db.get_knowledge_tree(subject_id)

        if nodes:
            # Research the first unresearched topic
            topic = nodes[0].title
            context = goal.purpose_statement
        else:
            # No knowledge tree yet - research the subject generally
            topic = subject_id.replace("-", " ").title()
            context = goal.purpose_statement

        return self.research_agent.research_topic(
            topic_path=topic,
            subject_id=subject_id,
            context=context,
        )

    def continue_research(self, user_input: str) -> str:
        """Continue research with user guidance.

        Args:
            user_input: User's direction or topic to research next.

        Returns:
            The research agent's response.
        """
        subject_id = self.get_active_subject()
        if subject_id is None:
            raise ValueError("No active subject set")

        # If user provides a topic, research it
        # Otherwise, continue with next topic from tree
        return self.research_agent.research_topic(
            topic_path=user_input,
            subject_id=subject_id,
        )

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

    def get_research_progress(self, subject_id: str | None = None) -> dict[str, Any]:
        """Get research progress for a subject.

        Combines knowledge tree structure with fact counts from vector store.

        Args:
            subject_id: Subject to get progress for. Uses active subject if None.

        Returns:
            Dictionary with:
            - subject_id: str
            - nodes: list of node dicts with id, title, depth, fact_count
            - total_facts: int

        Raises:
            ValueError: If no subject_id provided and no active subject set.
        """
        # Get subject_id (use active subject if None passed)
        if subject_id is None:
            subject_id = self.get_active_subject()
            if subject_id is None:
                raise ValueError("No active subject set")

        # Get knowledge tree nodes
        nodes = self.db.get_knowledge_tree(subject_id)

        # Get fact counts by topic from vector store
        fact_counts = self.vector_store.count_facts_by_topic(subject_id)

        # Combine nodes with fact counts
        node_list = []
        for node in nodes:
            node_list.append({
                "id": node.id,
                "title": node.title,
                "depth": node.depth,
                "fact_count": fact_counts.get(node.title, 0),
            })

        # Calculate total facts
        total_facts = sum(fact_counts.values())

        return {
            "subject_id": subject_id,
            "nodes": node_list,
            "total_facts": total_facts,
        }
