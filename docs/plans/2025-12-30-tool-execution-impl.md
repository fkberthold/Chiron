# Tool Execution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable agents to execute MCP tools in-process so research progress displays live updates during multi-hour sessions.

**Architecture:** Extract tool logic from MCP server into pure functions in `src/chiron/tools/`. Modify `BaseAgent.run()` to loop through tool calls until Claude stops requesting them. Wire tools through Orchestrator.

**Tech Stack:** Python 3.11+, Anthropic SDK (tool_use blocks), Pydantic, pytest

---

## Task 1: Create Tool Functions - Knowledge Module

**Files:**
- Create: `src/chiron/tools/__init__.py`
- Create: `src/chiron/tools/knowledge.py`
- Create: `tests/tools/__init__.py`
- Create: `tests/tools/test_knowledge.py`

**Step 1: Create tools package init**

```python
# src/chiron/tools/__init__.py
"""Tool functions for Chiron agents."""

from chiron.tools.knowledge import store_knowledge, vector_search

__all__ = [
    "store_knowledge",
    "vector_search",
]
```

**Step 2: Create tests directory init**

```python
# tests/tools/__init__.py
"""Tests for tool functions."""
```

**Step 3: Write failing test for store_knowledge**

```python
# tests/tools/test_knowledge.py
"""Tests for knowledge tools."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from chiron.tools.knowledge import store_knowledge


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
```

**Step 4: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_knowledge.py::test_store_knowledge_stores_chunk_and_returns_confirmation -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'chiron.tools.knowledge'"

**Step 5: Write store_knowledge implementation**

```python
# src/chiron/tools/knowledge.py
"""Knowledge storage and search tools."""

from datetime import datetime
from typing import Any

from chiron.models import KnowledgeChunk
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore


def store_knowledge(
    db: Database,
    vector_store: VectorStore,
    *,
    content: str,
    subject_id: str,
    source_url: str,
    source_score: float,
    topic_path: str,
    confidence: float,
    contradictions: list[str] | None = None,
) -> dict[str, str]:
    """Store a knowledge chunk in the vector store.

    Args:
        db: Database instance (unused but kept for consistent signature).
        vector_store: VectorStore instance for semantic search.
        content: The text content of the knowledge chunk.
        subject_id: The subject this knowledge belongs to.
        source_url: URL of the source where this knowledge came from.
        source_score: Dependability score of the source (0.0 to 1.0).
        topic_path: Hierarchical path of the topic.
        confidence: Confidence level in this knowledge (0.0 to 1.0).
        contradictions: List of any known contradicting information.

    Returns:
        A confirmation dict with status, subject_id, and topic_path.
    """
    chunk = KnowledgeChunk(
        content=content,
        subject_id=subject_id,
        source_url=source_url,
        source_score=source_score,
        topic_path=topic_path,
        confidence=confidence,
        contradictions=contradictions or [],
        last_validated=datetime.now(),
    )
    vector_store.store_knowledge(chunk)
    return {"status": "stored", "subject_id": subject_id, "topic_path": topic_path}
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_knowledge.py::test_store_knowledge_stores_chunk_and_returns_confirmation -v`
Expected: PASS

**Step 7: Write failing test for vector_search**

Add to `tests/tools/test_knowledge.py`:

```python
from chiron.tools.knowledge import vector_search


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
```

**Step 8: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_knowledge.py::test_vector_search_returns_list_of_dicts -v`
Expected: FAIL with "cannot import name 'vector_search'"

**Step 9: Write vector_search implementation**

Add to `src/chiron/tools/knowledge.py`:

```python
def vector_search(
    db: Database,
    vector_store: VectorStore,
    *,
    query: str,
    subject_id: str,
    top_k: int = 5,
    min_confidence: float = 0.0,
) -> list[dict[str, Any]]:
    """Search for knowledge chunks by semantic similarity.

    Args:
        db: Database instance (unused but kept for consistent signature).
        vector_store: VectorStore instance for semantic search.
        query: The search query text.
        subject_id: Filter results to this subject only.
        top_k: Maximum number of results to return.
        min_confidence: Minimum confidence score for results.

    Returns:
        A list of matching knowledge chunks as dicts.
    """
    chunks = vector_store.search(
        query=query,
        subject_id=subject_id,
        top_k=top_k,
        min_confidence=min_confidence,
    )
    return [chunk.model_dump() for chunk in chunks]
```

**Step 10: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_knowledge.py -v`
Expected: PASS (2 tests)

**Step 11: Commit**

```bash
git add src/chiron/tools/ tests/tools/
git commit -m "feat(tools): add knowledge tool functions

Extract store_knowledge and vector_search from MCP server into
pure functions that can be called directly by agents."
```

---

## Task 2: Create Tool Functions - Subjects Module

**Files:**
- Create: `src/chiron/tools/subjects.py`
- Create: `tests/tools/test_subjects.py`
- Modify: `src/chiron/tools/__init__.py`

