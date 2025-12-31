"""Tests for progress tools."""

from unittest.mock import MagicMock

from chiron.tools.progress import get_user_progress, record_assessment


def test_get_user_progress_returns_none_for_now() -> None:
    """get_user_progress should return None (not yet implemented)."""
    mock_db = MagicMock()
    mock_vs = MagicMock()

    result = get_user_progress(mock_db, mock_vs, node_id=1)

    # TODO: Update when Database.get_user_progress is implemented
    assert result is None


def test_record_assessment_returns_assessment_dict() -> None:
    """record_assessment should return the assessment as dict."""
    mock_db = MagicMock()
    mock_vs = MagicMock()

    result = record_assessment(
        mock_db,
        mock_vs,
        node_id=1,
        question_hash="abc123",
        response="My answer",
        correct=True,
        lesson_id=5,
    )

    assert result["node_id"] == 1
    assert result["question_hash"] == "abc123"
    assert result["response"] == "My answer"
    assert result["correct"] is True
    assert result["lesson_id"] == 5
