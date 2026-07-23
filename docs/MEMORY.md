# 🧠 Memory Subsystem

> Deep dive into the Jarvis conversation memory architecture.

---

## Overview

The Memory subsystem gives Jarvis **conversation continuity**. It stores every interaction (user input + task results), retrieves recent history as context for the LLM, and supports keyword search for memory browsing.

```
┌──────────────────────────────────────────────────────────┐
│                   Memory Architecture                    │
│                                                          │
│  Agent ──▶ MemoryManager ──▶ BaseMemory ◀── SqliteMemory │
│                │                                  │      │
│                │                                  │      │
│                ▼                                  ▼      │
│          MemoryContext                      SQLite DB     │
│          (formatted str)                  (~/.jarvis/     │
│                                            memory.db)    │
└──────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Fully Optional** — If `memory=None`, the Agent pipeline works identically
2. **Fail-Safe** — Memory errors are logged but never crash the pipeline
3. **Backend Agnostic** — `BaseMemory` abstract class allows any storage backend
4. **Zero Infrastructure** — SQLite requires no server, no setup, just a file

---

## SQLite Schema

### Database Location

```
~/.jarvis/memory.db
```

Override with `JARVIS_MEMORY_DB` environment variable.

### Table: `memory`

```sql
CREATE TABLE IF NOT EXISTS memory (
    id         TEXT PRIMARY KEY,           -- UUID v4
    timestamp  TEXT NOT NULL,              -- ISO 8601 UTC
    user_input TEXT NOT NULL,              -- Original user message
    tasks_json TEXT NOT NULL DEFAULT '[]', -- JSON array of task results
    summary    TEXT NOT NULL DEFAULT ''    -- One-line summary
);
```

### Column Details

| Column | Type | Description | Example |
|---|---|---|---|
| `id` | TEXT (UUID) | Unique entry identifier | `"a1b2c3d4-..."` |
| `timestamp` | TEXT (ISO 8601) | UTC timestamp of interaction | `"2026-07-23T12:00:00+00:00"` |
| `user_input` | TEXT | The user's original natural language | `"open calculator"` |
| `tasks_json` | TEXT (JSON) | Serialized task results array | `[{"tool":"windows",...}]` |
| `summary` | TEXT | Auto-generated one-line summary | `"open calculator → 1 completed"` |

### `tasks_json` Structure

Each entry in the JSON array contains:

```json
{
    "tool": "windows",
    "action": "open_app",
    "status": "completed",
    "result": "Opened calculator",
    "error": ""
}
```

### SQL Queries

**Insert**:
```sql
INSERT INTO memory (id, timestamp, user_input, tasks_json, summary)
VALUES (?, ?, ?, ?, ?)
```

**Get Recent** (most recent first):
```sql
SELECT id, timestamp, user_input, tasks_json, summary
FROM memory
ORDER BY timestamp DESC
LIMIT ?
```

**Search** (keyword match on user_input and summary):
```sql
SELECT id, timestamp, user_input, tasks_json, summary
FROM memory
WHERE user_input LIKE ? OR summary LIKE ?
ORDER BY timestamp DESC
LIMIT ?
```

**Clear All**:
```sql
DELETE FROM memory
```

---

## Data Models

### `MemoryEntry`

Represents one conversation turn stored in memory.

```python
@dataclass
class MemoryEntry:
    user_input: str                     # Original user message
    tasks: list[dict[str, Any]]         # Serialized task results
    summary: str = ""                   # Auto-generated summary
    id: str = uuid4()                   # Unique identifier
    timestamp: datetime = now(utc)      # When this occurred
```

### `MemoryContext`

Context bundle passed to the Planner for LLM injection.

```python
@dataclass
class MemoryContext:
    entries: list[MemoryEntry] = []     # Recent history entries
    formatted: str = ""                 # Pre-formatted prompt string
```

---

## Memory Lifecycle

### 1. Storage Flow

```
Agent._save_to_memory(user_input, tasks)
    │
    ▼
MemoryManager.store_interaction(user_input, tasks)
    │
    ├── _serialize_tasks(tasks)
    │   └── For each Task → dict with tool, action, status, result, error
    │
    ├── _build_summary(user_input, tasks)
    │   └── "open calculator → 1 completed"
    │
    ├── Create MemoryEntry(user_input, serialized, summary)
    │   └── Auto-generates UUID and UTC timestamp
    │
    └── BaseMemory.store(entry)
        └── SqliteMemory: INSERT INTO memory VALUES (...)
```

### 2. Retrieval Flow

```
Agent._load_context()
    │
    ▼
MemoryManager.get_context()
    │
    ├── BaseMemory.get_recent(limit=5)
    │   └── SqliteMemory: SELECT ... ORDER BY timestamp DESC LIMIT 5
    │
    ├── Returns list[MemoryEntry] (most recent first)
    │
    ├── _format_context(entries)
    │   └── Reverses to chronological order
    │   └── Formats as prompt-ready string
    │
    └── Returns MemoryContext(entries, formatted)
