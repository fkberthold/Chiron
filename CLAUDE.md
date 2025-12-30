# CLAUDE.md

This file provides guidance to Claude Code when working with the Chiron project.

## Project Overview

Chiron is an AI-powered adaptive learning platform that uses Claude agents to create personalized learning experiences. The system features:
- CLI orchestrator spawning specialized Claude agents
- Local storage (ChromaDB for vectors, SQLite for structured data)
- Custom MCP server for agent data access
- Four specialized agents: Curriculum, Research, Lesson, Assessment

## Development Environment

### Devbox (Primary)

This project uses **devbox** for environment management with Python 3.11.

```bash
# Enter devbox shell (sets up Python environment)
devbox shell

# Or run commands directly
devbox run <command>
```

### Package Management: uv

This project uses **uv** for Python package management (NOT pip directly).

```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --all-extras

# Run commands through uv
uv run pytest
uv run ruff check
uv run mypy src/
```

### Virtual Environment

The project has a `.venv` directory managed by uv. When in devbox shell, uv commands work automatically.

## Project Structure

```
/home/frank/repos/Chiron/
├── devbox.json              # Devbox configuration (Python 3.11)
├── pyproject.toml           # Project config, dependencies, tool settings
├── uv.lock                  # uv lockfile
├── src/chiron/              # Main package
│   ├── __init__.py          # Package version
│   ├── __main__.py          # Entry point
│   ├── cli.py               # Click CLI commands
│   ├── config.py            # Pydantic settings
│   ├── models.py            # Pydantic data models
│   ├── agents/              # Agent implementations
│   │   ├── base.py          # BaseAgent class
│   │   ├── curriculum.py    # CurriculumAgent
│   │   └── research.py      # ResearchAgent
│   ├── storage/             # Data persistence
│   │   ├── database.py      # SQLite operations
│   │   └── vector_store.py  # ChromaDB operations
│   └── mcp_server/          # FastMCP server
│       ├── server.py        # MCP tools
│       └── __main__.py      # Server entry point
├── tests/                   # Test files
│   ├── agents/              # Agent tests
│   └── test_*.py            # Module tests
└── docs/plans/              # Implementation plans
```

## Common Commands

### ALWAYS use uv run for Python commands:

```bash
# Run tests
uv run pytest
uv run pytest tests/path/test_file.py -v

# Linting
uv run ruff check src/ tests/

# Type checking
uv run mypy src/chiron/

# Run CLI
uv run chiron --help
uv run chiron-mcp
```

### Git Operations

```bash
git add <files>
git commit -m "type: description"
```

## Code Quality Requirements

Before committing, ensure:
1. `uv run pytest` - All tests pass
2. `uv run ruff check src/ tests/` - No linting errors
3. `uv run mypy src/chiron/` - No type errors

## Key Technologies

- **Python 3.11+** via devbox
- **uv** for package management
- **Click** for CLI
- **Rich** for terminal output
- **Pydantic v2** for data models
- **pydantic-settings** for configuration
- **ChromaDB** for vector embeddings
- **SQLite** for structured data
- **FastMCP** for MCP server
- **Anthropic SDK** for Claude API

## Testing

Tests use pytest with pytest-asyncio for async tests.

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/agents/test_base_agent.py -v

# Run with coverage
uv run pytest --cov=src/chiron
```

## Claude Code Integration

### Codebase Search

Use claude-context MCP tools for semantic code search:
- `mcp__claude-context__search_code` - Search indexed code
- `mcp__claude-context__index_codebase` - Index/re-index codebase
- `mcp__claude-context__get_indexing_status` - Check index status

The codebase at `/home/frank/repos/Chiron` is already indexed.

### Implementation Plan

The active implementation plan is at:
`docs/plans/2025-12-29-chiron-implementation.md`

## Important Notes for Subagents

1. **Always use `uv run`** - Never use bare `pytest`, `ruff`, or `mypy`
2. **Devbox provides Python** - Don't try to install Python separately
3. **Check tests pass** before committing: `uv run pytest`
4. **Check linting** before committing: `uv run ruff check src/ tests/`
5. **Check types** before committing: `uv run mypy src/chiron/`
6. **Use claude-context** for code search, not grep/find for exploration