**Step 1: Write failing test for get_active_subject**

```python
# tests/tools/test_subjects.py
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_subjects.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write subjects module**

```python
# src/chiron/tools/subjects.py
"""Subject management tools."""

from typing import Any

from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore


def get_active_subject(
    db: Database,
    vector_store: VectorStore,
) -> str | None:
    """Get the currently active learning subject.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).

    Returns:
        The subject_id of the active subject, or None if not set.
    """
    return db.get_setting("active_subject")


def set_active_subject(
    db: Database,
    vector_store: VectorStore,
    *,
    subject_id: str,
) -> dict[str, str]:
    """Set the active learning subject.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        subject_id: The identifier of the subject to make active.

    Returns:
        A confirmation dict.
    """
    db.set_setting("active_subject", subject_id)
    return {"status": "success", "active_subject": subject_id}


def list_subjects(
    db: Database,
    vector_store: VectorStore,
) -> list[dict[str, Any]]:
    """List all subjects with learning goals.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).

    Returns:
        A list of all learning goals as dicts.
    """
    goals = db.list_subjects()
    return [goal.model_dump() for goal in goals]
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_subjects.py -v`
Expected: PASS

**Step 5: Add more tests for set_active_subject and list_subjects**

Add to `tests/tools/test_subjects.py`:

```python
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
```

**Step 6: Run all subject tests**

Run: `uv run pytest tests/tools/test_subjects.py -v`
Expected: PASS (4 tests)

**Step 7: Update __init__.py**

```python
# src/chiron/tools/__init__.py
"""Tool functions for Chiron agents."""

from chiron.tools.knowledge import store_knowledge, vector_search
from chiron.tools.subjects import get_active_subject, list_subjects, set_active_subject

__all__ = [
    "get_active_subject",
    "list_subjects",
    "set_active_subject",
    "store_knowledge",
    "vector_search",
]
```

**Step 8: Commit**

```bash
git add src/chiron/tools/ tests/tools/
git commit -m "feat(tools): add subject management tool functions"
```

---

## Task 3: Create Tool Functions - Learning Goals Module

**Files:**
- Create: `src/chiron/tools/learning_goals.py`
- Create: `tests/tools/test_learning_goals.py`
- Modify: `src/chiron/tools/__init__.py`

**Step 1: Write failing tests**

```python
# tests/tools/test_learning_goals.py
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_learning_goals.py -v`
Expected: FAIL

**Step 3: Write learning_goals module**

```python
# src/chiron/tools/learning_goals.py
"""Learning goal tools."""

from typing import Any

from chiron.models import LearningGoal
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore


def get_learning_goal(
    db: Database,
    vector_store: VectorStore,
    *,
    subject_id: str,
) -> dict[str, Any] | None:
    """Get the learning goal for a specific subject.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        subject_id: The identifier of the subject to retrieve.

    Returns:
        The learning goal as a dict, or None if not found.
    """
    goal = db.get_learning_goal(subject_id)
    return goal.model_dump() if goal else None


def save_learning_goal(
    db: Database,
    vector_store: VectorStore,
    *,
    subject_id: str,
    purpose_statement: str,
    target_depth: str = "practical",
) -> dict[str, Any]:
    """Save or update a learning goal for a subject.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        subject_id: The unique identifier for this subject.
        purpose_statement: Why the user wants to learn this subject.
        target_depth: Desired depth of learning.

    Returns:
        The saved learning goal as a dict with its ID.
    """
    goal = LearningGoal(
        subject_id=subject_id,
        purpose_statement=purpose_statement,
        target_depth=target_depth,
    )
    saved_id = db.save_learning_goal(goal)
    goal.id = saved_id
    return goal.model_dump()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_learning_goals.py -v`
Expected: PASS (3 tests)

**Step 5: Update __init__.py**

```python
# src/chiron/tools/__init__.py
"""Tool functions for Chiron agents."""

from chiron.tools.knowledge import store_knowledge, vector_search
from chiron.tools.learning_goals import get_learning_goal, save_learning_goal
from chiron.tools.subjects import get_active_subject, list_subjects, set_active_subject

__all__ = [
    "get_active_subject",
    "get_learning_goal",
    "list_subjects",
    "save_learning_goal",
    "set_active_subject",
    "store_knowledge",
    "vector_search",
]
```

**Step 6: Commit**

```bash
git add src/chiron/tools/ tests/tools/
git commit -m "feat(tools): add learning goal tool functions"
```

---

## Task 4: Create Tool Functions - Knowledge Nodes Module

**Files:**
- Create: `src/chiron/tools/knowledge_nodes.py`
- Create: `tests/tools/test_knowledge_nodes.py`
- Modify: `src/chiron/tools/__init__.py`

**Step 1: Write failing tests**

```python
# tests/tools/test_knowledge_nodes.py
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_knowledge_nodes.py -v`
Expected: FAIL

**Step 3: Write knowledge_nodes module**

```python
# src/chiron/tools/knowledge_nodes.py
"""Knowledge node tools."""

