"""Agent implementations for Chiron."""

from chiron.agents.base import AgentConfig, BaseAgent
from chiron.agents.curriculum import CURRICULUM_AGENT_PROMPT, CurriculumAgent

__all__ = [
    "AgentConfig",
    "BaseAgent",
    "CURRICULUM_AGENT_PROMPT",
    "CurriculumAgent",
]
