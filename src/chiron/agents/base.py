"""Base agent class for Claude Code agents."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from anthropic import Anthropic

if TYPE_CHECKING:
    from anthropic.types import MessageParam


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    system_prompt: str
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8192
    mcp_server_url: str | None = None


@dataclass
class BaseAgent:
    """Base class for all Chiron agents."""

    config: AgentConfig
    messages: list["MessageParam"] = field(default_factory=list)
    _client: Anthropic = field(default_factory=Anthropic, repr=False)

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation."""
        self.messages.append({
            "role": "user",
            "content": content,
        })

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the conversation."""
        self.messages.append({
            "role": "assistant",
            "content": content,
        })

    def clear_messages(self) -> None:
        """Clear the conversation history."""
        self.messages = []

    def run(self, initial_message: str) -> str:
        """Run the agent with an initial message.

        Args:
            initial_message: The first user message to send

        Returns:
            The agent's response
        """
        self.add_user_message(initial_message)

        response = self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.config.system_prompt,
            messages=self.messages,
        )

        # Extract text content
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        self.add_assistant_message(content)
        return content

    def continue_conversation(self, user_message: str) -> str:
        """Continue the conversation with another message.

        Args:
            user_message: The next user message

        Returns:
            The agent's response
        """
        return self.run(user_message)