from typing import Any

from chiron.models import KnowledgeNode
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore


def get_knowledge_node(
    db: Database,
    vector_store: VectorStore,
    *,
    node_id: int,
) -> dict[str, Any] | None:
    """Get a specific knowledge node by its ID.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        node_id: The database ID of the knowledge node.

    Returns:
        The knowledge node as a dict, or None if not found.
    """
    node = db.get_knowledge_node(node_id)
    return node.model_dump() if node else None


def get_knowledge_tree(
    db: Database,
    vector_store: VectorStore,
    *,
    subject_id: str,
) -> list[dict[str, Any]]:
    """Get all knowledge nodes for a subject as a tree structure.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        subject_id: The subject identifier.

    Returns:
        A list of all knowledge nodes for the subject.
    """
    nodes = db.get_knowledge_tree(subject_id)
    return [node.model_dump() for node in nodes]


def save_knowledge_node(
    db: Database,
    vector_store: VectorStore,
    *,
    subject_id: str,
    title: str,
    description: str | None = None,
    parent_id: int | None = None,
    depth: int = 0,
    is_goal_critical: bool = False,
    prerequisites: list[int] | None = None,
    shared_with_subjects: list[str] | None = None,
) -> dict[str, Any]:
    """Save a new knowledge node or update an existing one.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        subject_id: The subject this node belongs to.
        title: The title/name of this knowledge node.
        description: Optional detailed description.
        parent_id: ID of the parent node (None for root nodes).
        depth: Depth in the tree (0 for root).
        is_goal_critical: Whether critical for the learning goal.
        prerequisites: List of node IDs that must be learned first.
        shared_with_subjects: List of other subjects sharing this node.

    Returns:
        The saved knowledge node as a dict with its ID.
    """
    node = KnowledgeNode(
        subject_id=subject_id,
        title=title,
        description=description,
        parent_id=parent_id,
        depth=depth,
        is_goal_critical=is_goal_critical,
        prerequisites=prerequisites or [],
        shared_with_subjects=shared_with_subjects or [],
    )
    saved_id = db.save_knowledge_node(node)
    node.id = saved_id
    return node.model_dump()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_knowledge_nodes.py -v`
Expected: PASS (4 tests)

**Step 5: Update __init__.py**

```python
# src/chiron/tools/__init__.py
"""Tool functions for Chiron agents."""

from chiron.tools.knowledge import store_knowledge, vector_search
from chiron.tools.knowledge_nodes import (
    get_knowledge_node,
    get_knowledge_tree,
    save_knowledge_node,
)
from chiron.tools.learning_goals import get_learning_goal, save_learning_goal
from chiron.tools.subjects import get_active_subject, list_subjects, set_active_subject

__all__ = [
    "get_active_subject",
    "get_knowledge_node",
    "get_knowledge_tree",
    "get_learning_goal",
    "list_subjects",
    "save_knowledge_node",
    "save_learning_goal",
    "set_active_subject",
    "store_knowledge",
    "vector_search",
]
```

**Step 6: Commit**

```bash
git add src/chiron/tools/ tests/tools/
git commit -m "feat(tools): add knowledge node tool functions"
```

---

## Task 5: Create Tool Functions - Progress Module

**Files:**
- Create: `src/chiron/tools/progress.py`
- Create: `tests/tools/test_progress_tools.py`
- Modify: `src/chiron/tools/__init__.py`

**Step 1: Write failing tests**

```python
# tests/tools/test_progress_tools.py
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_progress_tools.py -v`
Expected: FAIL

**Step 3: Write progress module**

```python
# src/chiron/tools/progress.py
"""User progress tools."""

from typing import Any

from chiron.models import AssessmentResponse
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore


def get_user_progress(
    db: Database,
    vector_store: VectorStore,
    *,
    node_id: int,
) -> dict[str, Any] | None:
    """Get the user's progress on a specific knowledge node.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        node_id: The ID of the knowledge node.

    Returns:
        The user's progress, or None if not recorded.
    """
    # TODO: Implement when Database.get_user_progress exists
    return None


