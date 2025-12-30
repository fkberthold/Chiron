"""Agent implementations for Chiron."""

from chiron.agents.base import AgentConfig, BaseAgent
from chiron.agents.curriculum import CURRICULUM_AGENT_PROMPT, CurriculumAgent
from chiron.agents.lesson import LESSON_AGENT_PROMPT, LessonAgent
from chiron.agents.research import RESEARCH_AGENT_PROMPT, ResearchAgent

__all__ = [
    "AgentConfig",
    "BaseAgent",
    "CURRICULUM_AGENT_PROMPT",
    "CurriculumAgent",
    "LESSON_AGENT_PROMPT",
    "LessonAgent",
    "RESEARCH_AGENT_PROMPT",
    "ResearchAgent",
]
