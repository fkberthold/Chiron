"""Tests for ChromaDB vector store."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from chiron.models import KnowledgeChunk
from chiron.storage import VectorStore


@pytest.fixture
def vector_store() -> VectorStore:
    """Create a temporary vector store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        persist_dir = Path(tmpdir) / "chroma"
        store = VectorStore(persist_dir)
        yield store


def test_store_and_search_knowledge(vector_store: VectorStore) -> None:
    """Should store knowledge chunks and find them via semantic search."""
    chunk = KnowledgeChunk(
        content="Kubernetes pods are the smallest deployable units in K8S",
        subject_id="kubernetes",
        source_url="https://kubernetes.io/docs",
        source_score=0.95,
        topic_path="architecture/pods",
        confidence=0.9,
    )
    vector_store.store_knowledge(chunk)

    results = vector_store.search(
        query="What are the basic building blocks in Kubernetes?",
        subject_id="kubernetes",
        top_k=5,
    )

    assert len(results) > 0
    assert results[0].content == chunk.content
    assert results[0].subject_id == "kubernetes"


def test_search_filters_by_subject(vector_store: VectorStore) -> None:
    """Search should only return results for the specified subject."""
    k8s_chunk = KnowledgeChunk(
        content="Kubernetes uses containers for application deployment",
        subject_id="kubernetes",
        source_url="https://kubernetes.io/docs",
        source_score=0.9,
        topic_path="basics/containers",
        confidence=0.85,
    )
    python_chunk = KnowledgeChunk(
        content="Python uses containers like lists and dictionaries",
        subject_id="python",
        source_url="https://docs.python.org",
        source_score=0.9,
        topic_path="basics/containers",
        confidence=0.85,
    )
    vector_store.store_knowledge(k8s_chunk)
    vector_store.store_knowledge(python_chunk)

    # Search for containers but filter by kubernetes
    results = vector_store.search(
        query="containers",
        subject_id="kubernetes",
        top_k=10,
    )

    assert len(results) == 1
    assert results[0].subject_id == "kubernetes"
    assert "Kubernetes" in results[0].content


def test_search_returns_metadata(vector_store: VectorStore) -> None:
    """Search results should include all metadata from the original chunk."""
    chunk = KnowledgeChunk(
        content="Services provide stable network endpoints for pods",
        subject_id="kubernetes",
        source_url="https://kubernetes.io/docs/services",
        source_score=0.92,
        topic_path="networking/services",
        confidence=0.88,
        contradictions=["Some sources say endpoints are deprecated"],
        last_validated=datetime(2024, 1, 15, 10, 30, 0),
    )
    vector_store.store_knowledge(chunk)

    results = vector_store.search(
        query="network endpoints",
        subject_id="kubernetes",
        top_k=1,
    )

    assert len(results) == 1
    result = results[0]
    assert result.source_url == "https://kubernetes.io/docs/services"
    assert result.source_score == 0.92
    assert result.topic_path == "networking/services"
    assert result.confidence == 0.88
    assert "deprecated" in result.contradictions[0]


def test_delete_by_subject(vector_store: VectorStore) -> None:
    """Should delete all chunks for a specific subject."""
    k8s_chunk1 = KnowledgeChunk(
        content="Pods are ephemeral by default",
        subject_id="kubernetes",
        source_url="https://kubernetes.io/docs",
        source_score=0.9,
        topic_path="architecture/pods",
        confidence=0.85,
    )
    k8s_chunk2 = KnowledgeChunk(
        content="Deployments manage pod lifecycles",
        subject_id="kubernetes",
        source_url="https://kubernetes.io/docs",
        source_score=0.9,
        topic_path="architecture/deployments",
        confidence=0.85,
    )
    python_chunk = KnowledgeChunk(
        content="Python is a high-level programming language",
        subject_id="python",
        source_url="https://docs.python.org",
        source_score=0.9,
        topic_path="intro",
        confidence=0.9,
    )
    vector_store.store_knowledge(k8s_chunk1)
    vector_store.store_knowledge(k8s_chunk2)
    vector_store.store_knowledge(python_chunk)

    # Delete kubernetes chunks
    vector_store.delete_subject("kubernetes")

    # Search should find no kubernetes chunks
    k8s_results = vector_store.search(
        query="pods deployments",
        subject_id="kubernetes",
        top_k=10,
    )
    assert len(k8s_results) == 0

    # Python chunks should still exist
    python_results = vector_store.search(
        query="programming language",
        subject_id="python",
        top_k=10,
    )
    assert len(python_results) == 1
    assert python_results[0].subject_id == "python"
