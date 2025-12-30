"""Tests for MCP server."""

import tempfile
from pathlib import Path

import pytest

from chiron.mcp_server import create_mcp_server
from chiron.storage import Database, VectorStore


@pytest.fixture
def db() -> Database:
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        database = Database(db_path)
        database.initialize()
        yield database


@pytest.fixture
def vector_store() -> VectorStore:
    """Create a temporary vector store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "vectors"
        store = VectorStore(store_path)
        yield store


REQUIRED_TOOLS = [
    "vector_search",
    "store_knowledge",
    "get_active_subject",
    "set_active_subject",
    "list_subjects",
    "get_user_progress",
    "record_assessment",
    "get_learning_goal",
    "save_learning_goal",
    "get_knowledge_node",
    "get_knowledge_tree",
    "save_knowledge_node",
]


@pytest.mark.asyncio
async def test_mcp_server_has_required_tools(
    db: Database, vector_store: VectorStore
) -> None:
    """MCP server should have all required tools registered."""
    mcp = create_mcp_server(db, vector_store)

    tools = await mcp.get_tools()
    tool_names = set(tools.keys())

    for required_tool in REQUIRED_TOOLS:
        assert required_tool in tool_names, f"Missing required tool: {required_tool}"


@pytest.mark.asyncio
async def test_mcp_server_tool_descriptions(
    db: Database, vector_store: VectorStore
) -> None:
    """All MCP server tools should have descriptions."""
    mcp = create_mcp_server(db, vector_store)

    tools = await mcp.get_tools()

    for name, tool in tools.items():
        assert tool.description, f"Tool '{name}' is missing a description"
        assert len(tool.description) > 10, (
            f"Tool '{name}' has a too-short description: {tool.description}"
        )
