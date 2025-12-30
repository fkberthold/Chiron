"""Agent implementations for Chiron."""

from chiron.agents.base import AgentConfig, BaseAgent
from chiron.agents.curriculum import CURRICULUM_AGENT_PROMPT, CurriculumAgent
from chiron.agents.research import RESEARCH_AGENT_PROMPT, ResearchAgent

__all__ = [
    "AgentConfig",
    "BaseAgent",
    "CURRICULUM_AGENT_PROMPT",
    "CurriculumAgent",
    "RESEARCH_AGENT_PROMPT",
    "ResearchAgent",
]