```

### 3. Search Flow

```
MemoryView._on_search(query)
    │
    ▼
SqliteMemory.search(query, limit=50)
    │
    ├── SQL: WHERE user_input LIKE '%query%' OR summary LIKE '%query%'
    │
    └── Returns list[MemoryEntry]
```

---

## Context Formatting

The `MemoryManager._format_context()` method produces a string ready for LLM prompt injection:

```
Previous conversation:
- User: open calculator
  Result: Opened calculator
- User: search google for Python
  Result: Searched Google for 'Python'
- User: list files on desktop
  Error: Path does not exist
```

### Format Rules

1. Entries are reversed to **chronological order** (oldest first) for natural conversation flow
2. Maximum **5 entries** by default (`_MAX_CONTEXT_ENTRIES = 5`)
3. Completed tasks show `Result: ...`
4. Failed tasks show `Error: ...`
5. Entries with unknown status are omitted

---

## Summary Generation

The `_build_summary` method auto-generates a one-line summary:

```python
def _build_summary(user_input: str, tasks: list[Task]) -> str:
    # Counts completed and failed tasks
    # Truncates user_input to 80 chars
    # Format: "{input} → {N completed}, {M failed}"
```

### Examples

| User Input | Tasks | Summary |
|---|---|---|
| `"open calculator"` | 1 completed | `"open calculator → 1 completed"` |
| `"open notepad and search google"` | 2 completed | `"open notepad and search google → 2 completed"` |
| `"delete system32"` | 1 failed | `"delete system32 → 1 failed"` |
| `"do many things..."` | 3 ok, 1 fail | `"do many things... → 3 completed, 1 failed"` |

---

## Backend Interface (`BaseMemory`)

To implement a custom memory backend, extend `BaseMemory`:

```python
from memory.base_memory import BaseMemory
from memory.models import MemoryEntry


class RedisMemory(BaseMemory):
    """Redis-backed memory implementation."""

    def store(self, entry: MemoryEntry) -> None:
        """Persist a memory entry to Redis."""
        ...

    def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        """Retrieve recent entries from Redis."""
        ...

    def search(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Full-text search in Redis."""
        ...

    def clear(self) -> None:
        """Delete all entries from Redis."""
        ...
```

Then inject it into `MemoryManager`:

```python
redis_memory = RedisMemory(host="localhost", port=6379)
memory_manager = MemoryManager(redis_memory)
agent = Agent(planner, validator, executor, memory=memory_manager)
```

---

## Error Handling

Memory operations are **never allowed to crash the pipeline**:

| Operation | Error Behavior |
|---|---|
| `store_interaction` | Exception → logged as warning, silently ignored |
| `get_context` | Exception → logged as warning, returns empty `MemoryContext` |
| `get_recent` | `sqlite3.Error` → logged, returns empty list |
| `search` | `sqlite3.Error` → logged, returns empty list |
| `clear` | `sqlite3.Error` → raises `MemoryError` |
| `_ensure_database` | `sqlite3.Error` → raises `MemoryError` (startup only) |

---

## SQLite Implementation Details

### Connection Management

- Each operation creates a **new connection** via `_connect()`
- Uses `sqlite3.Row` row factory for dict-like access
- Context manager (`with self._connect()`) ensures auto-commit and cleanup
- No connection pooling (single-user application)

### Auto-Initialization

On first instantiation:
1. Parent directories created with `Path.mkdir(parents=True, exist_ok=True)`
2. `CREATE TABLE IF NOT EXISTS` ensures idempotent setup
3. Logs confirmation: `"Memory database ready: {path}"`

### Serialization

| Direction | Method | Details |
|---|---|---|
| Python → SQLite | `json.dumps(entry.tasks, default=str)` | `default=str` handles non-serializable types |
| SQLite → Python | `json.loads(row["tasks_json"])` | Returns list[dict] |
| Timestamp → SQLite | `entry.timestamp.isoformat()` | ISO 8601 string |
| SQLite → Timestamp | `datetime.fromisoformat(row["timestamp"])` | Reconstructed with UTC tzinfo |

---

## Future Improvements

- [ ] **Vector Search** — Embed user queries with a local embedding model for semantic retrieval
- [ ] **Memory Pruning** — Auto-delete entries older than N days
- [ ] **Memory Tags** — Categorize memories by tool/action type
- [ ] **Export/Import** — JSON export for backup and migration
- [ ] **Memory Summarization** — LLM-powered summarization of long conversation histories
- [ ] **Chunked Context** — Smart context selection (most relevant, not just most recent)
- [ ] **Multi-User** — Separate memory spaces per user profile
- [ ] **Encryption** — Encrypt the SQLite database at rest
