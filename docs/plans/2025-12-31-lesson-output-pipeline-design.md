# Lesson Output Pipeline Design

## Overview

Transform lesson generation from raw text dump to structured file artifacts. After assessment, the system generates distinct deliverables: audio script, audio file, markdown with diagrams, and PDF.

## Current State

- `chiron lesson` runs assessment interactively
- User types `done` to generate lesson
- LessonAgent returns markdown with everything mixed together
- CLI just prints raw output to console

## Target State

After `done`, the system:
1. Parses LessonAgent output into sections
2. Generates artifacts in `data/lessons/{subject}/{YYYY-MM-DD}/`
3. Displays summary tree showing what was created

Output files:
- `script.txt` - Audio script for TTS
- `audio.mp3` - Generated audio (Coqui/Piper)
- `lesson.md` - Markdown with diagram image references
- `lesson.pdf` - PDF via Pandoc
- `diagrams/*.png` - Rendered PlantUML diagrams
- `exercises.json` - Exercise seeds for `chiron exercises`

---

## Section 1: Lesson Output Pipeline

When the user types `done` after assessment, the system:

1. **LessonAgent generates structured content** including:
   - Audio script (conversational narrative)
   - PlantUML diagram specifications
   - Exercise seeds (question prompts, expected approaches)
   - SRS flashcard items

2. **Parser extracts sections** from the markdown output:
   - `## Audio Script` → `script.txt`
   - `### Diagram N: Title` with plantuml blocks → `diagrams/`
   - `## Exercise Seeds` → `exercises.json`
   - `## SRS Items` → stored in database

3. **Content pipeline processes each**:
   - Audio: Coqui TTS (GPU) → Piper fallback → export fallback
   - Diagrams: PlantUML CLI renders `.puml` → `.png`
   - Markdown: Clean `lesson.md` with image references (not plantuml code)
   - PDF: Pandoc converts markdown → `lesson.pdf`

4. **CLI shows summary**:
   ```
   Lesson generated: data/lessons/card-game-war/2025-12-30/
     ├── script.txt (2,847 words)
     ├── audio.mp3 (14:32)
     ├── lesson.md
     ├── lesson.pdf
     ├── diagrams/
     │   ├── card-strength.png
     │   └── game-flow.png
     └── exercises.json (6 seeds)
   ```

---

## Section 2: LessonAgent Prompt Changes

Restructure output format for reliable parsing:

```markdown
# Lesson: [Topic Title]

## Learning Objectives
1. [Objective 1]
2. [Objective 2]

## Audio Script

[Full conversational script for TTS - no markdown formatting,
just natural spoken text with paragraph breaks]

## Visual Aids

### Diagram 1: [Title]
```plantuml
[PlantUML code]
```

[Brief caption explaining the diagram]

### Diagram 2: [Title]
```plantuml
[PlantUML code]
```

[Brief caption]

## Exercise Seeds

```json
[
  {
    "type": "scenario",
    "prompt": "You're playing War and both players flip a 7...",
    "key_concepts": ["war mechanic", "tie resolution"],
    "expected_understanding": "Player should explain the 3-down-1-up procedure"
  },
  {
    "type": "application",
    "prompt": "Your 6-year-old niece asks why Aces are low...",
    "key_concepts": ["card values", "teaching explanation"],
    "expected_understanding": "Age-appropriate explanation of game conventions"
  }
]
```

## SRS Items

- [Front] | [Back]
- [Front] | [Back]
```

Key changes:
- Audio script is pure text (no headers/formatting inside it)
- Exercise seeds are JSON for reliable parsing
- Each seed has metadata for the AssessmentAgent to use during branching

---

## Section 3: Content Parser Module

New module `src/chiron/content/parser.py`:

```python
@dataclass
class DiagramSpec:
    title: str
    puml_code: str
    caption: str

@dataclass
class ParsedLesson:
    title: str
    objectives: list[str]
    audio_script: str
    diagrams: list[DiagramSpec]
    exercise_seeds: list[dict]
    srs_items: list[tuple[str, str]]  # (front, back)
```

**Parsing approach:**
- Split on `## ` headers to get major sections
- Audio script: everything between `## Audio Script` and next `##`
- Diagrams: regex for `### Diagram N: Title` + plantuml fenced block + following paragraph
- Exercise seeds: extract JSON from fenced code block under `## Exercise Seeds`
- SRS items: parse `- [front] | [back]` lines under `## SRS Items`

**Error handling:**
- Missing sections → warning, continue with what's available
- Malformed JSON in exercises → log error, return empty list
- No diagrams → valid (some lessons may be audio-only)

---

## Section 4: Content Generation Pipeline

New module `src/chiron/content/pipeline.py`:

```python
def generate_lesson_artifacts(
    parsed: ParsedLesson,
    output_dir: Path,
    config: ChironConfig,
) -> LessonArtifacts:
```

**Step-by-step:**

1. **Create output directory**: `data/lessons/{subject}/{YYYY-MM-DD}/`

2. **Audio script** → `script.txt`
   - Write plain text file

3. **Audio generation** → `audio.mp3`
   - Try Coqui TTS (GPU) - segment script, generate, stitch
   - Fallback to Piper TTS (CPU)
   - Fallback to export-only (just keep script.txt)
   - Log which engine succeeded

