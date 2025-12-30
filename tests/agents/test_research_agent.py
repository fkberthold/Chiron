"""Tests for ResearchAgent."""

from chiron.agents.research import RESEARCH_AGENT_PROMPT, ResearchAgent


def test_research_agent_has_system_prompt() -> None:
    """ResearchAgent should have a specialized system prompt."""
    assert RESEARCH_AGENT_PROMPT is not None
    assert "research" in RESEARCH_AGENT_PROMPT.lower()
    assert "source" in RESEARCH_AGENT_PROMPT.lower()


def test_research_agent_initialization() -> None:
    """ResearchAgent should initialize correctly."""
    agent = ResearchAgent()
    assert agent.config.name == "research"


def test_research_agent_prompt_includes_validation() -> None:
    """Research agent prompt should include source validation."""
    prompt_lower = RESEARCH_AGENT_PROMPT.lower()
    assert "validation" in prompt_lower or "validate" in prompt_lower
    assert "confidence" in prompt_lower
