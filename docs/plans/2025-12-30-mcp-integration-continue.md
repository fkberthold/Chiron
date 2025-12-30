# Continue: MCP Tool Execution Integration

## Context

The research progress display feature is complete, but it shows no data because the agents don't actually execute MCP tools. The agents call the Claude API and return text, but they don't:
1. Pass tools to the API
2. Handle `tool_use` response blocks
3. Execute the MCP tools
4. Send results back to Claude

## Current State

**Working:**
- MCP server exists at `src/chiron/mcp_server/server.py` with tools like `store_knowledge`, `save_knowledge_node`, `vector_search`, etc.
- Progress display in `src/chiron/display/progress.py` correctly queries the database and vector store
- All 98 tests pass

**Not Working:**
- `src/chiron/agents/base.py` - The `run()` method just calls `client.messages.create()` and returns text
- Agents output `<invoke>` XML showing what they *would* call, but nothing executes

## What to Implement

### Option A: In-Process Tool Execution (Simpler)

Instead of running MCP as a server, inject the tools directly into the agent:

1. **Modify `BaseAgent`** to accept a tools dictionary
2. **Create tool executor** that maps tool names to functions
3. **Update `run()` method** to:
   - Pass tools to Claude API
   - Check for `tool_use` content blocks in response
   - Execute tools and collect results
   - Call Claude again with tool results
   - Repeat until no more tool calls

Example flow:
```python
def run(self, initial_message: str) -> str:
    self.add_user_message(initial_message)

    while True:
        response = self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.config.system_prompt,
            messages=self.messages,
            tools=self.tools,  # Add tools here
        )

        # Check if response contains tool_use
        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if not tool_uses:
            # No tool calls, extract text and return
            return self._extract_text(response)

        # Execute tools and add results
        self.add_assistant_message(response.content)
        for tool_use in tool_uses:
            result = self._execute_tool(tool_use.name, tool_use.input)
            self.add_tool_result(tool_use.id, result)
```

### Option B: MCP Server Connection (More Complex)

Keep MCP as a separate server and connect to it:

1. Start MCP server on a port
2. Use MCP client library to connect
3. Translate between Claude tool format and MCP protocol

## Files to Modify

1. **`src/chiron/agents/base.py`**
   - Add `tools` parameter to `AgentConfig`
   - Add tool execution loop to `run()` method
   - Add `_execute_tool()` helper method

2. **`src/chiron/orchestrator.py`**
   - Pass database and vector_store tools to agents
   - Create tool definitions from MCP server functions

3. **`src/chiron/mcp_server/server.py`**
   - Export tool functions for direct use (not just MCP registration)

## Key Files to Read

- `src/chiron/agents/base.py` - Current agent implementation
- `src/chiron/mcp_server/server.py` - Existing MCP tools
- `src/chiron/orchestrator.py` - Where agents are created
- Anthropic docs on tool use: https://docs.anthropic.com/en/docs/build-with-claude/tool-use

## Testing

After implementation:
1. Run `chiron research start` on a subject
2. The agent should actually store facts via `store_knowledge`
3. Progress display should show topics and fact counts updating
4. Vector store should contain the stored facts

## Recommended Approach

Use Option A (in-process) for simplicity. The MCP server can still be used for external access, but agents can call tools directly without the server overhead.
