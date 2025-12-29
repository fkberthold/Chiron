# Chiron: AI-Powered Adaptive Learning Platform

## Project Vision

Chiron is a comprehensive learning system designed to help users master any subject through research-validated content, adaptive daily lessons, and interactive assessment. Named after the wise centaur who mentored heroes, Chiron guides learners from their current knowledge state to mastery through purpose-driven curriculum and personalized instruction.

## Core Problems Addressed

- **Lack of credible sources**: Ensures learning from authoritative, well-vetted information
- **Inefficient learning pace**: Adapts to user's level and delivers focused daily lessons
- **Information retention**: Structured reinforcement with spaced repetition
- **Self-directed learning structure**: Provides curriculum structure and progression for independent learners

## Primary Design Goals

1. **Purpose-driven learning**: Learning depth driven by stated goals (e.g., "maintain K8S repos" vs "master Periclean thought")
2. **Source validation**: Consensus-based fact validation with source dependability scoring
3. **Adaptive delivery**: Interactive assessment-driven lesson generation
4. **Multi-modal lessons**: Audio (for listening), visual aids (PlantUML diagrams), programmed text exercises
5. **Understanding over memorization**: Remediation focuses on comprehension, not just recall
6. **Multi-subject support**: Learn multiple topics with cross-subject knowledge reuse

---

## Architecture Overview

### Three-Layer Architecture

**1. Orchestration Layer (Python Application)**
- Manages application state and workflow state machine
- Spawns and coordinates Claude Code agent sessions via Agent SDK
- Handles data persistence and retrieval
- Manages scheduling and session coordination

**2. Intelligence Layer (Claude Code Agents)**
Four specialized agents handle cognitive tasks:
- **CurriculumAgent**: Translates learning goals into coverage maps
- **ResearchAgent**: Discovers sources, validates facts, builds knowledge structure
- **LessonAgent**: Generates daily lessons (scripts, visuals, exercises)
- **AssessmentAgent**: Conducts interactive knowledge checks and adaptive tutoring

**3. Storage Layer (Local Services)**
- **ChromaDB**: Vector embeddings of researched content with metadata
- **SQLite**: Structured data (source scores, progress, lesson history)
- **File System**: Generated lessons (audio, PlantUML diagrams, reference docs)

### Communication Architecture

```
User ←→ Python CLI Orchestrator ←→ Claude Code Agents
                    ↓
            Custom MCP Server
                    ↓
        [ChromaDB | SQLite | File System]
```

Agents communicate with data storage through a custom MCP (Model Context Protocol) server that provides tools for querying and updating knowledge, progress, and lesson content.

---

## Learning Workflow

### Phase 1: Initial Setup & Research

**1. Goal Definition**
```bash
$ python chiron.py init
```
- User provides learning goal with purpose statement
- Examples:
  - "Learn Kubernetes well enough to maintain repos in my organization"
  - "Understand Periclean thought well enough to think in it myself"
  - "Use 'Pataphysics to enrich my creative practice"

**2. Curriculum Design**
- CurriculumAgent analyzes purpose, does shallow reconnaissance via WebSearch
- Identifies major topic areas and required depth
- Proposes initial coverage map (hierarchical outline of topics)
- **Iterative refinement**: User reviews and refines coverage map with agent

**3. Research Phase** (iterative cycles)
```bash
$ python chiron.py research --start
```

Research process:
- ResearchAgent works through coverage map topics systematically
- For each topic:
  - Searches for authoritative sources via WebSearch
  - Extracts factual claims and supporting evidence
  - Validates sources using consensus + dependability scoring
  - Stores validated facts in vector DB with source attribution

**Source Validation Algorithm**:
- Track source dependability scores (academic > official docs > expert blogs)
- For each fact: find multiple sources asserting it, flag contradictions
- Confidence score = f(corroborations, source_scores, contradictions)
- Only store claims with confidence > threshold

**Iterative Boundary Discovery**:
- As research progresses, ResearchAgent identifies:
  - Knowledge gaps in coverage map
  - Newly discovered prerequisite topics
  - Irrelevant areas to prune
