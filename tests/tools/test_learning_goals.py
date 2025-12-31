"""Tests for learning goal tools."""

from unittest.mock import MagicMock

from chiron.tools.learning_goals import get_learning_goal, save_learning_goal


def test_get_learning_goal_returns_goal_dict() -> None:
    """get_learning_goal should return goal as dict."""
    mock_db = MagicMock()
    mock_vs = MagicMock()

    mock_goal = MagicMock()
    mock_goal.model_dump.return_value = {
        "subject_id": "python",
        "purpose_statement": "Learn Python",
    }
    mock_db.get_learning_goal.return_value = mock_goal

    result = get_learning_goal(mock_db, mock_vs, subject_id="python")

    mock_db.get_learning_goal.assert_called_once_with("python")
    assert result == {"subject_id": "python", "purpose_statement": "Learn Python"}


def test_get_learning_goal_returns_none_when_not_found() -> None:
    """get_learning_goal should return None when goal doesn't exist."""
    mock_db = MagicMock()
    mock_vs = MagicMock()
    mock_db.get_learning_goal.return_value = None

    result = get_learning_goal(mock_db, mock_vs, subject_id="nonexistent")

    assert result is None


def test_save_learning_goal_creates_and_returns_goal() -> None:
    """save_learning_goal should save and return the goal."""
    mock_db = MagicMock()
    mock_vs = MagicMock()
    mock_db.save_learning_goal.return_value = 1  # Returns ID

    result = save_learning_goal(
        mock_db,
        mock_vs,
        subject_id="rust",
        purpose_statement="Learn systems programming",
        target_depth="deep",
    )

    mock_db.save_learning_goal.assert_called_once()
    saved_goal = mock_db.save_learning_goal.call_args[0][0]
    assert saved_goal.subject_id == "rust"
    assert saved_goal.purpose_statement == "Learn systems programming"
    assert saved_goal.target_depth == "deep"

    # Result should include the ID
    assert result["subject_id"] == "rust"
    assert result["id"] == 1