def record_assessment(
    db: Database,
    vector_store: VectorStore,
    *,
    node_id: int,
    question_hash: str,
    response: str,
    correct: bool,
    lesson_id: int | None = None,
) -> dict[str, Any]:
    """Record a user's response to an assessment question.

    Args:
        db: Database instance.
        vector_store: VectorStore instance (unused).
        node_id: The ID of the knowledge node being assessed.
        question_hash: A hash identifying the specific question.
        response: The user's response text.
        correct: Whether the response was correct.
        lesson_id: Optional ID of the lesson.

    Returns:
        The recorded assessment as a dict.
    """
    assessment = AssessmentResponse(
        node_id=node_id,
        question_hash=question_hash,
        response=response,
        correct=correct,
        lesson_id=lesson_id,
    )
    # TODO: Save to database when method is implemented
    return assessment.model_dump()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_progress_tools.py -v`
Expected: PASS (2 tests)

**Step 5: Update __init__.py with all exports**

```python
# src/chiron/tools/__init__.py
"""Tool functions for Chiron agents."""

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
]
```

**Step 6: Commit**

```bash
git add src/chiron/tools/ tests/tools/
git commit -m "feat(tools): add progress tool functions"
```

---

## Task 6: Add Tool Registry and Definitions

**Files:**
- Modify: `src/chiron/tools/__init__.py`
- Create: `tests/tools/test_registry.py`

**Step 1: Write failing test for TOOL_REGISTRY**

```python
# tests/tools/test_registry.py
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_registry.py -v`
Expected: FAIL with "cannot import name 'TOOL_REGISTRY'"

**Step 3: Add registry and definitions to __init__.py**

```python
# src/chiron/tools/__init__.py
"""Tool functions for Chiron agents."""

import inspect
from typing import Any, Callable, get_type_hints

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
        if origin is type(None) or (hasattr(param_type, "__args__") and type(None) in getattr(param_type, "__args__", ())):
            # It's Optional, extract the inner type
            args = getattr(param_type, "__args__", ())
            param_type = next((a for a in args if a is not type(None)), str)
        else:
            # Required parameter (no default or keyword-only without default)
            if param.default is inspect.Parameter.empty and param.kind != inspect.Parameter.VAR_KEYWORD:
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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_registry.py -v`
Expected: PASS (3 tests)

**Step 5: Run all tool tests**

Run: `uv run pytest tests/tools/ -v`
Expected: PASS (all tests)

**Step 6: Commit**

```bash
git add src/chiron/tools/ tests/tools/
git commit -m "feat(tools): add tool registry and definition generator

TOOL_REGISTRY maps tool names to functions.
get_all_tool_definitions() generates Anthropic ToolParam format."
```

---

## Task 7: Update BaseAgent with Tool Execution Loop

**Files:**
- Modify: `src/chiron/agents/base.py`
- Modify: `tests/agents/test_base_agent.py`

**Step 1: Write failing test for tool execution**

Add to `tests/agents/test_base_agent.py`:

```python
import json


def test_base_agent_executes_tools_and_loops() -> None:
    """BaseAgent should execute tools and loop until no more tool calls."""
    config = AgentConfig(name="test", system_prompt="Test prompt")

    # Create tool executor mock
    tool_executor = MagicMock()
    tool_executor.return_value = {"status": "stored", "topic": "test"}

    # Create agent with tools
    tools = [{"name": "store_knowledge", "description": "Store", "input_schema": {"type": "object", "properties": {}}}]
    agent = BaseAgent(config, tools=tools, tool_executor=tool_executor)

    # Mock client
    mock_client = MagicMock()

    # First response: tool_use
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.id = "tool_123"
    mock_tool_use.name = "store_knowledge"
    mock_tool_use.input = {"content": "test fact"}
    mock_response1 = MagicMock()
    mock_response1.content = [mock_tool_use]

    # Second response: text only (no tools)
    mock_text = MagicMock()
    mock_text.type = "text"
    mock_text.text = "Done storing knowledge."
    mock_response2 = MagicMock()
    mock_response2.content = [mock_text]

    mock_client.messages.create.side_effect = [mock_response1, mock_response2]
    agent._client = mock_client

    result = agent.run("Store some knowledge")

    # Should have called API twice (tool call + final response)
    assert mock_client.messages.create.call_count == 2

    # Should have executed the tool
    tool_executor.assert_called_once_with("store_knowledge", {"content": "test fact"})

    # Should return final text
    assert result == "Done storing knowledge."


def test_base_agent_without_tools_works_as_before() -> None:
    """BaseAgent without tools should work exactly as before."""
    config = AgentConfig(name="test", system_prompt="Test prompt")
    agent = BaseAgent(config)  # No tools

    mock_client = MagicMock()
    mock_text = MagicMock()
    mock_text.text = "Hello!"
    mock_text.type = "text"
    mock_response = MagicMock()
    mock_response.content = [mock_text]
    mock_client.messages.create.return_value = mock_response
    agent._client = mock_client

    result = agent.run("Hi")

    assert result == "Hello!"
    mock_client.messages.create.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/agents/test_base_agent.py::test_base_agent_executes_tools_and_loops -v`
Expected: FAIL (BaseAgent doesn't accept tools parameter)

**Step 3: Update BaseAgent implementation**

```python
# src/chiron/agents/base.py
"""Base agent class for Claude Code agents."""

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from anthropic import Anthropic

if TYPE_CHECKING:
    from anthropic.types import MessageParam, ToolParam


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    system_prompt: str
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8192


