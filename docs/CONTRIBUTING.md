# 🤝 Contributing Guide

> Guidelines for contributing to the Jarvis project.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Coding Standards](#coding-standards)
- [Folder Conventions](#folder-conventions)
- [Naming Conventions](#naming-conventions)
- [Architecture Rules](#architecture-rules)
- [SOLID Principles](#solid-principles)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)

---

## Getting Started

### 1. Fork & Clone

```bash
git clone https://github.com/your-username/Jarvis.git
cd Jarvis
```

### 2. Set Up Environment

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run the Application

```bash
python main.py         # GUI mode
python main.py --cli   # CLI mode
```

### 4. Create a Branch

```bash
git checkout -b feature/my-feature
# or
git checkout -b fix/my-bugfix
```

---

## Coding Standards

### Python Version

- **Python 3.11+** — Use modern syntax (type unions `X | Y`, `match` statements)

### Code Formatter

- **Line length**: 79 characters (PEP 8)
- **Indentation**: 4 spaces, never tabs
- **Quotes**: Double quotes `"..."` for strings
- **Trailing commas**: Always use in multi-line sequences

### Type Hints

- **All** public functions must have full type annotations
- **All** class attributes must be typed
- Use `from __future__ import annotations` for forward references
- Use `TYPE_CHECKING` guard for import-only types:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent import Agent
```

### Docstrings

Every module, class, and public method must have a docstring:

**Module docstring** (top of file):
```python
"""
Module name — one-line description.

Longer description explaining what this module does,
what it doesn't do, and how it relates to other modules.
"""
```

**Class docstring**:
```python
class MyClass:
    """One-line description.

    Optional longer description.

    Args:
        param: Description of constructor parameter.
    """
```

**Method docstring**:
```python
def my_method(self, arg: str) -> str:
    """One-line description.

    Args:
        arg: Description.

    Returns:
        Description of return value.

    Raises:
        SomeError: When this happens.
    """
```

### Imports

Order (with blank lines between groups):
1. Standard library
2. Third-party packages
3. Local modules

```python
import logging
import os

from PySide6.QtCore import Qt

from core.exceptions import JarvisError
from core.task import Task
```

### Logging

- Use `logging.getLogger(__name__)` at module level
- Never use `print()` for debugging
- Log levels:
  - `DEBUG` — Verbose internal state
  - `INFO` — Significant pipeline events
  - `WARNING` — Recoverable issues
  - `ERROR` — Failures that affect results

```python
logger = logging.getLogger(__name__)
logger.info("Processing: %s", user_input)
```

---

## Folder Conventions

### Directory Structure Rules

| Directory | Contents | Rules |
|---|---|---|
| `config/` | Configuration management | One config class, one loader function |
| `core/` | Agent pipeline | One class per file, no GUI imports |
| `tools/` | Tool plugins | Must implement `BaseTool`, self-contained |
| `memory/` | Memory subsystem | Must implement `BaseMemory` for backends |
| `gui/` | PySide6 GUI | No core logic, calls `Agent.run()` only |
| `gui/themes/` | Theme definitions | One preset per file, use `Theme` dataclass |
| `gui/views/` | Stacked page views | One view per file, self-contained |
| `gui/widgets/` | Reusable components | No business logic, purely display |
| `docs/` | Documentation | Markdown files only |

### File Size Guidelines

- **Target**: Under 200 lines per file
- **Maximum**: 400 lines (refactor if exceeded)
- **Exception**: `theme.py` QSS builder (layout-driven, hard to split)

---

## Naming Conventions

### Files

| Type | Convention | Example |
|---|---|---|
| Module | `snake_case.py` | `memory_manager.py` |
| Package init | `__init__.py` | `__init__.py` |
| Documentation | `UPPER_CASE.md` | `ARCHITECTURE.md` |

### Classes

| Type | Convention | Example |
|---|---|---|
| Regular class | `PascalCase` | `MemoryManager` |
| Abstract class | `PascalCase` with `Base` prefix | `BaseMemory`, `BaseTool` |
| Dataclass | `PascalCase` | `JarvisConfig`, `MemoryEntry` |
| Enum | `PascalCase` | `TaskStatus` |
| Exception | `PascalCase` ending in `Error` | `ValidationError` |
| Private class | `_PascalCase` | `_AgentWorker`, `_Dot` |

### Functions & Methods

| Type | Convention | Example |
|---|---|---|
| Public function | `snake_case` | `load_config()` |
| Public method | `snake_case` | `agent.run()` |
| Private method | `_snake_case` | `_build_system_prompt()` |
| Static method | `snake_case` | `_error_task()` |
| Signal handler | `_on_event_name` | `_on_page_changed()` |

### Variables

| Type | Convention | Example |
|---|---|---|
| Local variable | `snake_case` | `user_input` |
| Instance attr | `self._snake_case` | `self._registry` |
| Constants | `UPPER_SNAKE_CASE` | `_MAX_CONTEXT_ENTRIES` |
| Module-level private | `_UPPER_SNAKE_CASE` | `_SYSTEM_PROMPT_TEMPLATE` |

### Qt-Specific

| Type | Convention | Example |
|---|---|---|
| Object name | `camelCase` | `setObjectName("headerFrame")` |
| CSS property class | `camelCase` | `setProperty("class", "viewTitle")` |
| Signal | `snake_case` | `page_changed = Signal(str)` |

---

## Architecture Rules

### Dependency Direction

Dependencies flow **downward and inward**. Never create upward dependencies.

```
GUI → Core → Tools
       ↓
     Memory
       ↓
    Config
```

### Rules

1. **`core/` never imports from `gui/`** — The pipeline must work without a GUI
2. **`tools/` never imports from `gui/`** — Tools are headless
3. **`memory/` never imports from `gui/`** — Memory is headless
4. **`gui/` imports from `core/` via `Agent.run()` only** — No reaching into internals
5. **`main.py` is the sole composition root** — All dependency wiring happens here
6. **No module instantiates its own dependencies** — Constructor injection everywhere

### Tool Rules

1. Every tool **must** implement `BaseTool`
2. Tools communicate with the framework **only** through `BaseTool` interface
3. Tools must be **self-contained** — no tool depends on another tool
4. Tools must raise `ExecutionError` for all failures
5. Tool actions use the **dispatch pattern** (dict of handler functions)

### Memory Rules

1. Every backend **must** implement `BaseMemory`
2. Memory is **always optional** — `Agent` works with `memory=None`
3. Memory errors **never** crash the pipeline
4. Memory operations log warnings on failure, never raise to the caller (except `clear()` and initialization)

### GUI Rules

1. **No business logic in GUI** — The GUI calls `Agent.run()` and displays results
2. **Background threads for Agent** — Never call `Agent.run()` on the main thread
3. **Signals for cross-component communication** — No direct method calls between unrelated widgets
4. **Theme tokens for all colors** — No hardcoded colors in widgets
5. **Object names for QSS targeting** — Every styled widget has `setObjectName()`

---

## SOLID Principles

The Jarvis codebase strictly follows SOLID principles. Here's how they apply:

### S — Single Responsibility Principle

> Every module has exactly one reason to change.

| ✅ Correct | ❌ Wrong |
|---|---|
| `parser.py` only extracts JSON | Parser that also normalizes aliases |
| `executor.py` only runs tasks | Executor that also validates tasks |
| `llm.py` only talks to Ollama | LLM client that also parses responses |

### O — Open/Closed Principle

> Open for extension, closed for modification.

| Extension Point | How to Extend | Core Changes |
|---|---|---|
| New tool | Implement `BaseTool`, call `registry.register()` | Zero |
| New memory backend | Implement `BaseMemory` | Zero |
| New theme | Create new `Theme(...)` instance | Zero |
| New GUI view | Add widget to `MainWindow._stack` | Minimal |

### L — Liskov Substitution Principle

> Subclasses must be substitutable for their base classes.

All `BaseTool` implementations can be used interchangeably:
- `WindowsTool`, `BrowserTool`, `FileTool` all satisfy `BaseTool`
- `SqliteMemory` satisfies `BaseMemory`
- Any new implementation must honor the same contracts

### I — Interface Segregation Principle

> Clients should not depend on interfaces they don't use.

- `BaseTool` has exactly 4 members — nothing unnecessary
- `BaseMemory` has exactly 4 methods — store, get, search, clear
- `Agent` receives only what it needs (Planner, Validator, Executor, Memory)

### D — Dependency Inversion Principle

> Depend on abstractions, not concrete implementations.

| High-Level Module | Depends On | Not On |
|---|---|---|
| `Agent` | `Planner`, `Validator`, `Executor` | `LLMClient`, tools directly |
| `MemoryManager` | `BaseMemory` (abstract) | `SqliteMemory` (concrete) |
| `Executor` | `Registry` | Individual tools |
| `Planner` | `LLMClient`, `Registry` | Ollama SDK directly |

---

## Pull Request Process

### Branch Naming

```
feature/short-description    # New features
fix/short-description        # Bug fixes
refactor/short-description   # Code improvements
docs/short-description       # Documentation
```

### PR Checklist

- [ ] Code follows the coding standards above
- [ ] All public functions have docstrings
- [ ] All functions have type hints
- [ ] No hardcoded colors in GUI (use theme tokens)
- [ ] No `print()` statements (use `logging`)
- [ ] No upward dependencies (GUI ← Core ← Tools)
- [ ] Tests added/updated (when applicable)
- [ ] Documentation updated (when applicable)

### Commit Message Format

```
type: short description

Longer description if needed.

type = feat | fix | refactor | docs | test | chore
```

Examples:
```
feat: add clipboard tool with copy/paste actions
fix: handle empty JSON array from LLM response
refactor: extract dispatch pattern into base class
docs: add tool creation tutorial
```

---

## Issue Guidelines

### Bug Reports

Use the `[Bug]` prefix:

```
[Bug] Parser crashes on nested JSON arrays

**Steps to reproduce:**
1. ...

**Expected behavior:**
...

**Actual behavior:**
...

**Environment:**
- OS: Windows 11
- Python: 3.11.5
- Ollama model: qwen3:8b
```

### Feature Requests

Use the `[Feature Request]` prefix:

```
[Feature Request] Clipboard Tool

**Use case:**
I want to copy file listings to the clipboard.

**Proposed solution:**
Add a ClipboardTool with copy/paste actions.

**Target milestone:** v0.9
```

---

## Code of Conduct

- Be respectful and constructive in all interactions
- Focus feedback on the code, not the person
- Welcome newcomers and help them get started
- Credit contributors in commit messages and changelogs
