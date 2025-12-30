# Research Progress Display Design

## Goal

Show a live tree visualization of research progress during long-running research sessions, with completion indicators per node and current activity status.

## Architecture

Display a Rich-based tree showing the knowledge hierarchy (up to 3 levels deep) with:
- Completion status icons per node based on stored fact counts
- Highlighted active node being researched
- Status line showing current activity
- Elapsed time display

Progress is database-driven: query vector store for fact counts after each research call.

## Tree Display Format

```
Research Progress: peircean-thought

├── 🔍 Pragmatism [3/8 facts] ◐
│   ├── Origins [0/? facts] ○
│   ├── Maxim of Pragmatism [2/5 facts] ◔
│   └── Truth Theory [1/3 facts] ◔
├── Semiotics [0/? facts] ○
│   ├── Sign Categories
│   └── Interpretants
└── Logic [0/? facts] ○
    ├── Abduction
    └── Inquiry

Status: Searching stanford.edu/entries/peirce-logic...
Elapsed: 2m 34s
```

### Visual Indicators

| Icon | Meaning | Condition |
|------|---------|-----------|
| 🔍 | Currently researching | Active node |
| ○ | Not started | 0 facts |
| ◔ | Partial | 1-49% of threshold |
| ◐ | In progress | 50-99% of threshold |
| ● | Complete | >= threshold (default 5 facts with confidence > 0.7) |

## Data Flow

1. **Before each research call**: Query database for current knowledge tree structure and fact counts per node

2. **During research**: Show spinner on status line with topic being researched. Tree is static until call returns.

3. **After each research call**: Re-query to capture:
   - New nodes added via `store_knowledge` MCP tool
   - Updated fact counts
   - Structural changes (new subtopics, prerequisites)

4. **Live display**: Use `rich.live.Live` context manager to update tree in-place after each research call completes

### Completion Detection

- Query vector store: count facts where `metadata.topic_path` matches node
- Node is "complete" when it has >= N facts with confidence > 0.7 (configurable, default 5)
- Parent node completion = aggregate of children

## Implementation Components

### New Module: `src/chiron/cli/progress.py`

```python
class ResearchProgressDisplay:
    def __init__(self, console: Console, orchestrator: Orchestrator):
        ...

    def build_tree(self) -> rich.tree.Tree:
        """Query DB for nodes, vector store for fact counts."""
        ...

    def get_node_status(self, node_id: str) -> str:
        """Return status icon (○/◔/◐/●) based on fact count vs threshold."""
        ...

    def render(self) -> rich.console.RenderableType:
        """Combine tree + status line."""
        ...

    def update_status(self, message: str):
        """Update the 'Searching...' line."""
        ...
```

### Changes to Existing Code

1. **`cli.py`** - `research_start()` uses `Live` context with `ResearchProgressDisplay`

2. **`orchestrator.py`** - Add `get_research_progress(subject_id) -> dict[node_id, fact_count]`

3. **`vector_store.py`** - Add `count_facts_by_topic(subject_id) -> dict[str, int]`

### Rich Components Used

- `rich.tree.Tree` - Hierarchical display
- `rich.live.Live` - In-place updates
- `rich.spinner.Spinner` - Status line during research
- `rich.text.Text` - Styled node labels

## Testing

### Unit Tests (`tests/test_progress.py`)

- `test_build_tree_empty()` - No nodes returns minimal tree
- `test_build_tree_with_nodes()` - Correctly nests nodes by depth
- `test_node_status_icons()` - Returns correct icon for 0/partial/complete
- `test_tree_depth_limit()` - Only shows 3 levels even if tree is deeper

### Vector Store Tests (`tests/test_vector_store.py`)

- `test_count_facts_by_topic()` - Returns correct counts per topic path

### Integration Test

- `test_research_progress_updates()` - After research call, fact counts increase

### Manual Testing

- Run `chiron research start` on a real subject
- Verify tree updates after each research call
- Check spinner animates during long research
