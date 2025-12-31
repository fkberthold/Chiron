"""Tool functions for Chiron agents."""

import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from chiron.tools.knowledge import store_knowledge, vector_search
from chiron.tools.knowledge_nodes import (
    get_knowledge_node,
    get_knowledge_tree,
    save_knowledge_node,
)
from chiron.tools.learning_goals import get_learning_goal, save_learning_goal
from chiron.tools.progress import get_user_progress, record_assessment
from chiron.tools.subjects import get_active_subject, list_subjects, set_active_subject

__all__ = [
    "get_active_subject",
    "get_knowledge_node",
    "get_knowledge_tree",
    "get_learning_goal",
    "get_user_progress",
    "list_subjects",
    "record_assessment",
    "save_knowledge_node",
    "save_learning_goal",
    "set_active_subject",
    "store_knowledge",
    "vector_search",
    "TOOL_REGISTRY",
    "get_all_tool_definitions",
]

# Registry mapping tool names to functions
TOOL_REGISTRY: dict[str, Callable[..., Any]] = {
    "get_active_subject": get_active_subject,
    "get_knowledge_node": get_knowledge_node,
    "get_knowledge_tree": get_knowledge_tree,
    "get_learning_goal": get_learning_goal,
    "get_user_progress": get_user_progress,
    "list_subjects": list_subjects,
    "record_assessment": record_assessment,
    "save_knowledge_node": save_knowledge_node,
    "save_learning_goal": save_learning_goal,
    "set_active_subject": set_active_subject,
    "store_knowledge": store_knowledge,
    "vector_search": vector_search,
}


def _python_type_to_json_schema(py_type: Any) -> dict[str, Any]:
    """Convert Python type annotation to JSON schema."""
    origin = getattr(py_type, "__origin__", None)

    if py_type is str:
        return {"type": "string"}
    elif py_type is int:
        return {"type": "integer"}
    elif py_type is float:
        return {"type": "number"}
    elif py_type is bool:
        return {"type": "boolean"}
    elif origin is list:
        args = getattr(py_type, "__args__", (Any,))
        return {"type": "array", "items": _python_type_to_json_schema(args[0])}
    elif origin is type(None):
        return {"type": "null"}
    else:
        return {"type": "string"}  # Fallback


def _get_tool_definition(name: str, func: Callable[..., Any]) -> dict[str, Any]:
    """Generate Anthropic ToolParam from function signature."""
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    doc = inspect.getdoc(func) or ""

    # Extract first line of docstring as description
    description = doc.split("\n")[0] if doc else f"Tool: {name}"

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        # Skip db and vector_store parameters
        if param_name in ("db", "vector_store"):
            continue

        param_type = hints.get(param_name, str)

        # Handle Optional types
        origin = getattr(param_type, "__origin__", None)
        has_args = hasattr(param_type, "__args__")
        args_tuple = getattr(param_type, "__args__", ())
        is_optional = origin is type(None) or (has_args and type(None) in args_tuple)
        if is_optional:
            # It's Optional, extract the inner type
            args = getattr(param_type, "__args__", ())
            param_type = next((a for a in args if a is not type(None)), str)
        else:
            # Required parameter (no default or keyword-only without default)
            is_empty = param.default is inspect.Parameter.empty
            is_var_keyword = param.kind == inspect.Parameter.VAR_KEYWORD
            if is_empty and not is_var_keyword:
                required.append(param_name)

        properties[param_name] = _python_type_to_json_schema(param_type)

    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def get_all_tool_definitions() -> list[dict[str, Any]]:
    """Get all tool definitions in Anthropic ToolParam format."""
    return [_get_tool_definition(name, func) for name, func in TOOL_REGISTRY.items()]
