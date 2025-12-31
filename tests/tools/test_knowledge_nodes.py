"""Tests for knowledge node tools."""

from unittest.mock import MagicMock

from chiron.tools.knowledge_nodes import (
    get_knowledge_node,
    get_knowledge_tree,
    save_knowledge_node,
)


def test_get_knowledge_node_returns_node_dict() -> None:
    """get_knowledge_node should return node as dict."""
    mock_db = MagicMock()
    mock_vs = MagicMock()

    mock_node = MagicMock()
    mock_node.model_dump.return_value = {"id": 1, "title": "Pods"}
    mock_db.get_knowledge_node.return_value = mock_node

    result = get_knowledge_node(mock_db, mock_vs, node_id=1)

    mock_db.get_knowledge_node.assert_called_once_with(1)
    assert result == {"id": 1, "title": "Pods"}


def test_get_knowledge_node_returns_none_when_not_found() -> None:
    """get_knowledge_node should return None when not found."""
    mock_db = MagicMock()
    mock_vs = MagicMock()
    mock_db.get_knowledge_node.return_value = None

    result = get_knowledge_node(mock_db, mock_vs, node_id=999)

    assert result is None


def test_get_knowledge_tree_returns_list_of_nodes() -> None:
    """get_knowledge_tree should return all nodes for subject."""
    mock_db = MagicMock()
    mock_vs = MagicMock()

    mock_node = MagicMock()
    mock_node.model_dump.return_value = {"id": 1, "title": "Pods", "depth": 0}
    mock_db.get_knowledge_tree.return_value = [mock_node]

    result = get_knowledge_tree(mock_db, mock_vs, subject_id="kubernetes")

    mock_db.get_knowledge_tree.assert_called_once_with("kubernetes")
    assert result == [{"id": 1, "title": "Pods", "depth": 0}]


def test_save_knowledge_node_creates_and_returns_node() -> None:
    """save_knowledge_node should save and return the node."""
    mock_db = MagicMock()
    mock_vs = MagicMock()
    mock_db.save_knowledge_node.return_value = 1

    result = save_knowledge_node(
        mock_db,
        mock_vs,
        subject_id="kubernetes",
        title="Pods",
        description="Smallest deployable unit",
        depth=0,
        is_goal_critical=True,
    )

    mock_db.save_knowledge_node.assert_called_once()
    saved_node = mock_db.save_knowledge_node.call_args[0][0]
    assert saved_node.subject_id == "kubernetes"
    assert saved_node.title == "Pods"
    assert saved_node.description == "Smallest deployable unit"
    assert saved_node.is_goal_critical is True

    assert result["id"] == 1
    assert result["title"] == "Pods"
