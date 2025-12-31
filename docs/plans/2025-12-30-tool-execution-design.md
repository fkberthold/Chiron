# Tool Execution Design for Live Research Progress

## Goal

Execute MCP tools during agent runs so research progress displays live updates. For multi-hour research sessions (e.g., "How to think about the world like C.S. Peirce"), users need to see directions the research is progressing in real-time.

## Design Decisions

- **All tools available to all agents** - System prompts guide which tools each agent uses
- **Loop until done** - Keep calling Claude until it stops requesting tools (enables multi-step reasoning)
- **Separate tool functions module** - Pure functions in `src/chiron/tools/`, imported by both agents and MCP server
- **View-only progress** - User watches progress, Ctrl+C to stop, no mid-session steering

## Architecture Overview

```
User runs "chiron research start"
    → Orchestrator creates ResearchAgent with tools + db/vector_store
    → Agent.run() enters tool execution loop:
        → Call Claude API with tool definitions
        → Claude returns tool_use blocks
        → Execute each tool (writes to db/vector_store immediately)
        → Send tool results back to Claude
        → Repeat until Claude returns only text
    → Progress display polls db/vector_store periodically
    → User sees facts accumulating in real-time
```

## Components

### 1. Tool Functions Module

**New structure:** `src/chiron/tools/`

```
src/chiron/tools/
├── __init__.py          # Exports all tools + get_all_tool_definitions()
├── knowledge.py         # store_knowledge, vector_search
├── subjects.py          # get/set_active_subject, list_subjects
├── learning_goals.py    # get/save_learning_goal
├── knowledge_nodes.py   # get/save_knowledge_node, get_knowledge_tree
└── progress.py          # get_user_progress, record_assessment
```

**Tool function signature pattern:**

```python
def store_knowledge(
    db: Database,
    vector_store: VectorStore,
    *,
    content: str,
    subject_id: str,
    source_url: str,
    # ... other params
) -> dict[str, str]:
    """Store a knowledge chunk. Returns confirmation dict."""
```

Key points:
- Pure functions - no global state, receive db/vector_store as args
- Return dicts (JSON-serializable for Claude)
- `get_all_tool_definitions()` returns list of Anthropic `ToolParam` dicts

**MCP server changes:**
- `create_mcp_server()` imports from `tools/` and wraps with `@mcp.tool`
- No logic duplication

### 2. BaseAgent Tool Execution Loop

**Changes to AgentConfig and BaseAgent:**

```python
@dataclass
class AgentConfig:
    name: str
    system_prompt: str
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8192
    # mcp_server_url removed - no longer needed

@dataclass
class BaseAgent:
    config: AgentConfig
    tools: list[ToolParam] | None = None           # Tool definitions for Claude
    tool_executor: Callable | None = None          # Function to execute tools
    messages: list[MessageParam] = field(default_factory=list)
    _client: Anthropic = field(default_factory=Anthropic, repr=False)
```

**The run() method loop:**

```python
def run(self, initial_message: str) -> str:
    self.add_user_message(initial_message)

    while True:
        response = self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.config.system_prompt,
            messages=self.messages,
            tools=self.tools or [],
        )

        # Check for tool_use blocks
        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if not tool_uses:
            # No tools - extract text and return
            return self._extract_text(response)

        # Add assistant's response (with tool_use blocks) to history
        self._add_assistant_content(response.content)

        # Execute each tool, collect results
        tool_results = []
        for tool_use in tool_uses:
            result = self.tool_executor(tool_use.name, tool_use.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": json.dumps(result),
            })

        # Add tool results as user message
        self.messages.append({"role": "user", "content": tool_results})
        # Loop continues...
```

### 3. Orchestrator Wiring

**Orchestrator creates tool executor bound to db/vector_store:**

```python
def __init__(
    self,
    db: Database,
    vector_store: VectorStore,
    lessons_dir: Path,
) -> None:
    self.db = db
    self.vector_store = vector_store
    self.lessons_dir = lessons_dir
    # mcp_server_url removed

    self._tool_executor = self._create_tool_executor()
    self._tool_definitions = get_all_tool_definitions()
    # ... rest unchanged

def _create_tool_executor(self) -> Callable[[str, dict], dict]:
    from chiron.tools import TOOL_REGISTRY

    def execute(name: str, args: dict) -> dict:
        func = TOOL_REGISTRY[name]
        return func(self.db, self.vector_store, **args)

    return execute
```

**Agent creation passes tools:**

```python
@property
def research_agent(self) -> ResearchAgent:
    if self._research_agent is None:
        self._research_agent = ResearchAgent(
            tools=self._tool_definitions,
            tool_executor=self._tool_executor,
        )
    return self._research_agent
```

### 4. Error Handling

Errors returned as data, not exceptions:

```python
def execute(name: str, args: dict) -> dict:
    func = TOOL_REGISTRY.get(name)
    if func is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return func(self.db, self.vector_store, **args)
    except Exception as e:
        return {"error": str(e)}
```

Claude sees errors and can adjust its approach.

## Testing Strategy

1. **Unit tests for tool functions** - Test each function in `tools/` directly with mock db/vector_store
2. **Unit tests for BaseAgent loop** - Mock Anthropic client to return scripted tool_use responses, verify loop executes tools and terminates
3. **Existing tests** - Update to pass `tools=None, tool_executor=None` (backward compatible)

No integration tests with real Claude API - too slow/expensive for CI.

## Files to Modify

### New Files
- `src/chiron/tools/__init__.py`
- `src/chiron/tools/knowledge.py`
- `src/chiron/tools/subjects.py`
- `src/chiron/tools/learning_goals.py`
- `src/chiron/tools/knowledge_nodes.py`
- `src/chiron/tools/progress.py`
- `tests/tools/test_*.py`

### Modified Files
- `src/chiron/agents/base.py` - Add tool execution loop
- `src/chiron/agents/research.py` - Accept tools in constructor
- `src/chiron/agents/curriculum.py` - Accept tools in constructor
- `src/chiron/agents/lesson.py` - Accept tools in constructor
- `src/chiron/agents/assessment.py` - Accept tools in constructor
- `src/chiron/orchestrator.py` - Wire tools to agents, remove mcp_server_url
- `src/chiron/mcp_server/server.py` - Import from tools module
- `tests/agents/test_*.py` - Update for new constructor args
