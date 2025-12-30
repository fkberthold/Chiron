"""Rich-based progress display for research sessions."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, TypedDict

from rich.console import Console, Group, RenderableType
from rich.text import Text
from rich.tree import Tree

if TYPE_CHECKING:
    from chiron.orchestrator import Orchestrator


class NodeDict(TypedDict):
    """Type for knowledge node dictionaries from orchestrator."""

    id: int
    title: str
    depth: int
    fact_count: int

# Completion threshold - facts needed to mark a topic as "complete"
COMPLETION_THRESHOLD = 5

# Maximum tree depth to display (0, 1, 2 = 3 levels)
MAX_DISPLAY_DEPTH = 2


class ResearchProgressDisplay:
    """Rich-based tree display for research progress."""

    def __init__(self, console: Console, orchestrator: Orchestrator) -> None:
        """Initialize the progress display.

        Args:
            console: Rich Console instance.
            orchestrator: Orchestrator to get progress data from.
        """
        self.console = console
        self.orchestrator = orchestrator
        self._status_message = ""
        self._start_time: float | None = None
        self._active_topic: str | None = None

    def build_tree(self, active_topic: str | None = None) -> Tree:
        """Build Rich Tree from knowledge nodes with status icons.

        Args:
            active_topic: Currently researching topic (gets magnifying glass icon).

        Returns:
            Rich Tree with progress indicators.
        """
        # Get progress data from orchestrator
        progress = self.orchestrator.get_research_progress()
        subject_id = progress["subject_id"]
        nodes = progress["nodes"]

        # Create root tree
        root = Tree(f"[bold]Research Progress: {subject_id}[/bold]")

        if not nodes:
            root.add("[dim]No topics yet[/dim]")
            return root

        # Build tree structure - organize nodes by depth
        # We need to build parent-child relationships
        node_trees: dict[int, Tree] = {}  # id -> Tree node

        # Cast nodes to proper type for type checking
        typed_nodes: list[NodeDict] = nodes

        # Build tree starting from depth 0
        for node in typed_nodes:
            if node["depth"] > MAX_DISPLAY_DEPTH:
                continue

            fact_count = node["fact_count"]
            title = node["title"]
            is_active = active_topic is not None and title == active_topic

            # Get status icon
            status_icon = self.get_node_status(fact_count, is_active)

            # Build label
            label = f"{status_icon} {title} [{fact_count} facts]"

            if node["depth"] == 0:
                # Add to root
                tree_node = root.add(label)
                node_trees[node["id"]] = tree_node
            else:
                # Find parent (the previous node with depth - 1)
                # Since nodes are ordered, we look backwards
                parent_tree = self._find_parent_tree(
                    node, typed_nodes, node_trees, root
                )
                if parent_tree is not None:
                    tree_node = parent_tree.add(label)
                    node_trees[node["id"]] = tree_node

        return root

    def _find_parent_tree(
        self,
        node: NodeDict,
        all_nodes: list[NodeDict],
        node_trees: dict[int, Tree],
        root: Tree,
    ) -> Tree | None:
        """Find the parent Tree node for a given node.

        Args:
            node: The node to find a parent for.
            all_nodes: All nodes from progress data.
            node_trees: Mapping of node IDs to Tree objects.
            root: The root Tree.

        Returns:
            Parent Tree or None if not found.
        """
        target_depth = node["depth"] - 1
        node_idx = next(
            (i for i, n in enumerate(all_nodes) if n["id"] == node["id"]),
            -1,
        )

        if node_idx <= 0:
            return root if target_depth < 0 else None

        # Look backwards for a node with the target depth
        for i in range(node_idx - 1, -1, -1):
            candidate = all_nodes[i]
            if candidate["depth"] == target_depth:
                parent_id = candidate["id"]
                if parent_id in node_trees:
                    return node_trees[parent_id]
                break
            elif candidate["depth"] < target_depth:
                # We've gone past possible parents
                break

        return root if target_depth == 0 else None

    def get_node_status(self, fact_count: int, is_active: bool = False) -> str:
        """Return status icon based on fact count vs threshold.

        Args:
            fact_count: Number of facts for this topic.
            is_active: Whether this topic is currently being researched.

        Returns:
            Status icon: magnifying glass (active), empty circle (not started),
            quarter circle (partial), half circle (in progress), full circle (complete)
        """
        if is_active:
            return "\U0001f50d"  # magnifying glass
        if fact_count == 0:
            return "\u25cb"  # empty circle
        if fact_count < COMPLETION_THRESHOLD * 0.5:
            return "\u25d4"  # quarter circle
        if fact_count < COMPLETION_THRESHOLD:
            return "\u25d0"  # half circle
        return "\u25cf"  # full circle

    def render(self) -> RenderableType:
        """Render the complete progress display.

        Returns:
            Renderable combining tree + status line + elapsed time.
        """
        tree = self.build_tree(self._active_topic)

        # Build status line
        status_text = Text()
        if self._status_message:
            status_text.append("\nStatus: ", style="bold")
            status_text.append(self._status_message, style="dim")

        # Build elapsed time line
        elapsed_text = Text()
        elapsed_text.append("\nElapsed: ", style="bold")
        elapsed_text.append(self.get_elapsed(), style="cyan")

        return Group(tree, status_text, elapsed_text)

    def update_status(self, message: str) -> None:
        """Update the status message.

        Args:
            message: New status message (e.g., "Searching stanford.edu/...").
        """
        self._status_message = message

    def set_active_topic(self, topic: str | None) -> None:
        """Set the currently active topic being researched.

        Args:
            topic: Topic name or None to clear.
        """
        self._active_topic = topic

    def start_timer(self) -> None:
        """Start the elapsed time timer."""
        self._start_time = time.time()

    def get_elapsed(self) -> str:
        """Get formatted elapsed time string.

        Returns:
            Formatted time like "2m 34s" or "0s" if not started.
        """
        if self._start_time is None:
            return "0s"

        elapsed = time.time() - self._start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"