4. **Diagrams** → `diagrams/*.png`
   - For each diagram: save `.puml`, run `plantuml -tpng`
   - Slug title for filename: "Card Strength" → `card-strength.puml`
   - If plantuml not available, keep `.puml` files only

5. **Lesson markdown** → `lesson.md`
   - Title + objectives
   - Diagram images with captions: `![Card Strength](diagrams/card-strength.png)`
   - No plantuml code blocks, no exercises, no SRS items

6. **PDF generation** → `lesson.pdf`
   - Run `pandoc lesson.md -o lesson.pdf`
   - If pandoc not available, skip with warning

7. **Exercise seeds** → `exercises.json`
   - Write parsed JSON directly

8. **SRS items** → database
   - Store via `db.add_srs_items(subject_id, items)`

**Return value:**
```python
@dataclass
class LessonArtifacts:
    output_dir: Path
    script_path: Path
    audio_path: Path | None  # None if TTS unavailable
    markdown_path: Path
    pdf_path: Path | None    # None if pandoc unavailable
    diagram_paths: list[Path]
    exercises_path: Path
    srs_items_added: int
```

---

## Section 5: CLI and Orchestrator Integration

**Changes to `orchestrator.py`:**

```python
def generate_lesson(self) -> LessonArtifacts:
    """Generate lesson and save all artifacts."""
    # ... existing code to get assessment_summary, topics ...

    raw_content = self.lesson_agent.generate_lesson(...)

    # Parse the structured output
    parsed = parse_lesson_content(raw_content)

    # Generate all artifacts
    output_dir = self.config.lessons_dir / subject_id / date.today().isoformat()
    artifacts = generate_lesson_artifacts(parsed, output_dir, self.config)

    # Store SRS items in database
    self.db.add_srs_items(subject_id, parsed.srs_items)

    return artifacts
```

**Changes to `cli.py`:**

```python
if user_input.lower().strip() == "done":
    console.print("\n[yellow]Generating personalized lesson...[/yellow]\n")

    with console.status("[bold green]Creating lesson materials..."):
        artifacts = orchestrator.generate_lesson()

    # Display summary
    tree = Tree(f"[bold]Lesson generated: {artifacts.output_dir}[/bold]")
    tree.add(f"[green]✓[/green] script.txt ({word_count(artifacts.script_path)} words)")
    if artifacts.audio_path:
        tree.add(f"[green]✓[/green] audio.mp3 ({duration(artifacts.audio_path)})")
    else:
        tree.add("[yellow]○[/yellow] audio.mp3 (TTS not available)")
    tree.add(f"[green]✓[/green] lesson.md")
    if artifacts.pdf_path:
        tree.add(f"[green]✓[/green] lesson.pdf")
    else:
        tree.add("[yellow]○[/yellow] lesson.pdf (pandoc not available)")
    if artifacts.diagram_paths:
        diagrams = tree.add("diagrams/")
        for p in artifacts.diagram_paths:
            diagrams.add(f"[green]✓[/green] {p.name}")
    tree.add(f"[green]✓[/green] exercises.json ({len(parsed.exercise_seeds)} seeds)")

    console.print(tree)
    console.print(f"\n[dim]Run 'chiron exercises' to practice.[/dim]")
    break
```

---

## Section 6: Dependencies and External Tools

**New Python dependencies:**

For Coqui TTS (optional, GPU):
```toml
# pyproject.toml [project.optional-dependencies]
tts = ["TTS>=0.22.0"]
```

For Piper TTS (optional, CPU fallback):
```toml
piper = ["piper-tts>=1.2.0"]
```

**External tools (not Python packages):**

- `plantuml` - Java-based, installed via package manager or JAR
- `pandoc` - Document converter, installed via package manager

**Detection approach in pipeline:**

```python
def check_available_tools() -> dict[str, bool]:
    return {
        "coqui": _try_import("TTS"),
        "piper": _try_import("piper"),
        "plantuml": shutil.which("plantuml") is not None,
        "pandoc": shutil.which("pandoc") is not None,
    }
```

**Devbox additions:**

```json
{
  "packages": [
    "plantuml",
    "pandoc"
  ]
}
```

The TTS libraries are Python-only and installed via `uv sync --extra tts` or `uv sync --extra piper`.

---

## Files to Create/Modify

### New Files
- `src/chiron/content/parser.py` - Parse LessonAgent output into sections
- `src/chiron/content/pipeline.py` - Orchestrate artifact generation
- `tests/test_parser.py` - Parser unit tests
- `tests/test_pipeline.py` - Pipeline unit tests

### Modified Files
- `src/chiron/agents/lesson.py` - Update prompt for new output format
- `src/chiron/orchestrator.py` - Return LessonArtifacts instead of string
- `src/chiron/cli.py` - Display artifact summary tree
- `src/chiron/content/audio.py` - Add Coqui/Piper TTS implementations
- `src/chiron/storage/database.py` - Add `add_srs_items()` method
- `pyproject.toml` - Add optional TTS dependencies
- `devbox.json` - Add plantuml, pandoc

---

## Implementation Order

1. Parser module (no external deps, easy to test)
2. Update LessonAgent prompt
3. Pipeline module (calls parser, existing audio/diagram helpers)
4. Database SRS method
5. Orchestrator changes
6. CLI changes
7. Add TTS implementations
8. Add devbox packages
