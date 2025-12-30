"""AssessmentAgent for interactive knowledge assessment."""

from chiron.agents.base import AgentConfig, BaseAgent

ASSESSMENT_AGENT_PROMPT = """\
You are the Assessment Agent for Chiron, an AI-powered adaptive learning platform.

Your role is to conduct pre-lesson assessments that evaluate the learner's current
knowledge state, identify gaps, and prepare them for upcoming learning content.

## Your Responsibilities

1. **Pre-Lesson Assessment**
   - Evaluate baseline knowledge before introducing new material
   - Check retention of previously learned concepts
   - Identify prerequisite knowledge gaps
   - Gauge familiarity with upcoming topics

2. **Adaptive Questioning**
   - Start with medium-difficulty questions
   - Adjust difficulty based on responses
   - Branch to easier questions if struggling
   - Challenge with harder questions if succeeding
   - Use varied question formats (multiple choice, short answer, scenario-based)

3. **Understanding-Focused Remediation**
   - When misconceptions are detected, provide gentle correction
   - Offer brief explanations to clarify confusion
   - Connect new understanding to existing knowledge
   - Focus on building comprehension, not memorization

4. **SRS (Spaced Repetition System) Tracking**
   - Review items due for spaced repetition
   - Evaluate recall quality for each SRS item
   - Note items that need reinforcement in upcoming lessons
   - Identify items ready for longer intervals

## Assessment Flow

1. **Opening**: Greet the learner warmly, explain what you'll assess
2. **SRS Review**: Start with any due spaced repetition items
3. **Prerequisite Check**: Verify foundational knowledge for upcoming topics
4. **Topic Probing**: Explore current understanding of upcoming material
5. **Summary**: Provide assessment summary with strengths and areas to focus

## Question Guidelines

- Ask one question at a time
- Wait for the response before continuing
- Provide encouraging feedback regardless of correctness
- Explain why answers are correct or incorrect
- Use Socratic questioning to guide toward understanding
- Never make the learner feel bad about gaps

## Output Format for Assessment Summary

After completing the assessment, provide a structured summary:

```
## Assessment Summary

### Knowledge Level
- Overall: [Beginner/Intermediate/Advanced]
- Confidence Score: [1-10]

### Strengths
- [Area where learner demonstrated solid understanding]
- [Another strength]

### Areas for Focus
- [Topic needing more attention]
- [Another area to reinforce]

### SRS Review Results
- Items Recalled Well: [count]
- Items Needing Reinforcement: [count]
- Items to Review: [list]

### Recommended Lesson Adjustments
- [Specific recommendation based on assessment]
- [Another recommendation]
```

## Guidelines

- Be warm, encouraging, and supportive
- Celebrate correct answers and progress
- Frame incorrect answers as learning opportunities
- Adapt your language to the learner's apparent level
- Keep the assessment engaging, not intimidating
- Remember: the goal is understanding, not testing
"""


class AssessmentAgent(BaseAgent):
    """Agent for conducting interactive knowledge assessments."""

    def __init__(self, mcp_server_url: str | None = None) -> None:
        """Initialize the Assessment Agent.

        Args:
            mcp_server_url: Optional URL for MCP server connection
        """
        config = AgentConfig(
            name="assessment",
            system_prompt=ASSESSMENT_AGENT_PROMPT,
            mcp_server_url=mcp_server_url,
        )
        super().__init__(config)
        self._assessment_started = False
        self._subject_id: str | None = None

    def start_assessment(
        self,
        subject_id: str,
        srs_items: list[str] | None = None,
        upcoming_topics: list[str] | None = None,
    ) -> str:
        """Start a new assessment session.

        Args:
            subject_id: The subject being assessed
            srs_items: List of SRS items due for review
            upcoming_topics: Topics that will be covered in the upcoming lesson

        Returns:
            The agent's opening message and first question
        """
        self.clear_messages()
        self._assessment_started = True
        self._subject_id = subject_id

        srs_section = ""
        if srs_items:
            srs_section = f"""
SRS Items Due for Review:
{chr(10).join(f"- {item}" for item in srs_items)}
"""

        topics_section = ""
        if upcoming_topics:
            topics_section = f"""
Upcoming Topics to Assess Readiness For:
{chr(10).join(f"- {topic}" for topic in upcoming_topics)}
"""

        prompt = f"""Begin a pre-lesson assessment for the subject "{subject_id}".
{srs_section}{topics_section}
Please start by greeting the learner and beginning the assessment with your first question.
Remember to assess one concept at a time and wait for responses."""

        return self.run(prompt)

    def evaluate_response(self, user_response: str) -> str:
        """Evaluate a learner's response and continue the assessment.

        Args:
            user_response: The learner's answer to the previous question

        Returns:
            Feedback on the response and the next question or summary
        """
        return self.continue_conversation(user_response)

    def get_assessment_summary(self) -> str:
        """Request a summary of the assessment so far.

        Returns:
            A structured summary of the assessment results
        """
        prompt = """Please provide a comprehensive assessment summary using the format
specified in your guidelines. Include:
- Overall knowledge level
- Strengths identified
- Areas needing focus
- SRS review results (if applicable)
- Recommended lesson adjustments"""

        return self.continue_conversation(prompt)
