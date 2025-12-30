"""ChromaDB vector store for knowledge embeddings."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import chromadb
from chromadb.api.types import Where
from chromadb.config import Settings

from chiron.models import KnowledgeChunk


class VectorStore:
    """Vector store for semantic search of knowledge chunks using ChromaDB."""

    def __init__(self, persist_dir: Path) -> None:
        """Initialize vector store with persistence directory.

        Args:
            persist_dir: Path to the directory for persisting ChromaDB data.
        """
        self.persist_dir = persist_dir
        self._client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="knowledge_chunks",
            metadata={"hnsw:space": "cosine"},
        )

    def _generate_id(self, chunk: KnowledgeChunk) -> str:
        """Generate a unique ID for a knowledge chunk using SHA256 hash.

        Args:
            chunk: The knowledge chunk to generate an ID for.

        Returns:
            A SHA256 hash string based on the chunk's content and metadata.
        """
        # Create a unique identifier based on content and key metadata
        unique_string = f"{chunk.subject_id}:{chunk.topic_path}:{chunk.content}"
        return hashlib.sha256(unique_string.encode()).hexdigest()

    def _metadata_to_chunk(self, doc: str, metadata: dict[str, Any]) -> KnowledgeChunk:
        """Convert a document and metadata dict to a KnowledgeChunk.

        Args:
            doc: The document content.
            metadata: The metadata dictionary from ChromaDB.

        Returns:
            A KnowledgeChunk object.
        """
        return KnowledgeChunk(
            content=doc,
            subject_id=str(metadata["subject_id"]),
            source_url=str(metadata["source_url"]),
            source_score=float(metadata["source_score"]),
            topic_path=str(metadata["topic_path"]),
            confidence=float(metadata["confidence"]),
            contradictions=json.loads(str(metadata["contradictions"])),
            last_validated=datetime.fromisoformat(str(metadata["last_validated"])),
        )

    def store_knowledge(self, chunk: KnowledgeChunk) -> None:
        """Store a knowledge chunk in the vector store.

        Uses upsert to handle duplicates based on the generated ID.

        Args:
            chunk: The knowledge chunk to store.
        """
        chunk_id = self._generate_id(chunk)

        metadata: dict[str, str | int | float | bool] = {
            "subject_id": chunk.subject_id,
            "source_url": chunk.source_url,
            "source_score": chunk.source_score,
            "topic_path": chunk.topic_path,
            "confidence": chunk.confidence,
            "contradictions": json.dumps(chunk.contradictions),
            "last_validated": chunk.last_validated.isoformat(),
        }

        self._collection.upsert(
            ids=[chunk_id],
            documents=[chunk.content],
            metadatas=[metadata],
        )

    def search(
        self,
        query: str,
        subject_id: str,
        top_k: int = 5,
        min_confidence: float = 0.0,
    ) -> list[KnowledgeChunk]:
        """Search for knowledge chunks by semantic similarity.

        Args:
            query: The search query text.
            subject_id: Filter results to this subject only.
            top_k: Maximum number of results to return.
            min_confidence: Minimum confidence score for results.

        Returns:
            List of KnowledgeChunk objects matching the search criteria.
        """
        # Build where filter for subject_id
        where_filter: Where = cast(Where, {"subject_id": {"$eq": subject_id}})

        # Add confidence filter if specified
        if min_confidence > 0.0:
            where_filter = cast(
                Where,
                {
                    "$and": [
                        {"subject_id": {"$eq": subject_id}},
                        {"confidence": {"$gte": min_confidence}},
                    ]
                },
            )

        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter,
        )

        chunks: list[KnowledgeChunk] = []

        if results["documents"] and results["metadatas"]:
            for doc, metadata in zip(
                results["documents"][0], results["metadatas"][0], strict=True
            ):
                chunk = self._metadata_to_chunk(doc, cast(dict[str, Any], metadata))
                chunks.append(chunk)

        return chunks

    def delete_subject(self, subject_id: str) -> None:
        """Delete all knowledge chunks for a specific subject.

        Args:
            subject_id: The subject identifier to delete chunks for.
        """
        where_filter: Where = cast(Where, {"subject_id": {"$eq": subject_id}})
        self._collection.delete(where=where_filter)

    def get_by_topic(
        self, subject_id: str, topic_path: str
    ) -> list[KnowledgeChunk]:
        """Get all knowledge chunks for a specific subject and topic.

        Args:
            subject_id: The subject identifier.
            topic_path: The topic path to filter by.

        Returns:
            List of KnowledgeChunk objects matching the criteria.
        """
        where_filter: Where = cast(
            Where,
            {
                "$and": [
                    {"subject_id": {"$eq": subject_id}},
                    {"topic_path": {"$eq": topic_path}},
                ]
            },
        )
        results = self._collection.get(where=where_filter)

        chunks: list[KnowledgeChunk] = []

        if results["documents"] and results["metadatas"]:
            for doc, metadata in zip(
                results["documents"], results["metadatas"], strict=True
            ):
                chunk = self._metadata_to_chunk(doc, cast(dict[str, Any], metadata))
                chunks.append(chunk)

        return chunks
