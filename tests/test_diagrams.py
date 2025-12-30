"""Tests for diagram generation."""

from pathlib import Path

from chiron.content.diagrams import extract_plantuml_blocks, save_diagram


def test_extract_plantuml_blocks() -> None:
    """Should extract PlantUML blocks from markdown."""
    content = """
# Lesson

Some text here.

```plantuml
@startuml
Alice -> Bob: Hello
@enduml
```

More text.

```plantuml
@startuml
Bob -> Alice: Hi
@enduml
```
"""
    blocks = extract_plantuml_blocks(content)
    assert len(blocks) == 2
    assert "Alice -> Bob" in blocks[0]
    assert "Bob -> Alice" in blocks[1]


def test_extract_no_blocks() -> None:
    """Should return empty list when no PlantUML blocks."""
    content = "Just regular markdown without diagrams."
    blocks = extract_plantuml_blocks(content)
    assert blocks == []


def test_save_diagram(tmp_path: Path) -> None:
    """Should save PlantUML source to file."""
    puml_content = """@startuml
Alice -> Bob: Hello
@enduml"""

    output_path = save_diagram(puml_content, tmp_path, "test-diagram")

    assert output_path.exists()
    assert output_path.suffix == ".puml"
    assert output_path.read_text() == puml_content
