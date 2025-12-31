# Continue: Lesson Output Pipeline Implementation

## Context

We have a complete implementation plan at `docs/plans/2025-12-31-lesson-output-pipeline-impl.md` with 20 TDD tasks to transform lesson generation from raw text dump to structured file artifacts.

## What Was Done

1. Brainstormed and designed the lesson output pipeline
2. Created design doc: `docs/plans/2025-12-31-lesson-output-pipeline-design.md`
3. Created implementation plan: `docs/plans/2025-12-31-lesson-output-pipeline-impl.md`

## What Needs to Be Done

Execute the 20-task implementation plan using subagent-driven development.

## How to Continue

Use the `superpowers:subagent-driven-development` skill to execute the plan:

```
/superpowers:subagent-driven-development
```

The plan file is: `docs/plans/2025-12-31-lesson-output-pipeline-impl.md`

## Key Files

- **Plan**: `docs/plans/2025-12-31-lesson-output-pipeline-impl.md`
- **Design**: `docs/plans/2025-12-31-lesson-output-pipeline-design.md`
- **Parser to create**: `src/chiron/content/parser.py`
- **Pipeline to create**: `src/chiron/content/pipeline.py`
- **LessonAgent to modify**: `src/chiron/agents/lesson.py`
- **Orchestrator to modify**: `src/chiron/orchestrator.py`
- **CLI to modify**: `src/chiron/cli.py`
- **Database to modify**: `src/chiron/storage/database.py`

## Commands

```bash
# Run tests
uv run pytest -v

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/chiron/
```

## Goal

After implementation, `chiron lesson` will generate:
- `script.txt` - Audio script
- `audio.mp3` - TTS audio (when available)
- `lesson.md` - Markdown with diagram references
- `lesson.pdf` - PDF via Pandoc (when available)
- `diagrams/*.png` - Rendered PlantUML diagrams
- `exercises.json` - Exercise seeds for `chiron exercises`
