"""Tests for knowledge tools."""

from unittest.mock import MagicMock

from chiron.tools.knowledge import store_knowledge, vector_search


def test_store_knowledge_stores_chunk_and_returns_confirmation() -> None:
    """store_knowledge should store to vector store and return confirmation."""
    mock_db = MagicMock()
    mock_vs = MagicMock()

    result = store_knowledge(
        mock_db,
        mock_vs,
        content="Pods are the smallest deployable units in Kubernetes.",
        subject_id="kubernetes",
        source_url="https://kubernetes.io/docs",
        source_score=0.9,
        topic_path="Pods",
        confidence=0.85,
    )

    # Should call vector_store.store_knowledge
    mock_vs.store_knowledge.assert_called_once()
    stored_chunk = mock_vs.store_knowledge.call_args[0][0]
    assert stored_chunk.content == "Pods are the smallest deployable units in Kubernetes."
    assert stored_chunk.subject_id == "kubernetes"
    assert stored_chunk.source_url == "https://kubernetes.io/docs"
    assert stored_chunk.source_score == 0.9
    assert stored_chunk.topic_path == "Pods"
    assert stored_chunk.confidence == 0.85

    # Should return confirmation dict
    assert result == {
        "status": "stored",
        "subject_id": "kubernetes",
        "topic_path": "Pods",
    }


def test_vector_search_returns_list_of_dicts() -> None:
    """vector_search should return list of chunk dicts."""
    mock_db = MagicMock()
    mock_vs = MagicMock()

    # Create mock chunks that will be returned
    mock_chunk = MagicMock()
    mock_chunk.model_dump.return_value = {
        "content": "Test content",
        "subject_id": "test",
        "confidence": 0.8,
    }
    mock_vs.search.return_value = [mock_chunk]

    result = vector_search(
        mock_db,
        mock_vs,
        query="test query",
        subject_id="test",
        top_k=5,
    )

    mock_vs.search.assert_called_once_with(
        query="test query",
        subject_id="test",
        top_k=5,
        min_confidence=0.0,
    )
    assert result == [{"content": "Test content", "subject_id": "test", "confidence": 0.8}]
