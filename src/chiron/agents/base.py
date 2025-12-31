"""Base agent class for Claude Code agents."""

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from anthropic import Anthropic

if TYPE_CHECKING:
    from anthropic.types import MessageParam, ToolParam


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    system_prompt: str
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8192


@dataclass
class BaseAgent:
    """Base class for all Chiron agents."""

    config: AgentConfig
    tools: list["ToolParam"] | None = None
    tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None
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

    def _add_assistant_content(self, content: list[Any]) -> None:
        """Add raw assistant content blocks to the conversation."""
        self.messages.append({
            "role": "assistant",
            "content": content,
        })

    def clear_messages(self) -> None:
        """Clear the conversation history."""
        self.messages = []

    def _extract_text(self, response: Any) -> str:
        """Extract text content from response."""
        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        return "".join(text_parts)

    def run(self, initial_message: str) -> str:
        """Run the agent with an initial message.

        Args:
            initial_message: The first user message to send

        Returns:
            The agent's response
        """
        self.add_user_message(initial_message)

        while True:
            # Build API call kwargs
            kwargs: dict[str, Any] = {
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "system": self.config.system_prompt,
                "messages": self.messages,
            }
            if self.tools:
                kwargs["tools"] = self.tools

            response = self._client.messages.create(**kwargs)

            # Check for tool_use blocks
            tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]

            if not tool_uses:
                # No tool calls - extract text and return
                content = self._extract_text(response)
                self.add_assistant_message(content)
                return content

            # Add assistant's response (with tool_use blocks) to history
            self._add_assistant_content(list(response.content))

            # Execute each tool, collect results
            tool_results: list[dict[str, Any]] = []
            for tool_use in tool_uses:
                if self.tool_executor:
                    result = self.tool_executor(tool_use.name, tool_use.input)
                else:
                    result = {"error": "No tool executor configured"}

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result),
                })

            # Add tool results as user message
            self.messages.append({"role": "user", "content": tool_results})
            # Loop continues...

    def continue_conversation(self, user_message: str) -> str:
        """Continue the conversation with another message.

        Args:
            user_message: The next user message

        Returns:
            The agent's response
        """
        return self.run(user_message)
