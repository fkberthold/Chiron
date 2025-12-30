"""Tests for LessonAgent."""

from chiron.agents.lesson import LESSON_AGENT_PROMPT, LessonAgent


def test_lesson_agent_has_system_prompt() -> None:
    """LessonAgent should have a specialized system prompt."""
    assert LESSON_AGENT_PROMPT is not None
    assert "lesson" in LESSON_AGENT_PROMPT.lower()


def test_lesson_agent_initialization() -> None:
    """LessonAgent should initialize correctly."""
    agent = LessonAgent()
    assert agent.config.name == "lesson"


def test_lesson_agent_prompt_includes_audio() -> None:
    """Lesson agent prompt should mention audio script generation."""
    assert "audio" in LESSON_AGENT_PROMPT.lower()


def test_lesson_agent_prompt_includes_exercises() -> None:
    """Lesson agent prompt should mention exercise generation."""
    assert "exercise" in LESSON_AGENT_PROMPT.lower()