- Updates coverage map, triggers new research cycles
- Continues until coverage map stabilizes and all areas meet confidence thresholds

**4. Skill Tree Generation**
```bash
$ python chiron.py tree --view
```
- Auto-generated from knowledge structure + stated goals
- Emphasizes path toward goals, de-emphasizes tangential knowledge
- Visual indicators: locked, available, in-progress, mastered, needs review

### Phase 2: Daily Learning

**1. Interactive Assessment** (5-10 minutes)
```bash
$ python chiron.py lesson
```
- AssessmentAgent session starts (interactive CLI conversation)
- Asks 3-5 questions:
  - Spaced repetition review from previous lessons
  - Knowledge gap identification
  - Readiness check for new material
- Analyzes responses in real-time, adjusts lesson plan

**2. Lesson Generation**
- LessonAgent generates based on assessment results:

**Audio Script** (15 minutes):
- Conversational narrative optimized for listening
- Story-driven where possible, concrete examples
- Paced for comprehension, natural spoken rhythm
- Saved as `.txt` for TTS rendering

**Visual Aids**:
- PlantUML diagrams/charts for complex concepts
- Generated as `.puml` files, rendered to PNG/SVG
- Wrapped in markdown document with explanations
- Exportable to PDF via pandoc for portable viewing

**Reinforcement Exercises**:
- Programmed text micro-lessons matched to content:
  - Branching scenarios (concept → test → remedial → advance)
  - Active recall problems (apply what you learned)
  - Spaced repetition questions from previous lessons
- Mix of exercise types appropriate to subject matter

**3. Audio Rendering**
- Python app renders audio from script:
  - **First choice**: Coqui TTS with GPU acceleration
    - Segment script for GPU memory management
    - Stitch together seamlessly
  - **Fallback**: Piper TTS (faster but more robotic)
  - **Last resort**: Export optimized script for Speechify on Android
- Audio saved to lesson directory

**4. Post-Lesson Reinforcement**
```bash
$ python chiron.py exercises
```
- CLI presents exercises interactively
- Captures responses, provides immediate feedback:
  - Simple answers validated locally
  - Complex answers evaluated by AssessmentAgent
- All responses stored with timestamps for SRS scheduling

**Understanding-Focused Remediation**:
When incorrect answer given:
- AssessmentAgent provides explanation from different angle
- May ask follow-up questions to diagnose misconception
- If pattern detected, triggers review lesson on prerequisites
- Also schedules earlier SRS review

**5. Progress Tracking**
- Updates skill tree in real-time
- Knowledge state based on assessment responses over time
- SRS scheduling: next review dates per concept
- Adaptive pacing: accelerate if strong retention, slow if gaps detected

---

## Multi-Subject Support

### Active Subject Model
```bash
$ python chiron.py use kubernetes    # Switch active subject
$ python chiron.py lesson             # Operates on kubernetes
$ python chiron.py use philosophy     # Switch to philosophy
```

### Cross-Subject Knowledge Reuse

**Architecture**: Shared infrastructure (MCP server, database), separate knowledge per subject by default

**Intelligent Linking**:
When starting new subject (e.g., Kubernetes), ResearchAgent:
1. Queries existing knowledge bases for potential overlaps
   - "Does user already know Linux, networking, containers?"
2. Treats existing knowledge as high-quality sources:
   - **Tag for sharing**: Mark concepts as prerequisites for multiple subjects
   - **Re-contextualize**: Add subject-specific context to existing concepts
   - **Build dependencies**: Link new concepts to existing mastered concepts
3. Updates skill trees to show cross-subject relationships
   - Linux skill tree shows concepts reused in K8S
   - K8S skill tree shows Linux prerequisites (potentially marked "already mastered")

**Result**: Build a personal knowledge graph that grows more valuable over time

---

## Data Architecture

### ChromaDB Collections