@dataclass
class BaseAgent:
    """Base class for all Chiron agents."""

    config: AgentConfig
    tools: list["ToolParam"] | None = None
    tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None
    messages: list["MessageParam"] = field(default_factory=list)
    _client: Anthropic = field(default_factory=Anthropic, repr=False)

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation."""
        self.messages.append({
            "role": "user",
            "content": content,
        })

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the conversation."""
        self.messages.append({
            "role": "assistant",
            "content": content,
        })

    def _add_assistant_content(self, content: list[Any]) -> None:
        """Add raw assistant content blocks to the conversation."""
        self.messages.append({
            "role": "assistant",
            "content": content,
        })

    def clear_messages(self) -> None:
        """Clear the conversation history."""
        self.messages = []

    def _extract_text(self, response: Any) -> str:
        """Extract text content from response."""
        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        return "".join(text_parts)

    def run(self, initial_message: str) -> str:
        """Run the agent with an initial message.

        Args:
            initial_message: The first user message to send

        Returns:
            The agent's response
        """
        self.add_user_message(initial_message)

        while True:
            # Build API call kwargs
            kwargs: dict[str, Any] = {
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "system": self.config.system_prompt,
                "messages": self.messages,
            }
            if self.tools:
                kwargs["tools"] = self.tools

            response = self._client.messages.create(**kwargs)

            # Check for tool_use blocks
            tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]

            if not tool_uses:
                # No tool calls - extract text and return
                content = self._extract_text(response)
                self.add_assistant_message(content)
                return content

            # Add assistant's response (with tool_use blocks) to history
            self._add_assistant_content(list(response.content))

            # Execute each tool, collect results
            tool_results: list[dict[str, Any]] = []
            for tool_use in tool_uses:
                if self.tool_executor:
                    result = self.tool_executor(tool_use.name, tool_use.input)
                else:
                    result = {"error": "No tool executor configured"}

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result),
                })

            # Add tool results as user message
            self.messages.append({"role": "user", "content": tool_results})
            # Loop continues...

    def continue_conversation(self, user_message: str) -> str:
        """Continue the conversation with another message.

        Args:
            user_message: The next user message

        Returns:
            The agent's response
        """
        return self.run(user_message)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/agents/test_base_agent.py -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add src/chiron/agents/base.py tests/agents/test_base_agent.py
git commit -m "feat(agents): add tool execution loop to BaseAgent

BaseAgent now accepts tools and tool_executor parameters.
The run() method loops through tool calls until Claude stops
requesting tools, executing each tool and sending results back."
```

---

## Task 8: Update Agent Subclasses

**Files:**
- Modify: `src/chiron/agents/research.py`
- Modify: `src/chiron/agents/curriculum.py`
- Modify: `src/chiron/agents/lesson.py`
- Modify: `src/chiron/agents/assessment.py`
- Modify: `tests/agents/test_research_agent.py`

**Step 1: Update ResearchAgent**

```python
# src/chiron/agents/research.py
"""ResearchAgent for discovering and validating knowledge."""

from typing import Any, Callable

from chiron.agents.base import AgentConfig, BaseAgent

RESEARCH_AGENT_PROMPT = """\
You are the Research Agent for Chiron, an AI-powered adaptive learning platform.

Your role is to systematically research topics from the coverage map, discover
authoritative sources, validate facts, and store verified knowledge.

## Your Responsibilities

1. **Source Discovery**
   - Search for authoritative sources on each topic
   - Prioritize: academic papers > official documentation > expert blogs > general articles
   - Track source URLs and their types

2. **Fact Extraction**
   - Extract key facts, concepts, and relationships from sources
   - Note definitions, examples, and important details
   - Identify connections between concepts

3. **Source Validation**
   - Assign dependability scores to sources:
     - Academic/peer-reviewed: 0.9-1.0
     - Official documentation: 0.8-0.9
     - Expert blogs/books: 0.6-0.8
     - General articles: 0.4-0.6
     - User-generated content: 0.2-0.4

4. **Fact Validation**
   - For each fact, find corroborating sources
   - Flag contradictions when found
   - Calculate confidence: (corroborations × avg_source_score) / max(assertions, 1)
   - Only store facts with confidence > 0.7

5. **Knowledge Storage**
   Use the tools to store validated knowledge:
   - `store_knowledge` - Store validated facts with metadata
   - `vector_search` - Check for existing related knowledge
   - `get_knowledge_tree` - Understand current structure

## Output Format for Research Session

When researching a topic:

```
## Researching: [Topic Path]

### Sources Found
1. [URL] (type: official_docs, score: 0.85)
2. [URL] (type: academic, score: 0.92)
...

### Key Facts Extracted

**Fact 1:** [Statement]
- Sources: [1, 2]
- Confidence: 0.88
- Stored: ✓

**Fact 2:** [Statement]
- Sources: [1]
- Confidence: 0.72
- Stored: ✓

**Fact 3:** [Statement]
- Sources: [3]
- Contradicted by: [2]
- Confidence: 0.45
- Stored: ✗ (below threshold)

### Coverage Updates Needed
- New subtopic discovered: [Topic]
- Prerequisite identified: [Topic] requires [Other Topic]
- Suggest removing: [Topic] (not relevant to goal)
```

## Guidelines

- Be thorough but focused on the learning goal
- Quality over quantity - fewer high-confidence facts are better
- Always attribute sources
- Flag uncertainties explicitly
- Suggest coverage map updates when you discover new areas or irrelevant ones
"""


