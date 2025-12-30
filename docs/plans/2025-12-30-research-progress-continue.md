# Continue: Research Progress Display Implementation

## Context

We just completed a brainstorming session and created a design document at `docs/plans/2025-12-30-research-progress-display.md`. The design is approved and ready for implementation.

## What to Do

Use the `superpowers:subagent-driven-development` skill to implement the research progress display feature.

### Design Summary

Add a Rich-based tree visualization during `chiron research start` that shows:
- Knowledge tree (up to 3 levels deep) with completion indicators per node
- Icons: 🔍 (active), ○ (not started), ◔ (partial), ◐ (in progress), ● (complete)
- Status line showing current activity ("Searching stanford.edu/...")
- Elapsed time display

Progress is database-driven - query vector store for fact counts after each research call.

### Implementation Tasks

1. **Add `count_facts_by_topic()` to VectorStore** (`src/chiron/storage/vector_store.py`)
   - Query ChromaDB to count facts per topic path for a subject
   - Return `dict[str, int]` mapping topic titles to fact counts

2. **Add `get_research_progress()` to Orchestrator** (`src/chiron/orchestrator.py`)
   - Combine knowledge tree nodes with fact counts from vector store
   - Return structure suitable for progress display

3. **Create `ResearchProgressDisplay` class** (`src/chiron/cli/progress.py`)
   - New file in new `cli/` subdirectory
   - `build_tree()` - Build Rich Tree from knowledge nodes with status icons
   - `get_node_status()` - Return icon based on fact count vs threshold (default 5)
   - `render()` - Combine tree + status line
   - `update_status()` - Update activity message

4. **Update `research_start()` in CLI** (`src/chiron/cli.py`)
   - Wrap research loop with `rich.live.Live` context
   - Use `ResearchProgressDisplay` to show/update progress
   - Refresh tree after each research call

5. **Add tests**
   - `tests/test_progress.py` - Unit tests for tree building and status icons
   - `tests/test_vector_store.py` - Add test for `count_facts_by_topic()`

### Files to Read First

- `docs/plans/2025-12-30-research-progress-display.md` - Full design document
- `src/chiron/storage/vector_store.py` - Existing vector store implementation
- `src/chiron/orchestrator.py` - Existing orchestrator with research methods
- `src/chiron/cli.py` - Current CLI with `research_start()` command

### Key Decisions Already Made

- Database-driven progress (query vector store for fact counts)
- Completion threshold: >= 5 facts with confidence > 0.7
- Tree depth limited to 3 levels
- Use Rich `Live`, `Tree`, `Spinner`, and `Text` components
- Tree is static during research calls, updates after each call completes