**knowledge_chunks**:
- Embedded content from research
- Metadata:
  ```json
  {
    "subject_id": "kubernetes",
    "source_url": "https://...",
    "source_score": 0.85,
    "topic_path": "Architecture/Pods/Lifecycle",
    "confidence": 0.92,
    "contradictions": [],
    "last_validated": "2025-01-15"
  }
  ```

**lesson_content**:
- Historical lessons for reference
- Metadata: date, topic, mastery_level_after, exercises_included

### SQLite Schema

```sql
-- Source tracking and validation
CREATE TABLE sources (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    type TEXT,  -- 'academic', 'official_docs', 'expert_blog', etc.
    base_dependability_score REAL,
    validation_count INTEGER DEFAULT 0,
    last_checked TIMESTAMP,
    notes TEXT
);

-- Knowledge structure (skill tree)
CREATE TABLE knowledge_nodes (
    id INTEGER PRIMARY KEY,
    subject_id TEXT NOT NULL,
    parent_id INTEGER REFERENCES knowledge_nodes(id),
    title TEXT NOT NULL,
    description TEXT,
    depth INTEGER,
    is_goal_critical BOOLEAN,
    prerequisites_json TEXT,  -- JSON array of node IDs
    shared_with_subjects TEXT  -- JSON array of other subject_ids
);

-- Learning progress
CREATE TABLE user_progress (
    node_id INTEGER PRIMARY KEY REFERENCES knowledge_nodes(id),
    mastery_level REAL,  -- 0.0 to 1.0
    last_assessed TIMESTAMP,
    next_review_date TIMESTAMP,
    assessment_history_json TEXT  -- JSON array of past scores
);

-- Lesson history
CREATE TABLE lessons (
    id INTEGER PRIMARY KEY,
    subject_id TEXT NOT NULL,
    date DATE NOT NULL,
    node_ids_covered TEXT,  -- JSON array
    audio_path TEXT,
    materials_path TEXT,
    duration_minutes INTEGER
);

-- Assessment responses (for SRS)
CREATE TABLE responses (
    id INTEGER PRIMARY KEY,
    lesson_id INTEGER REFERENCES lessons(id),
    node_id INTEGER REFERENCES knowledge_nodes(id),
    question_hash TEXT,
    response TEXT,
    correct BOOLEAN,
    timestamp TIMESTAMP,
    next_review TIMESTAMP
);

-- Learning goals
CREATE TABLE learning_goals (
    id INTEGER PRIMARY KEY,
    subject_id TEXT UNIQUE NOT NULL,
    purpose_statement TEXT NOT NULL,
    target_depth TEXT,
    created_date TIMESTAMP,
    research_complete BOOLEAN DEFAULT FALSE
);

-- Active subject tracking
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
-- Stores: active_subject
```

### File System Structure

```
/home/frank/Working/trainer/
├── docs/
│   └── plans/
│       └── 2025-12-29-chiron-design.md
├── knowledge_bases/
│   ├── kubernetes/
│   │   ├── research/
│   │   │   ├── coverage_map.json
│   │   │   └── sources.md
│   │   └── vector_db/  (ChromaDB persisted)
│   └── philosophy/
│       ├── research/
│       └── vector_db/
├── lessons/
│   ├── kubernetes/
│   │   └── 2025-01-15/
│   │       ├── lesson.md
│   │       ├── script.txt
│   │       ├── audio.mp3
│   │       ├── diagrams/
│   │       │   ├── pod-lifecycle.puml
│   │       │   └── pod-lifecycle.png
│   │       └── exercises.json
│   └── philosophy/
├── progress/
│   ├── kubernetes-skill-tree.json
│   ├── philosophy-skill-tree.json
│   └── current_state.json
├── chiron.db  (SQLite)
└── chiron.py  (Main orchestrator)
```

---

## Custom MCP Server

### Purpose
Provides tools for Claude Code agents to interact with local data stores.

### MCP Tools

