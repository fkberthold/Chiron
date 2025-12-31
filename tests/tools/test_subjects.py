"""Tests for subject management tools."""

from unittest.mock import MagicMock

from chiron.tools.subjects import get_active_subject, set_active_subject, list_subjects


def test_get_active_subject_returns_setting() -> None:
    """get_active_subject should return the active_subject setting."""
    mock_db = MagicMock()
    mock_vs = MagicMock()
    mock_db.get_setting.return_value = "kubernetes"

    result = get_active_subject(mock_db, mock_vs)

    mock_db.get_setting.assert_called_once_with("active_subject")
    assert result == "kubernetes"


def test_get_active_subject_returns_none_when_not_set() -> None:
    """get_active_subject should return None when no active subject."""
    mock_db = MagicMock()
    mock_vs = MagicMock()
    mock_db.get_setting.return_value = None

    result = get_active_subject(mock_db, mock_vs)

    assert result is None


def test_set_active_subject_updates_setting() -> None:
    """set_active_subject should update the database setting."""
    mock_db = MagicMock()
    mock_vs = MagicMock()

    result = set_active_subject(mock_db, mock_vs, subject_id="python")

    mock_db.set_setting.assert_called_once_with("active_subject", "python")
    assert result == {"status": "success", "active_subject": "python"}


def test_list_subjects_returns_all_goals() -> None:
    """list_subjects should return all learning goals as dicts."""
    mock_db = MagicMock()
    mock_vs = MagicMock()

    mock_goal = MagicMock()
    mock_goal.model_dump.return_value = {"subject_id": "test", "purpose": "Learn"}
    mock_db.list_subjects.return_value = [mock_goal]

    result = list_subjects(mock_db, mock_vs)

    assert result == [{"subject_id": "test", "purpose": "Learn"}]
