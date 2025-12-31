"""Tests for tool registry and definitions."""

from chiron.tools import TOOL_REGISTRY, get_all_tool_definitions


def test_tool_registry_contains_all_tools() -> None:
    """TOOL_REGISTRY should map tool names to functions."""
    expected_tools = [
        "store_knowledge",
        "vector_search",
        "get_active_subject",
        "set_active_subject",
        "list_subjects",
        "get_learning_goal",
        "save_learning_goal",
        "get_knowledge_node",
        "get_knowledge_tree",
        "save_knowledge_node",
        "get_user_progress",
        "record_assessment",
    ]

    for tool_name in expected_tools:
        assert tool_name in TOOL_REGISTRY, f"Missing tool: {tool_name}"
        assert callable(TOOL_REGISTRY[tool_name])


def test_get_all_tool_definitions_returns_list() -> None:
    """get_all_tool_definitions should return Anthropic ToolParam format."""
    definitions = get_all_tool_definitions()

    assert isinstance(definitions, list)
    assert len(definitions) == 12  # All tools

    # Check structure of first definition
    first_def = definitions[0]
    assert "name" in first_def
    assert "description" in first_def
    assert "input_schema" in first_def
    assert first_def["input_schema"]["type"] == "object"


def test_store_knowledge_definition_has_correct_schema() -> None:
    """store_knowledge should have correct parameter schema."""
    definitions = get_all_tool_definitions()
    store_def = next(d for d in definitions if d["name"] == "store_knowledge")

    props = store_def["input_schema"]["properties"]
    assert "content" in props
    assert "subject_id" in props
    assert "source_url" in props
    assert "source_score" in props
    assert "topic_path" in props
    assert "confidence" in props

    required = store_def["input_schema"]["required"]
    assert "content" in required
    assert "subject_id" in required