**Knowledge Base Tools**:
- `vector_search(query, subject_id, collection, top_k)`: Semantic search
- `store_knowledge(content, metadata, subject_id, collection)`: Add validated content
- `get_knowledge_node(node_id)`: Retrieve specific concept
- `link_knowledge_across_subjects(node_id, target_subject_id)`: Create cross-subject link

**Source Management**:
- `record_source(url, type, initial_score)`: Add source to tracking
- `update_source_score(source_id, adjustment, reason)`: Modify dependability
- `get_source_info(source_id)`: Retrieve source details

**Progress Tracking**:
- `get_user_progress(node_ids)`: Retrieve mastery levels
- `record_assessment(node_id, response, correct)`: Store assessment result
- `get_srs_schedule(subject_id)`: Get upcoming review items

**Lesson Management**:
- `save_lesson(date, subject_id, content, metadata)`: Persist lesson
- `get_lesson_history(subject_id, count)`: Retrieve recent lessons
- `save_exercise_response(exercise_id, response)`: Record reinforcement activity

**Curriculum Operations**:
- `get_coverage_map(subject_id)`: Retrieve knowledge structure
- `update_coverage_map(subject_id, updates)`: Modify structure based on research
- `get_learning_goal(subject_id)`: Retrieve purpose statement

**Subject Management**:
- `get_active_subject()`: Get currently active subject
- `set_active_subject(subject_id)`: Switch active subject
- `list_subjects()`: Get all subjects with research status

### Server Architecture
- Python FastAPI or Flask app serving MCP protocol
- Agents connect to `localhost:PORT` when spawned
- All database operations go through MCP tools
- Handles data validation, consistency, transactions

---

## Agent Implementation Details

### Agent Session Management

**Session Spawning** (via Claude Agent SDK):
```python
from anthropic import Anthropic

# Example: Spawn CurriculumAgent
session = agent_sdk.create_session(
    agent_type="curriculum",
    system_prompt=CURRICULUM_AGENT_PROMPT,
    mcp_server_url="http://localhost:8000",
    tools=["web_search", "mcp_tools"]
)
```

**Context Provision**:
- Before spawning, Python loads relevant context from SQLite/ChromaDB
- Passes to agent as initial prompt context
- Agent queries MCP server for additional data during execution

### Agent Responsibilities

**CurriculumAgent**:
- Input: Learning goal statement
- Process:
  - WebSearch to explore domain boundaries
  - Draft initial coverage map
  - Iterate with user feedback
- Output: `coverage_map.json`, initial knowledge structure

**ResearchAgent** (long-running, multiple sessions):
- Input: Coverage map section to research
- Process:
  - WebSearch extensively for sources
  - Extract and validate claims
  - Store validated facts via MCP `store_knowledge`
  - Update source scores via MCP `update_source_score`
  - Identify and flag coverage map updates
- Output: Researched content in vector DB, updated coverage map

**LessonAgent**:
- Input: Assessment results, target concepts, progress state
- Process:
  - Query vector DB via MCP `vector_search` for relevant knowledge
  - Generate lesson script optimized for audio
  - Generate PlantUML specifications for visual aids
  - Generate programmed text exercises
- Output: Files written to lesson directory

**AssessmentAgent** (interactive):
- Input: Current knowledge state, SRS schedule
- Process:
  - Conduct interactive conversation
  - Ask questions from SRS schedule + readiness checks
  - Record responses via MCP `record_assessment`
  - Provide understanding-focused remediation
- Output: Assessment results, updated progress state

---

## Technical Implementation Stack

### Core Technologies

**Python Ecosystem**:
- FastAPI/Flask for MCP server
- SQLite for structured data
- ChromaDB for vector storage
- Claude Agent SDK for agent orchestration

**Audio Generation**:
1. Coqui TTS (GPU-accelerated, high quality)
   - Segment scripts for GPU memory limits
   - Stitch audio seamlessly
2. Piper TTS (fallback, CPU-based)
3. Optimized script export for Speechify (last resort)

**Visual Generation**:
- PlantUML for diagrams (`.puml` → PNG/SVG)
- Markdown documents with embedded diagrams
- Pandoc for PDF export (portable viewing)

