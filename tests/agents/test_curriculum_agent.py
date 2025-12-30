"""Tests for CurriculumAgent."""

from chiron.agents.curriculum import CURRICULUM_AGENT_PROMPT, CurriculumAgent


def test_curriculum_agent_has_system_prompt() -> None:
    """CurriculumAgent should have a specialized system prompt."""
    assert CURRICULUM_AGENT_PROMPT is not None
    assert "curriculum" in CURRICULUM_AGENT_PROMPT.lower()
    assert "coverage map" in CURRICULUM_AGENT_PROMPT.lower()


def test_curriculum_agent_initialization() -> None:
    """CurriculumAgent should initialize with config."""
    agent = CurriculumAgent()
    assert agent.config.name == "curriculum"
    assert "curriculum" in agent.config.system_prompt.lower()


def test_curriculum_agent_inherits_base() -> None:
    """CurriculumAgent should have base agent capabilities."""
    agent = CurriculumAgent()

    # Should have message management
    agent.add_user_message("Test")
    assert len(agent.messages) == 1
    agent.clear_messages()
    assert len(agent.messages) == 0