class ResearchAgent(BaseAgent):
    """Agent for researching and validating knowledge."""

    def __init__(
        self,
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        """Initialize the Research Agent.

        Args:
            tools: Tool definitions for Claude API.
            tool_executor: Function to execute tool calls.
        """
        config = AgentConfig(
            name="research",
            system_prompt=RESEARCH_AGENT_PROMPT,
        )
        super().__init__(config, tools=tools, tool_executor=tool_executor)

    def research_topic(self, topic_path: str, subject_id: str, context: str = "") -> str:
        """Research a specific topic.

        Args:
            topic_path: Hierarchical path like "Architecture/Pods"
            subject_id: The subject being researched
            context: Additional context about the learning goal

        Returns:
            Research findings and stored knowledge summary
        """
        prompt = f"""Research the following topic for the subject "{subject_id}":

Topic: {topic_path}

{f"Context: {context}" if context else ""}

Please:
1. Search for authoritative sources
2. Extract and validate key facts
3. Store validated knowledge using the tools
4. Report what you found and stored"""

        return self.run(prompt)
```

**Step 2: Update test_research_agent.py**

```python
# tests/agents/test_research_agent.py
"""Tests for ResearchAgent."""

from chiron.agents.research import RESEARCH_AGENT_PROMPT, ResearchAgent


def test_research_agent_has_system_prompt() -> None:
    """ResearchAgent should have a specialized system prompt."""
    assert RESEARCH_AGENT_PROMPT is not None
    assert "research" in RESEARCH_AGENT_PROMPT.lower()
    assert "source" in RESEARCH_AGENT_PROMPT.lower()


def test_research_agent_initialization() -> None:
    """ResearchAgent should initialize correctly."""
    agent = ResearchAgent()
    assert agent.config.name == "research"


def test_research_agent_initialization_with_tools() -> None:
    """ResearchAgent should accept tools and executor."""
    tools = [{"name": "test", "description": "Test", "input_schema": {"type": "object"}}]
    executor = lambda name, args: {"result": "ok"}

    agent = ResearchAgent(tools=tools, tool_executor=executor)

    assert agent.tools == tools
    assert agent.tool_executor is not None


def test_research_agent_prompt_includes_validation() -> None:
    """Research agent prompt should include source validation."""
    prompt_lower = RESEARCH_AGENT_PROMPT.lower()
    assert "validation" in prompt_lower or "validate" in prompt_lower
    assert "confidence" in prompt_lower
```

**Step 3: Read and update CurriculumAgent**

First read it:

```bash
cat src/chiron/agents/curriculum.py
```

Then update similarly to accept tools/tool_executor.

**Step 4: Read and update LessonAgent and AssessmentAgent**

Apply same pattern.

**Step 5: Run all agent tests**

Run: `uv run pytest tests/agents/ -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/chiron/agents/ tests/agents/
git commit -m "feat(agents): update all agents to accept tools

ResearchAgent, CurriculumAgent, LessonAgent, and AssessmentAgent
now accept tools and tool_executor parameters for in-process
tool execution."
```

---

## Task 9: Update Orchestrator to Wire Tools

**Files:**
- Modify: `src/chiron/orchestrator.py`
- Modify: `tests/test_orchestrator.py`

**Step 1: Write failing test**

Add to `tests/test_orchestrator.py`:

```python
def test_orchestrator_creates_tool_executor(orchestrator: Orchestrator) -> None:
    """Orchestrator should create tool executor bound to db/vector_store."""
    executor = orchestrator._create_tool_executor()

    assert callable(executor)


def test_orchestrator_research_agent_has_tools(orchestrator: Orchestrator) -> None:
    """research_agent should have tools configured."""
    agent = orchestrator.research_agent

    assert agent.tools is not None
    assert len(agent.tools) > 0
    assert agent.tool_executor is not None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_orchestrator.py::test_orchestrator_creates_tool_executor -v`
Expected: FAIL

**Step 3: Update Orchestrator**

```python
# src/chiron/orchestrator.py
"""Workflow orchestrator with state machine for Chiron learning sessions."""

from enum import Enum
from pathlib import Path
from typing import Any, Callable

from chiron.agents import (
    AssessmentAgent,
    CurriculumAgent,
    LessonAgent,
    ResearchAgent,
)
from chiron.models import LearningGoal
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore
from chiron.tools import TOOL_REGISTRY, get_all_tool_definitions


class WorkflowState(str, Enum):
    """States for the learning workflow state machine."""

    IDLE = "idle"
    INITIALIZING = "initializing"
    RESEARCHING = "researching"
    ASSESSING = "assessing"
    GENERATING_LESSON = "generating_lesson"
    DELIVERING_LESSON = "delivering_lesson"
    EXERCISING = "exercising"


class Orchestrator:
    """Orchestrates the learning workflow between agents."""

    def __init__(
        self,
        db: Database,
        vector_store: VectorStore,
        lessons_dir: Path,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            db: Database instance for structured data.
            vector_store: VectorStore instance for semantic search.
            lessons_dir: Directory for storing lesson files.
        """
        self.db = db
        self.vector_store = vector_store
        self.lessons_dir = lessons_dir

        self._state = WorkflowState.IDLE
        self._active_subject_id: str | None = None

        # Tool infrastructure
        self._tool_executor = self._create_tool_executor()
        self._tool_definitions = get_all_tool_definitions()

        # Lazy-loaded agents
        self._curriculum_agent: CurriculumAgent | None = None
        self._research_agent: ResearchAgent | None = None
        self._lesson_agent: LessonAgent | None = None
        self._assessment_agent: AssessmentAgent | None = None

    def _create_tool_executor(self) -> Callable[[str, dict[str, Any]], dict[str, Any]]:
        """Create tool executor bound to this orchestrator's db/vector_store."""

        def execute(name: str, args: dict[str, Any]) -> dict[str, Any]:
            func = TOOL_REGISTRY.get(name)
            if func is None:
                return {"error": f"Unknown tool: {name}"}
            try:
                return func(self.db, self.vector_store, **args)
            except Exception as e:
                return {"error": str(e)}

        return execute

    @property
    def state(self) -> WorkflowState:
        """Get the current workflow state."""
        return self._state

    @state.setter
    def state(self, value: WorkflowState) -> None:
        """Set the workflow state."""
        self._state = value

    @property
    def curriculum_agent(self) -> CurriculumAgent:
        """Get or create the curriculum agent."""
        if self._curriculum_agent is None:
            self._curriculum_agent = CurriculumAgent(
                tools=self._tool_definitions,
                tool_executor=self._tool_executor,
            )
        return self._curriculum_agent

    @property
    def research_agent(self) -> ResearchAgent:
        """Get or create the research agent."""
        if self._research_agent is None:
            self._research_agent = ResearchAgent(
                tools=self._tool_definitions,
                tool_executor=self._tool_executor,
            )
        return self._research_agent

    @property
    def lesson_agent(self) -> LessonAgent:
        """Get or create the lesson agent."""
        if self._lesson_agent is None:
            self._lesson_agent = LessonAgent(
                tools=self._tool_definitions,
                tool_executor=self._tool_executor,
            )
        return self._lesson_agent

    @property
    def assessment_agent(self) -> AssessmentAgent:
        """Get or create the assessment agent."""
        if self._assessment_agent is None:
            self._assessment_agent = AssessmentAgent(
                tools=self._tool_definitions,
                tool_executor=self._tool_executor,
            )
        return self._assessment_agent

    # ... rest of methods unchanged ...
```

**Step 4: Update test fixture to not pass mcp_server_url**

In `tests/test_orchestrator.py`, the fixture should just be:

```python
@pytest.fixture
def orchestrator(tmp_path: Path) -> Orchestrator:
    """Create test orchestrator."""
    db = Database(tmp_path / "test.db")
    db.initialize()
    vs = VectorStore(tmp_path / "chroma")
    return Orchestrator(db, vs, lessons_dir=tmp_path / "lessons")
```

**Step 5: Run tests**

Run: `uv run pytest tests/test_orchestrator.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/chiron/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): wire tools to agents

Orchestrator creates tool executor and passes tool definitions
to all agents. Removed mcp_server_url parameter."
```

---

## Task 10: Update MCP Server to Import from Tools

**Files:**
- Modify: `src/chiron/mcp_server/server.py`
- Modify: `tests/test_mcp_server.py`

**Step 1: Update MCP server to use tool functions**

```python
# src/chiron/mcp_server/server.py
"""FastMCP server implementation for Chiron."""

from typing import Any

from fastmcp import FastMCP

from chiron.storage import Database, VectorStore
from chiron.tools import (
    get_active_subject,
    get_knowledge_node,
    get_knowledge_tree,
    get_learning_goal,
    get_user_progress,
    list_subjects,
    record_assessment,
    save_knowledge_node,
    save_learning_goal,
    set_active_subject,
    store_knowledge,
    vector_search,
)


def create_mcp_server(db: Database, vector_store: VectorStore) -> FastMCP:
    """Create and configure a FastMCP server with Chiron tools.

    Args:
        db: The SQLite database instance for persistent storage.
        vector_store: The ChromaDB vector store for semantic search.

    Returns:
        A configured FastMCP server instance with all Chiron tools registered.
    """
    mcp = FastMCP("chiron")

    # Wrap each tool function with MCP decorator
    @mcp.tool
    def mcp_vector_search(
        query: str,
        subject_id: str,
        top_k: int = 5,
        min_confidence: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Search for knowledge chunks by semantic similarity."""
        return vector_search(
            db, vector_store,
            query=query,
            subject_id=subject_id,
            top_k=top_k,
            min_confidence=min_confidence,
        )

    @mcp.tool
    def mcp_store_knowledge(
        content: str,
        subject_id: str,
        source_url: str,
        source_score: float,
        topic_path: str,
        confidence: float,
        contradictions: list[str] | None = None,
    ) -> dict[str, str]:
        """Store a knowledge chunk in the vector store."""
        return store_knowledge(
            db, vector_store,
            content=content,
            subject_id=subject_id,
            source_url=source_url,
            source_score=source_score,
            topic_path=topic_path,
            confidence=confidence,
            contradictions=contradictions,
        )

    @mcp.tool
    def mcp_get_active_subject() -> str | None:
        """Get the currently active learning subject."""
        return get_active_subject(db, vector_store)

    @mcp.tool
    def mcp_set_active_subject(subject_id: str) -> dict[str, str]:
        """Set the active learning subject."""
        return set_active_subject(db, vector_store, subject_id=subject_id)

    @mcp.tool
    def mcp_list_subjects() -> list[dict[str, Any]]:
        """List all subjects with learning goals."""
        return list_subjects(db, vector_store)

    @mcp.tool
    def mcp_get_learning_goal(subject_id: str) -> dict[str, Any] | None:
        """Get the learning goal for a specific subject."""
        return get_learning_goal(db, vector_store, subject_id=subject_id)

    @mcp.tool
    def mcp_save_learning_goal(
        subject_id: str,
        purpose_statement: str,
        target_depth: str = "practical",
    ) -> dict[str, Any]:
        """Save or update a learning goal for a subject."""
        return save_learning_goal(
            db, vector_store,
            subject_id=subject_id,
            purpose_statement=purpose_statement,
            target_depth=target_depth,
        )

    @mcp.tool
    def mcp_get_knowledge_node(node_id: int) -> dict[str, Any] | None:
        """Get a specific knowledge node by its ID."""
        return get_knowledge_node(db, vector_store, node_id=node_id)

    @mcp.tool
    def mcp_get_knowledge_tree(subject_id: str) -> list[dict[str, Any]]:
        """Get all knowledge nodes for a subject as a tree structure."""
        return get_knowledge_tree(db, vector_store, subject_id=subject_id)

    @mcp.tool
    def mcp_save_knowledge_node(
        subject_id: str,
        title: str,
        description: str | None = None,
        parent_id: int | None = None,
        depth: int = 0,
        is_goal_critical: bool = False,
        prerequisites: list[int] | None = None,
        shared_with_subjects: list[str] | None = None,
    ) -> dict[str, Any]:
        """Save a new knowledge node or update an existing one."""
        return save_knowledge_node(
            db, vector_store,
            subject_id=subject_id,
            title=title,
            description=description,
            parent_id=parent_id,
            depth=depth,
            is_goal_critical=is_goal_critical,
            prerequisites=prerequisites,
            shared_with_subjects=shared_with_subjects,
        )

    @mcp.tool
    def mcp_get_user_progress(node_id: int) -> dict[str, Any] | None:
        """Get the user's progress on a specific knowledge node."""
        return get_user_progress(db, vector_store, node_id=node_id)

    @mcp.tool
    def mcp_record_assessment(
        node_id: int,
        question_hash: str,
        response: str,
        correct: bool,
        lesson_id: int | None = None,
    ) -> dict[str, Any]:
        """Record a user's response to an assessment question."""
        return record_assessment(
            db, vector_store,
            node_id=node_id,
            question_hash=question_hash,
            response=response,
            correct=correct,
            lesson_id=lesson_id,
        )

    return mcp
```

**Step 2: Run MCP server tests**

Run: `uv run pytest tests/test_mcp_server.py -v`
Expected: PASS

**Step 3: Run all tests**

Run: `uv run pytest`
Expected: PASS (all tests)

**Step 4: Commit**

```bash
git add src/chiron/mcp_server/server.py
git commit -m "refactor(mcp): use tool functions from tools module

MCP server now imports and wraps functions from chiron.tools,
eliminating code duplication."
```

---

## Task 11: Run Full Test Suite and Linting

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: PASS (all tests)

**Step 2: Run ruff linting**

Run: `uv run ruff check src/ tests/`
Expected: No errors (or fix any that appear)

**Step 3: Run mypy type checking**

Run: `uv run mypy src/chiron/`
Expected: No errors (or fix any that appear)

**Step 4: Final commit if any fixes**

```bash
git add -A
git commit -m "fix: address linting and type checking issues"
```

---

## Task 12: Merge Feature Branch

**Step 1: Check all tests pass one more time**

Run: `uv run pytest`
Expected: PASS

**Step 2: Review changes**

Run: `git log --oneline origin/main..HEAD`

**Step 3: Use finishing-a-development-branch skill**

Invoke: `superpowers:finishing-a-development-branch`

This will guide you through merging or creating a PR.
