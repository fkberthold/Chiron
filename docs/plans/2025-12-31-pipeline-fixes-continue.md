# Continuation Prompt: Fix Pipeline Issues

## Context

The lesson output pipeline implementation (20 tasks) is complete and working. However, during manual testing, several issues were discovered that need to be addressed.

## Issues Found

### Issue 1: PlantUML Rendering Errors
**Symptom:** `PlantUML rendering failed for .../probability-distribution-of-game-lengths.puml: Error line 3`

**Root Cause:** The LessonAgent is generating invalid PlantUML code. The PlantUML command runs but returns an error because the diagram syntax is incorrect.

**Fix Needed:**
1. Improve the LessonAgent prompt to emphasize valid PlantUML syntax
2. Consider adding PlantUML validation before rendering
3. Gracefully handle PlantUML errors (currently it logs a warning but the .png files don't exist)

### Issue 2: Pandoc PDF Generation Requires LaTeX
**Symptom:** `pdflatex not found. Please select a different --pdf-engine or install pdflatex`

**Root Cause:** Pandoc needs a LaTeX engine (like pdflatex) to generate PDFs. We only added `pandoc` to devbox.json, not a LaTeX distribution.

**Fix Options:**
1. Add `texlive` or `texlive-basic` to devbox.json packages
2. OR use pandoc's HTML-to-PDF engine instead (requires wkhtmltopdf)
3. OR generate HTML output instead of PDF
4. Update `check_available_tools()` to also check for pdflatex

### Issue 3: Diagram PNGs Not Being Created
**Symptom:** The diagrams/ branch in the tree output shows no .png files even though .puml files exist

**Root Cause:** PlantUML rendering failed, so PNG files weren't created. The CLI only shows .png files in the tree.

**Fix Needed:**
1. Update CLI to show .puml files if .png rendering failed
2. Add better error messaging when diagram rendering fails
3. Consider showing partial success (e.g., "3 diagrams (1 rendered)")

### Issue 4: PDF References Missing Images
**Symptom:** `Could not fetch resource diagrams/game-flow-and-decision-points.png: replacing image with description`

**Root Cause:** Pandoc tries to embed the PNG images but they don't exist because PlantUML rendering failed.

**Fix Needed:**
1. Only attempt PDF generation if all referenced images exist
2. OR skip PDF generation when diagrams fail to render
3. OR use a fallback that doesn't require images

## Files to Modify

1. `src/chiron/agents/lesson.py` - Improve PlantUML syntax guidance in prompt
2. `src/chiron/content/pipeline.py` - Better error handling for diagram/PDF generation
3. `src/chiron/cli.py` - Show .puml files when .png not available
4. `devbox.json` - Add texlive-basic for PDF generation (optional)

## Recommended Approach

### Quick Fix (Minimal Changes)
1. Update CLI to show .puml files in the tree
2. Skip PDF generation when any diagram references fail to render
3. Add clearer warning messages

### Full Fix (More Robust)
1. Add PlantUML syntax validation
2. Add texlive to devbox for PDF generation
3. Track which diagrams rendered successfully
4. Only include successful diagrams in markdown/PDF

## Test Commands

```bash
# Run the full test suite
uv run pytest -v

# Test lesson generation manually
uv run chiron lesson
# Answer questions or type 'done'

# Check generated files
ls -la ~/.chiron/lessons/<subject>/<date>/
cat ~/.chiron/lessons/<subject>/<date>/script.txt
```

## Current State

- All 151 tests pass
- Linting is clean
- Pipeline works end-to-end
- These are enhancement issues, not blockers
