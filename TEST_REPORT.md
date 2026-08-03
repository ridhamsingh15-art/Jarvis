# Test Report

Date: 2026-08-04

## Automated verification

| Check | Result |
| --- | --- |
| `pytest -q` | Passed: 322 tests |
| `ruff check .` | Passed |
| `mypy .` | Passed: no issues in 542 source files |
| `python main.py --cli` | Passed: registry, SQLite memory, provider, and action bridge initialized; clean exit confirmed |

## Conversation and routing coverage

Regression tests verify:

- `hello` produces a natural greeting.
- `who are you` and `what can you do` produce JARVIS-specific responses.
- Identity/name questions receive a truthful prompt to provide the user's name.
- Explicit personal facts persist in SQLite and can be recalled in a later turn.
- Common file-creation requests use the file tool without requiring an LLM.
- `open github` selects `browser.open_site`.
- A URL selects `browser.open_url`.
- `search python` selects `browser.search_google`.
- Browser routing keeps browser arguments and does not fall back to Windows.

## Manual-action safety note

Desktop application launches, browser launches, and file creation were not
performed against the active user session during this audit. Their routing and
execution bridges are covered by tests; executing them manually would mutate
the desktop session.

Personal-memory verification was run through the real CLI against an isolated
temporary SQLite database. It successfully stored and recalled a user name and
favorite editor without calling Ollama.
