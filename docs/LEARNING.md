# 🎓 Jarvis Academy — Learning Subsystem

> Design document for the future Jarvis Academy: the self-improving learning engine.

---

## Vision

**Jarvis Academy** is a planned subsystem that will enable Jarvis to **learn from user interactions**, adapt to individual preferences, and improve its accuracy over time — all while running locally and preserving user privacy.

The Academy turns Jarvis from a static tool executor into an **adaptive AI assistant** that gets smarter with every conversation.

```
┌─────────────────────────────────────────────────────────────┐
│                    Jarvis Academy                            │
│                                                             │
│  ┌───────────┐   ┌───────────┐   ┌────────────────────┐    │
│  │ Correction │   │ Pattern   │   │ Preference         │    │
│  │ Learning   │   │ Detection │   │ Modeling           │    │
│  │            │   │           │   │                    │    │
│  │ "Not that, │   │ Recurring │   │ Favorite apps,     │    │
│  │  this..."  │   │ commands  │   │ default paths,     │    │
│  │            │   │ → macros  │   │ preferred browser  │    │
│  └─────┬─────┘   └─────┬─────┘   └──────┬─────────────┘    │
│        │               │                │                   │
│        ▼               ▼                ▼                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Knowledge Store                         │   │
│  │  (Local SQLite / JSON — never leaves the machine)    │   │
│  └──────────────────────────────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            Adaptive Prompt Engine                    │   │
│  │  Injects learned preferences into system prompts    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Correction Learning

**What**: When the user corrects Jarvis, the system learns the correct mapping.

**Example Scenario**:

```
User: "open browser"
Jarvis: [opens Edge]
User: "no, use Chrome"
Jarvis: [opens Chrome]
Academy: Learned: "open browser" → prefer Chrome
```

**Implementation**:

```python
@dataclass
class Correction:
    """Records a user correction for learning."""

    original_input: str        # What the user said
    wrong_action: dict         # What Jarvis did wrong
    correct_action: dict       # What the user wanted
    timestamp: datetime
    confidence: float = 1.0    # Decays over time if not reinforced
```

**Storage**: Corrections are stored in a `corrections` table:

```sql
CREATE TABLE corrections (
    id          TEXT PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    user_input  TEXT NOT NULL,
    wrong_tool  TEXT NOT NULL,
    wrong_action TEXT NOT NULL,
    correct_tool TEXT NOT NULL,
    correct_action TEXT NOT NULL,
    correct_args TEXT NOT NULL DEFAULT '{}',
    confidence  REAL NOT NULL DEFAULT 1.0
);
```

**Retrieval**: Before planning, the Academy checks for relevant corrections and injects them as hints:

```
Previous corrections:
- When user says "open browser", prefer Chrome (not Edge)
- When user says "search", use Google (not Bing)
```

---

### 2. Pattern Detection

**What**: Detects recurring command sequences and offers to create macros.

**Example Scenario**:

```
Day 1: "open terminal, then open VS Code"
Day 2: "open terminal and VS Code"
Day 3: "open terminal, then VS Code"
Academy: Detected pattern! Create shortcut "morning setup"?
```

**Implementation**:

```python
@dataclass
class Pattern:
    """A detected recurring command pattern."""

    name: str                          # Auto-generated or user-defined
    trigger_phrases: list[str]         # Phrases that match this pattern
    tasks: list[dict]                  # Sequence of tasks to execute
    frequency: int                     # How many times detected
    last_seen: datetime
```

**Detection Algorithm**:

```
1. Track sequences of tasks per session
2. Hash task sequences (tool + action, ignoring args)
3. Count occurrences of each hash
4. If count >= threshold (e.g., 3):
   → Suggest creating a macro
   → Store as Pattern
```

**Macro Execution**:

```python
class MacroTool(BaseTool):
    """Executes learned multi-step macros."""

    @property
    def name(self) -> str:
        return "macro"

    def get_actions(self) -> dict[str, str]:
        # Dynamically built from stored patterns
        return {
            "morning_setup": "Opens terminal and VS Code",
            "research_mode": "Opens browser, GitHub, and StackOverflow",
        }

    def execute(self, action: str, args: dict) -> str:
        pattern = self._patterns[action]
        for task_def in pattern.tasks:
            # Delegate each step to the real tool
            ...
```

---

### 3. Preference Modeling

**What**: Builds a user profile based on observed behavior.

**Preference Categories**:

| Category | What It Tracks | Example |
|---|---|---|
| **App Preferences** | Preferred applications | "Browser = Chrome, Editor = VS Code" |
| **Path Preferences** | Commonly used directories | "Projects at C:\Users\ridha\Projects" |
| **Time Patterns** | Usage by time of day | "Morning: email+calendar, Evening: entertainment" |
| **Language Style** | How the user phrases requests | "Says 'fire up' to mean 'open'" |
| **Tool Frequency** | Most/least used tools | "Browser 60%, Windows 30%, File 10%" |

**Implementation**:

```python
@dataclass
class UserProfile:
    """Aggregated user preferences."""

    preferred_apps: dict[str, str] = field(default_factory=dict)
    # e.g., {"browser": "chrome", "editor": "vscode"}

    preferred_paths: dict[str, str] = field(default_factory=dict)
    # e.g., {"projects": "C:\\Users\\ridha\\Projects"}

    custom_aliases: dict[str, dict] = field(default_factory=dict)
    # e.g., {"fire up": {"tool": "windows", "action": "open_app"}}

    tool_usage: dict[str, int] = field(default_factory=dict)
    # e.g., {"browser": 150, "windows": 80, "file": 30}
