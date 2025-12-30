"""Tests for AssessmentAgent."""

from chiron.agents.assessment import ASSESSMENT_AGENT_PROMPT, AssessmentAgent


def test_assessment_agent_has_system_prompt() -> None:
    """AssessmentAgent should have a specialized system prompt."""
    assert ASSESSMENT_AGENT_PROMPT is not None
    assert "assessment" in ASSESSMENT_AGENT_PROMPT.lower()


def test_assessment_agent_initialization() -> None:
    """AssessmentAgent should initialize correctly."""
    agent = AssessmentAgent()
    assert agent.config.name == "assessment"


def test_assessment_agent_prompt_includes_srs() -> None:
    """Assessment agent prompt should mention spaced repetition."""
    prompt_lower = ASSESSMENT_AGENT_PROMPT.lower()
    assert "spaced repetition" in prompt_lower or "srs" in prompt_lower


def test_assessment_agent_prompt_includes_remediation() -> None:
    """Assessment agent prompt should mention remediation."""
    prompt_lower = ASSESSMENT_AGENT_PROMPT.lower()
    assert "remediation" in prompt_lower or "understanding" in prompt_lower