**LLM Integration**:
- Claude Code via Agent SDK
- WebSearch built into Claude Code
- Custom MCP tools for data access

### Algorithms

**Source Validation**:
```python
def validate_claim(claim, sources):
    assertions = count_sources_asserting(claim, sources)
    contradictions = count_sources_contradicting(claim, sources)
    avg_source_score = mean([s.dependability_score for s in sources])

    confidence = (
        (assertions - contradictions) * avg_source_score
    ) / max(assertions, 1)

    return confidence > CONFIDENCE_THRESHOLD
```

**Spaced Repetition** (SM-2 variant):
```python
def calculate_next_review(correct, current_interval, ease_factor):
    if correct:
        next_interval = current_interval * ease_factor
        return next_interval, ease_factor
    else:
        next_interval = 1  # day
        new_ease = max(1.3, ease_factor - 0.2)
        return next_interval, new_ease
```

---

## Command Reference

### Initialization
```bash
$ python chiron.py init
# Interactive: Define learning goal and subject
```

### Research Management
```bash
$ python chiron.py research --start
# Start research phase (runs in background)

$ python chiron.py research --status
# Check research progress

$ python chiron.py research --pause
# Pause research

$ python chiron.py research --resume
# Resume research
```

### Daily Learning
```bash
$ python chiron.py lesson
# Start interactive assessment + lesson generation + delivery

$ python chiron.py exercises
# Work through post-lesson reinforcement exercises
```

### Progress & Visualization
```bash
$ python chiron.py tree --view
# View skill tree for active subject

$ python chiron.py progress
# Show detailed progress stats
```

### Subject Management
```bash
$ python chiron.py subjects
# List all subjects

$ python chiron.py use <subject_id>
# Switch active subject

$ python chiron.py link-subjects
# Run agent to identify cross-subject knowledge overlaps
```

---

## Future Enhancements (Out of Scope for V1)

### Advanced Features
- **Collaborative learning**: Share validated knowledge bases with others
- **Custom source whitelists**: Pre-approved sources per domain
- **Multi-language support**: Learn subjects in non-English languages
- **Voice interaction**: Speak answers during assessment instead of typing
- **Mobile app**: Native iOS/Android for on-the-go learning

### System Improvements
- **Distributed research**: Parallelize research across multiple machines
- **Advanced visualization**: Interactive skill tree with zooming, filtering
- **Learning analytics**: Deep insights into learning patterns and velocity
- **Export capabilities**: Generate comprehensive study guides from knowledge base

---

## Success Metrics

### Research Phase
- Coverage map completeness
- Source dependability scores
- Fact confidence levels
- Number of validated facts per topic

### Learning Phase
- Mastery progression velocity
- Retention rates (via SRS performance)
- Skill tree completion percentage
- Understanding depth (remediation frequency)

### System Quality
- Lesson generation time
- Audio quality ratings
- Exercise relevance scores
- Cross-subject knowledge reuse frequency

---

## Design Principles

1. **Purpose drives depth**: Learning goals determine research scope, not arbitrary levels
2. **Understanding over memorization**: Remediation focuses on comprehension
3. **Validated knowledge**: Only teach from consensus-backed, attributed sources
4. **Adaptive delivery**: Every lesson customized based on current state
5. **Multi-modal learning**: Combine audio, visual, and interactive elements
6. **Personal knowledge graph**: Subjects connect naturally where they overlap
7. **Respect time**: 15-minute lessons fit into daily life
8. **Learn and apply**: Immediate reinforcement after every lesson

---

## Conclusion

Chiron is designed to be a comprehensive, intelligent learning companion that combines rigorous research validation with adaptive, personalized instruction. By leveraging Claude Code's capabilities through specialized agents and maintaining local control of knowledge and progress data, it creates a system that grows more valuable over time as subjects interconnect and knowledge deepens.

The wise centaur guides you from novice to master, one validated fact and adaptive lesson at a time.
