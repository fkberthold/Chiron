"""Tests for base agent class."""

from chiron.agents.base import AgentConfig, BaseAgent


def test_agent_config_has_required_fields() -> None:
    """AgentConfig should have model and system prompt."""
    config = AgentConfig(
        name="test_agent",
        model="claude-sonnet-4-20250514",
        system_prompt="You are a test agent.",
    )
    assert config.name == "test_agent"
    assert config.model == "claude-sonnet-4-20250514"
    assert config.system_prompt == "You are a test agent."


def test_agent_config_defaults() -> None:
    """AgentConfig should have sensible defaults."""
    config = AgentConfig(
        name="test",
        system_prompt="Test prompt",
    )
    assert config.model == "claude-sonnet-4-20250514"
    assert config.max_tokens == 8192


def test_base_agent_initialization() -> None:
    """BaseAgent should initialize with config."""
    config = AgentConfig(
        name="test_agent",
        system_prompt="You are a test agent.",
    )
    agent = BaseAgent(config)
    assert agent.config == config
    assert agent.messages == []


def test_base_agent_add_message() -> None:
    """BaseAgent should track conversation messages."""
    config = AgentConfig(name="test", system_prompt="Test")
    agent = BaseAgent(config)

    agent.add_user_message("Hello")
    assert len(agent.messages) == 1
    assert agent.messages[0]["role"] == "user"
    assert agent.messages[0]["content"] == "Hello"

    agent.add_assistant_message("Hi there!")
    assert len(agent.messages) == 2
    assert agent.messages[1]["role"] == "assistant"


def test_base_agent_clear_messages() -> None:
    """BaseAgent should be able to clear conversation."""
    config = AgentConfig(name="test", system_prompt="Test")
    agent = BaseAgent(config)

    agent.add_user_message("Hello")
    agent.add_assistant_message("Hi")
    assert len(agent.messages) == 2

    agent.clear_messages()
    assert len(agent.messages) == 0