```

---

### 4. Adaptive Prompt Engine

**What**: Injects learned knowledge into the LLM system prompt to improve accuracy.

**Current prompt** (static):
```
You are Jarvis, an AI operating system.
Available tools: ...
```

**Academy-enhanced prompt**:
```
You are Jarvis, an AI operating system.
Available tools: ...

User Preferences:
- Preferred browser: Chrome
- Preferred editor: VS Code
- Default project directory: C:\Users\ridha\Projects

Learned Corrections:
- "open browser" → use Chrome, not Edge
- "search something" → use search_google action

Available Macros:
- "morning setup" → opens Terminal + VS Code
- "research mode" → opens Chrome + GitHub + StackOverflow
```

---

## Architecture

### Module Structure

```
learning/
├── __init__.py
├── base_learner.py           # Abstract base class for learning modules
├── correction_learner.py     # Learns from user corrections
├── pattern_detector.py       # Detects recurring command patterns
├── preference_modeler.py     # Builds user preference profile
├── knowledge_store.py        # Persists learned knowledge (SQLite)
├── prompt_enhancer.py        # Injects knowledge into system prompts
└── models.py                 # Correction, Pattern, UserProfile dataclasses
```

### Integration Points

```
┌─────────┐     ┌──────────┐     ┌───────────────┐
│  Agent   │────▶│ Planner  │────▶│ PromptEnhancer│
│          │     │          │     │               │
│ (after   │     │ (before  │     │ Injects:      │
│ execution)│    │ LLM call)│     │ - corrections │
│          │     │          │     │ - preferences │
│ Feeds    │     │          │     │ - macros      │
│ results  │     │          │     │               │
│ to       │     │          │     │               │
│ Academy  │     │          │     │               │
└─────┬────┘     └──────────┘     └───────────────┘
      │
      ▼
┌───────────────────────────────────────┐
│            Jarvis Academy              │
│                                       │
│  ┌──────────────┐  ┌───────────────┐  │
│  │ Correction   │  │ Pattern       │  │
│  │ Learner      │  │ Detector      │  │
│  └──────┬───────┘  └──────┬────────┘  │
│         │                 │           │
│         ▼                 ▼           │
│  ┌──────────────────────────────┐     │
│  │      Knowledge Store        │     │
│  │      (SQLite tables)        │     │
│  └──────────────────────────────┘     │
└───────────────────────────────────────┘
```

---

## Privacy & Safety

The Academy is designed with the same privacy-first principles as the rest of Jarvis:

| Principle | Implementation |
|---|---|
| **100% Local** | All learning data stored in local SQLite |
| **No Telemetry** | Nothing is ever sent to external servers |
| **User Control** | Users can view, edit, and delete learned data |
| **Opt-In** | Learning can be enabled/disabled per category |
| **Transparency** | GUI shows what has been learned and why |
| **Reset** | One-click "forget everything" |

---

## GUI Integration

### Academy View (Planned)

A new sidebar page showing learned knowledge:

```
┌───────────────────────────────────────┐
│  🎓 Academy                           │
│                                       │
│  ── Corrections (3) ──────────────── │
│  ┌─────────────────────────────────┐  │
│  │ "open browser" → Chrome         │  │
│  │ Confidence: 95% | Used: 12x     │  │
│  │                      [Delete]   │  │
│  └─────────────────────────────────┘  │
│                                       │
│  ── Macros (2) ──────────────────── │
│  ┌─────────────────────────────────┐  │
│  │ 🚀 Morning Setup                │  │
│  │ Opens: Terminal, VS Code        │  │
│  │ Trigger: "morning setup"        │  │
│  │              [Edit] [Delete]    │  │
│  └─────────────────────────────────┘  │
│                                       │
│  ── Preferences ────────────────── │
│  ┌─────────────────────────────────┐  │
│  │ Browser: Chrome                 │  │
│  │ Editor: VS Code                 │  │
│  │ Projects: C:\Users\...\Projects │  │
│  └─────────────────────────────────┘  │
│                                       │
│  [Reset All Learning]                 │
└───────────────────────────────────────┘
```

---

## Roadmap

| Milestone | Features |
|---|---|
| **v1.0** | Knowledge store schema, basic correction learning |
| **v1.5** | Pattern detection, macro creation |
| **v2.0** | Full Academy with preference modeling, adaptive prompts, GUI |
| **v2.5** | Confidence decay, reinforcement learning, smart suggestions |

---

## Research References

The Academy design draws inspiration from:

- **User modeling** in recommender systems — preference profiles
- **Few-shot learning** — corrections as in-context examples
- **Sequence mining** — pattern detection in user behavior
- **Retrieval-Augmented Generation (RAG)** — injecting knowledge into prompts
- **Personalized language models** — adapting LLM behavior to individual users

---

## Contributing to Academy

The Academy is the most research-oriented part of Jarvis. Contributions welcome in:

1. **Correction detection heuristics** — How to identify when the user is correcting Jarvis
2. **Pattern mining algorithms** — Efficient detection of recurring command sequences
3. **Prompt injection formats** — How to most effectively inject knowledge into prompts
4. **Evaluation metrics** — How to measure if learning is actually improving accuracy
5. **Privacy preservation** — Techniques to learn without storing sensitive information

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.
