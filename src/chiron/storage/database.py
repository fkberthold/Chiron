"""SQLite database layer for Chiron."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from chiron.models import KnowledgeNode, LearningGoal, SubjectStatus


class Database:
    """SQLite database for persisting Chiron data."""

    def __init__(self, db_path: Path) -> None:
        """Initialize database with path.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Get a database connection as a context manager.

        Yields:
            A SQLite connection with row factory set to sqlite3.Row.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        """Create all required tables and indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Learning goals table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_id TEXT UNIQUE NOT NULL,
                    purpose_statement TEXT NOT NULL,
                    target_depth TEXT DEFAULT 'practical',
                    created_date TEXT NOT NULL,
                    research_complete INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'initializing'
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_learning_goals_subject
                ON learning_goals(subject_id)
            """)

            # Knowledge nodes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_id TEXT NOT NULL,
                    parent_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    depth INTEGER DEFAULT 0,
                    is_goal_critical INTEGER DEFAULT 0,
                    prerequisites TEXT DEFAULT '[]',
                    shared_with_subjects TEXT DEFAULT '[]',
                    FOREIGN KEY (parent_id) REFERENCES knowledge_nodes(id),
                    FOREIGN KEY (subject_id) REFERENCES learning_goals(subject_id)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_subject
                ON knowledge_nodes(subject_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_parent
                ON knowledge_nodes(parent_id)
            """)

            # User progress table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_progress (
                    node_id INTEGER PRIMARY KEY,
                    mastery_level REAL DEFAULT 0.0,
                    last_assessed TEXT,
                    next_review_date TEXT,
                    assessment_history TEXT DEFAULT '[]',
                    ease_factor REAL DEFAULT 2.5,
                    FOREIGN KEY (node_id) REFERENCES knowledge_nodes(id)
                )
            """)

            # Sources table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    source_type TEXT NOT NULL,
                    base_dependability_score REAL NOT NULL,
                    validation_count INTEGER DEFAULT 0,
                    last_checked TEXT,
                    notes TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sources_url
                ON sources(url)
            """)

            # Lessons table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    node_ids_covered TEXT DEFAULT '[]',
                    audio_path TEXT,
                    materials_path TEXT,
                    duration_minutes INTEGER,
                    FOREIGN KEY (subject_id) REFERENCES learning_goals(subject_id)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_lessons_subject
                ON lessons(subject_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_lessons_date
                ON lessons(date)
            """)

            # Assessment responses table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lesson_id INTEGER,
                    node_id INTEGER NOT NULL,
                    question_hash TEXT NOT NULL,
                    response TEXT NOT NULL,
                    correct INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    next_review TEXT NOT NULL,
                    FOREIGN KEY (lesson_id) REFERENCES lessons(id),
                    FOREIGN KEY (node_id) REFERENCES knowledge_nodes(id)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_responses_node
                ON responses(node_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_responses_next_review
                ON responses(next_review)
            """)

            # Settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

    def get_tables(self) -> list[str]:
        """Get list of all tables in the database.

        Returns:
            List of table names.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            return [row["name"] for row in cursor.fetchall()]

    def save_learning_goal(self, goal: LearningGoal) -> int:
        """Save a learning goal to the database.

        Args:
            goal: The learning goal to save.

        Returns:
            The ID of the saved goal.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO learning_goals
                    (subject_id, purpose_statement, target_depth, created_date,
                     research_complete, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(subject_id) DO UPDATE SET
                    purpose_statement = excluded.purpose_statement,
                    target_depth = excluded.target_depth,
                    research_complete = excluded.research_complete,
                    status = excluded.status
                """,
                (
                    goal.subject_id,
                    goal.purpose_statement,
                    goal.target_depth,
                    goal.created_date.isoformat(),
                    1 if goal.research_complete else 0,
                    goal.status.value,
                ),
            )
            return cursor.lastrowid or self._get_goal_id(conn, goal.subject_id)

    def _get_goal_id(self, conn: sqlite3.Connection, subject_id: str) -> int:
        """Get the ID of a learning goal by subject ID."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM learning_goals WHERE subject_id = ?", (subject_id,)
        )
        row = cursor.fetchone()
        return row["id"] if row else 0

    def get_learning_goal(self, subject_id: str) -> LearningGoal | None:
        """Get a learning goal by subject ID.

        Args:
            subject_id: The subject identifier.

        Returns:
            The learning goal or None if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM learning_goals WHERE subject_id = ?", (subject_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return LearningGoal(
                id=row["id"],
                subject_id=row["subject_id"],
                purpose_statement=row["purpose_statement"],
                target_depth=row["target_depth"],
                created_date=datetime.fromisoformat(row["created_date"]),
                research_complete=bool(row["research_complete"]),
                status=SubjectStatus(row["status"]),
            )

    def list_subjects(self) -> list[LearningGoal]:
        """List all subjects with learning goals.

        Returns:
            List of all learning goals.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM learning_goals ORDER BY created_date DESC")
            return [
                LearningGoal(
                    id=row["id"],
                    subject_id=row["subject_id"],
                    purpose_statement=row["purpose_statement"],
                    target_depth=row["target_depth"],
                    created_date=datetime.fromisoformat(row["created_date"]),
                    research_complete=bool(row["research_complete"]),
                    status=SubjectStatus(row["status"]),
                )
                for row in cursor.fetchall()
            ]

    def delete_subject(self, subject_id: str) -> bool:
        """Delete a subject and all associated data.

        Args:
            subject_id: The subject identifier to delete.

        Returns:
            True if the subject was deleted, False if it didn't exist.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if subject exists
            cursor.execute(
                "SELECT id FROM learning_goals WHERE subject_id = ?", (subject_id,)
            )
            if cursor.fetchone() is None:
                return False

            # Delete in order respecting foreign keys
            # First delete responses (references lessons and knowledge_nodes)
            cursor.execute(
                """
                DELETE FROM responses WHERE lesson_id IN (
                    SELECT id FROM lessons WHERE subject_id = ?
                )
                """,
                (subject_id,),
            )

            # Delete lessons
            cursor.execute("DELETE FROM lessons WHERE subject_id = ?", (subject_id,))

            # Delete knowledge nodes
            cursor.execute(
                "DELETE FROM knowledge_nodes WHERE subject_id = ?", (subject_id,)
            )

            # Delete the learning goal
            cursor.execute(
                "DELETE FROM learning_goals WHERE subject_id = ?", (subject_id,)
            )

            # Clear active subject if it was this one
            cursor.execute(
                "DELETE FROM settings WHERE key = 'active_subject' AND value = ?",
                (subject_id,),
            )

            conn.commit()
            return True

    def save_knowledge_node(self, node: KnowledgeNode) -> int:
        """Save a knowledge node to the database.

        Args:
            node: The knowledge node to save.

        Returns:
            The ID of the saved node.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if node.id is not None:
                # Update existing node
                cursor.execute(
                    """
                    UPDATE knowledge_nodes SET
                        subject_id = ?,
                        parent_id = ?,
                        title = ?,
                        description = ?,
                        depth = ?,
                        is_goal_critical = ?,
                        prerequisites = ?,
                        shared_with_subjects = ?
                    WHERE id = ?
                    """,
                    (
                        node.subject_id,
                        node.parent_id,
                        node.title,
                        node.description,
                        node.depth,
                        1 if node.is_goal_critical else 0,
                        json.dumps(node.prerequisites),
                        json.dumps(node.shared_with_subjects),
                        node.id,
                    ),
                )
                return node.id
            else:
                # Insert new node
                cursor.execute(
                    """
                    INSERT INTO knowledge_nodes
                        (subject_id, parent_id, title, description, depth,
                         is_goal_critical, prerequisites, shared_with_subjects)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node.subject_id,
                        node.parent_id,
                        node.title,
                        node.description,
                        node.depth,
                        1 if node.is_goal_critical else 0,
                        json.dumps(node.prerequisites),
                        json.dumps(node.shared_with_subjects),
                    ),
                )
                return cursor.lastrowid or 0

    def get_knowledge_node(self, node_id: int) -> KnowledgeNode | None:
        """Get a knowledge node by ID.

        Args:
            node_id: The node identifier.

        Returns:
            The knowledge node or None if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM knowledge_nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return KnowledgeNode(
                id=row["id"],
                subject_id=row["subject_id"],
                parent_id=row["parent_id"],
                title=row["title"],
                description=row["description"],
                depth=row["depth"],
                is_goal_critical=bool(row["is_goal_critical"]),
                prerequisites=json.loads(row["prerequisites"]),
                shared_with_subjects=json.loads(row["shared_with_subjects"]),
            )

    def get_knowledge_tree(self, subject_id: str) -> list[KnowledgeNode]:
        """Get all knowledge nodes for a subject.

        Args:
            subject_id: The subject identifier.

        Returns:
            List of all knowledge nodes for the subject.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM knowledge_nodes WHERE subject_id = ? ORDER BY depth, id",
                (subject_id,),
            )
            return [
                KnowledgeNode(
                    id=row["id"],
                    subject_id=row["subject_id"],
                    parent_id=row["parent_id"],
                    title=row["title"],
                    description=row["description"],
                    depth=row["depth"],
                    is_goal_critical=bool(row["is_goal_critical"]),
                    prerequisites=json.loads(row["prerequisites"]),
                    shared_with_subjects=json.loads(row["shared_with_subjects"]),
                )
                for row in cursor.fetchall()
            ]

    def get_setting(self, key: str) -> str | None:
        """Get a setting value by key.

        Args:
            key: The setting key.

        Returns:
            The setting value or None if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        """Set a setting value.

        Args:
            key: The setting key.
            value: The setting value.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
