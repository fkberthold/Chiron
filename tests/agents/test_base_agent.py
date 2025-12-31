"""Tests for base agent class."""

from unittest.mock import MagicMock

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


def test_base_agent_run_calls_api() -> None:
    """BaseAgent.run should call Anthropic API and return response."""
    config = AgentConfig(name="test", system_prompt="Test prompt")
    agent = BaseAgent(config)

    # Create mock client and replace the agent's client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_text_block = MagicMock()
    mock_text_block.text = "Hello response"
    mock_response.content = [mock_text_block]
    mock_client.messages.create.return_value = mock_response
    agent._client = mock_client

    result = agent.run("Hello")

    assert result == "Hello response"
    assert len(agent.messages) == 2
    assert agent.messages[0]["role"] == "user"
    assert agent.messages[0]["content"] == "Hello"
    assert agent.messages[1]["role"] == "assistant"
    assert agent.messages[1]["content"] == "Hello response"
    mock_client.messages.create.assert_called_once()


def test_base_agent_run_calls_api_with_correct_parameters() -> None:
    """BaseAgent.run should pass correct parameters to API."""
    config = AgentConfig(
        name="test",
        system_prompt="You are a helpful assistant.",
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
    )
    agent = BaseAgent(config)

    # Create mock client and replace the agent's client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_text_block = MagicMock()
    mock_text_block.text = "Response"
    mock_response.content = [mock_text_block]
    mock_client.messages.create.return_value = mock_response
    agent._client = mock_client

    agent.run("Test message")

    # Verify API was called once
    mock_client.messages.create.assert_called_once()

    # Check call arguments (note: messages list is mutable, so we check the call kwargs)
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-20250514"
    assert call_kwargs["max_tokens"] == 4096
    assert call_kwargs["system"] == "You are a helpful assistant."
    # The messages list passed to API should have included user message at call time
    # We verify the agent's final state instead
    assert len(agent.messages) == 2
    assert agent.messages[0] == {"role": "user", "content": "Test message"}


def test_base_agent_continue_conversation() -> None:
    """BaseAgent.continue_conversation should continue existing conversation."""
    config = AgentConfig(name="test", system_prompt="Test prompt")
    agent = BaseAgent(config)

    # Create mock client and replace the agent's client
    mock_client = MagicMock()

    # First response
    mock_response1 = MagicMock()
    mock_text_block1 = MagicMock()
    mock_text_block1.text = "First response"
    mock_response1.content = [mock_text_block1]

    # Second response
    mock_response2 = MagicMock()
    mock_text_block2 = MagicMock()
    mock_text_block2.text = "Second response"
    mock_response2.content = [mock_text_block2]

    mock_client.messages.create.side_effect = [mock_response1, mock_response2]
    agent._client = mock_client

    result1 = agent.run("First message")
    result2 = agent.continue_conversation("Second message")

    assert result1 == "First response"
    assert result2 == "Second response"
    assert len(agent.messages) == 4
    assert agent.messages[0]["content"] == "First message"
    assert agent.messages[1]["content"] == "First response"
    assert agent.messages[2]["content"] == "Second message"
    assert agent.messages[3]["content"] == "Second response"
    assert mock_client.messages.create.call_count == 2


def test_base_agent_executes_tools_and_loops() -> None:
    """BaseAgent should execute tools and loop until no more tool calls."""
    config = AgentConfig(name="test", system_prompt="Test prompt")

    # Create tool executor mock
    tool_executor = MagicMock()
    tool_executor.return_value = {"status": "stored", "topic": "test"}

    # Create agent with tools
    tools = [
        {
            "name": "store_knowledge",
            "description": "Store",
            "input_schema": {"type": "object", "properties": {}},
        }
    ]
    agent = BaseAgent(config, tools=tools, tool_executor=tool_executor)

    # Mock client
    mock_client = MagicMock()

    # First response: tool_use
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.id = "tool_123"
    mock_tool_use.name = "store_knowledge"
    mock_tool_use.input = {"content": "test fact"}
    mock_response1 = MagicMock()
    mock_response1.content = [mock_tool_use]

    # Second response: text only (no tools)
    mock_text = MagicMock()
    mock_text.type = "text"
    mock_text.text = "Done storing knowledge."
    mock_response2 = MagicMock()
    mock_response2.content = [mock_text]

    mock_client.messages.create.side_effect = [mock_response1, mock_response2]
    agent._client = mock_client

    result = agent.run("Store some knowledge")

    # Should have called API twice (tool call + final response)
    assert mock_client.messages.create.call_count == 2

    # Should have executed the tool
    tool_executor.assert_called_once_with("store_knowledge", {"content": "test fact"})

    # Should return final text
    assert result == "Done storing knowledge."


def test_base_agent_without_tools_works_as_before() -> None:
    """BaseAgent without tools should work exactly as before."""
    config = AgentConfig(name="test", system_prompt="Test prompt")
    agent = BaseAgent(config)  # No tools

    mock_client = MagicMock()
    mock_text = MagicMock()
    mock_text.text = "Hello!"
    mock_text.type = "text"
    mock_response = MagicMock()
    mock_response.content = [mock_text]
    mock_client.messages.create.return_value = mock_response
    agent._client = mock_client

    result = agent.run("Hi")

    assert result == "Hello!"
    mock_client.messages.create.assert_called_once()
