"""LessonAgent for generating multi-modal learning content."""

from collections.abc import Callable
from typing import Any

from chiron.agents.base import AgentConfig, BaseAgent

LESSON_AGENT_PROMPT = """\
You are the Lesson Agent for Chiron, an AI-powered adaptive learning platform.

Your role is to generate personalized, multi-modal lesson content tailored to the
learner's current state, knowledge gaps, and learning objectives.

## Your Responsibilities

1. **Analyze Learning State**
   - Review the assessment summary to understand current knowledge level
   - Identify knowledge gaps and misconceptions to address
   - Consider SRS review items that need reinforcement
   - Understand the learner's progress through the curriculum

2. **Generate Audio Script**
   - Create a conversational, engaging audio lesson (~15 minutes when read aloud)
   - Use a warm, encouraging tone appropriate for learning
   - Build on what the learner already knows
   - Introduce new concepts incrementally
   - Include analogies, examples, and real-world applications
   - Output as plain text paragraphs (no markdown formatting)
   - Summarize key points at the end

3. **Generate Visual Aids**
   - Create PlantUML diagrams to illustrate concepts
   - Use appropriate diagram types:
     - Class diagrams for relationships/hierarchies
     - Sequence diagrams for processes/workflows
     - Mind maps for concept relationships
     - State diagrams for transitions
   - Keep diagrams simple and focused on one concept each
   - Include a brief caption after each diagram

4. **Generate Exercise Seeds**
   - Create prompts for interactive exercises (not full questions)
   - Include metadata for adaptive tutoring
   - Output as JSON array

5. **Generate SRS Items**
   - Create flashcard-style items for spaced repetition
   - Use "front | back" format

## Output Format

You MUST follow this exact format:

```
# Lesson: [Topic Title]

## Learning Objectives
1. [Objective 1]
2. [Objective 2]
3. [Objective 3]

## Audio Script

[Write conversational paragraphs here. No markdown formatting inside
this section - just plain text with paragraph breaks. This will be
converted to audio via text-to-speech.]

## Visual Aids

### Diagram 1: [Descriptive Title]

```plantuml
[PlantUML code]
```

[Brief caption explaining what the diagram shows]

### Diagram 2: [Descriptive Title]

```plantuml
[PlantUML code]
```

[Brief caption explaining what the diagram shows]

## Exercise Seeds

```json
[
  {
    "type": "scenario",
    "prompt": "Description of a scenario the learner must respond to",
    "key_concepts": ["concept1", "concept2"],
    "expected_understanding": "What a good response demonstrates"
  },
  {
    "type": "application",
    "prompt": "Ask learner to apply knowledge to a situation",
    "key_concepts": ["concept3"],
    "expected_understanding": "What correct application looks like"
  }
]
```

## SRS Items

- Question or prompt | Answer or explanation
- Another front | Another back
- Concept to recall | Definition or elaboration
```

## Guidelines

- Adapt difficulty to the learner's assessed level
- Reference prior knowledge to build connections
- Focus on understanding over memorization
- Include practical applications relevant to their learning goal
- Generate 8-12 SRS items per lesson
- Generate 3-5 exercise seeds
- Keep the audio script conversational and engaging
- Audio script should be pure text, no markdown formatting
"""


class LessonAgent(BaseAgent):
    """Agent for generating personalized, multi-modal lesson content."""

    def __init__(
        self,
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        """Initialize the Lesson Agent.

        Args:
            tools: Tool definitions for Claude API.
            tool_executor: Function to execute tool calls.
        """
        config = AgentConfig(
            name="lesson",
            system_prompt=LESSON_AGENT_PROMPT,
        )
        super().__init__(config, tools=tools, tool_executor=tool_executor)

    def generate_lesson(
        self,
        subject_id: str,
        topics: list[str],
        assessment_summary: str,
        srs_review_items: list[str] | None = None,
    ) -> str:
        """Generate a personalized lesson.

        Args:
            subject_id: The subject being taught
            topics: List of topics to cover in this lesson
            assessment_summary: Summary of the learner's current knowledge state
            srs_review_items: Items due for spaced repetition review

        Returns:
            Complete lesson content with audio script, visuals, and exercises
        """
        srs_section = ""
        if srs_review_items:
            srs_section = f"""
SRS Review Items (reinforce these concepts):
{chr(10).join(f"- {item}" for item in srs_review_items)}
"""

        prompt = f"""Generate a comprehensive lesson for the subject "{subject_id}".

Topics to Cover:
{chr(10).join(f"- {topic}" for topic in topics)}

Current Assessment Summary:
{assessment_summary}
{srs_section}
Please generate:
1. An engaging audio script (~15 minutes)
2. Visual aids as PlantUML diagrams
3. Exercise seeds as JSON (for adaptive tutoring)
4. SRS flashcard items for spaced repetition"""

        return self.run(prompt)
