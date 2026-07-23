# 🗺 Roadmap

> Development milestones for the Jarvis Local AI Operating System.

---

## Release Timeline

```
         v0.8                v0.9               v1.0               v2.0
          │                   │                  │                   │
──────────┼───────────────────┼──────────────────┼───────────────────┼──────────▶
          │                   │                  │                   │
    Foundation          Production          Stable 1.0          Intelligence
    & Stability          Polish             Release              & Multimodal
```

---

## v0.8 — Foundation & Stability

> **Theme**: Harden the core pipeline, improve reliability, add testing.

### Core Pipeline

- [ ] **Unit tests** for all core modules (parser, normalizer, validator, executor)
- [ ] **Integration tests** for the full Agent pipeline (mock LLM)
- [ ] **Retry logic** in Executor with configurable max attempts
- [ ] **Task timeout** — kill tasks that exceed `JARVIS_TIMEOUT`
- [ ] **Structured logging** with log levels configurable per module
- [ ] **Input sanitization** — strip dangerous inputs before LLM

### Tools

- [ ] **Argument validation** — Validator checks required args, not just tool/action
- [ ] **Unknown app fallback** — Windows tool attempts `subprocess.Popen(name)` for unlisted apps
- [ ] **File tool safety** — Confirm destructive operations (delete, move) before execution
- [ ] **Browser tool** — Add `close_tab`, `open_incognito` actions

### Memory

- [ ] **Memory pruning** — Auto-delete entries older than 30 days
- [ ] **Memory stats** — Expose entry count, oldest/newest timestamps
- [ ] **Export/Import** — JSON export for backup and migration

### GUI

- [ ] **Error toast notifications** instead of error bubbles
- [ ] **Loading skeleton** for memory and history views
- [ ] **Keyboard shortcut overlay** — show all shortcuts on `Ctrl+?`
- [ ] **Window state persistence** — remember size and position

### Infrastructure

- [ ] **CI/CD pipeline** — GitHub Actions for linting, testing, type checking
- [ ] **Pre-commit hooks** — black, isort, pyright
- [ ] **`.env.example`** — Document all environment variables
- [ ] **`setup.py` / `pyproject.toml`** — Proper packaging

---

## v0.9 — Production Polish

> **Theme**: Polish the user experience, expand tool capabilities, prepare for public release.

### Core Pipeline

- [ ] **Streaming responses** — LLM responses streamed token-by-token
- [ ] **Multi-turn planning** — Planner can ask clarifying questions
- [ ] **Task dependencies** — Define execution order for related tasks
- [ ] **Parallel execution** — Run independent tasks concurrently
- [ ] **Fallback planning** — Retry with simpler prompt on parse failure

### Tools

- [ ] **Clipboard Tool** — Read/write system clipboard
- [ ] **System Info Tool** — CPU, RAM, disk, battery, network status
- [ ] **Notification Tool** — Show Windows toast notifications
- [ ] **Scheduler Tool** — Schedule tasks for future execution
- [ ] **Custom app paths** — User-defined app name → command mappings

### Memory

- [ ] **Vector search** — Embed queries with local model for semantic retrieval
- [ ] **Smart context** — Select most relevant memories, not just most recent
- [ ] **Memory tags** — Auto-categorize by tool/action type
- [ ] **Conversation sessions** — Group related interactions

### GUI

- [ ] **Streaming chat** — Display LLM tokens as they arrive
- [ ] **Task queue panel** — Show pending/running/completed tasks
- [ ] **System tray** — Minimize to tray, quick-launch from tray icon
- [ ] **Drag-and-drop** — Drop files into chat for file operations
- [ ] **Notification badge** — Sidebar icons show unread counts
- [ ] **Responsive layout** — Collapsible sidebar on narrow windows
- [ ] **Custom CSS** — User-defined theme overrides

### Documentation

- [ ] **API reference** — Auto-generated from docstrings
- [ ] **Video tutorials** — Setup, usage, and tool creation
- [ ] **Plugin development guide** — Step-by-step tutorial

---

## v1.0 — Stable Release

> **Theme**: First public stable release. Feature-complete core, production-ready, well-documented.

### Core

- [ ] **Stable public API** — `Agent.run()` contract locked
- [ ] **Semantic versioning** — Proper semver from this point
- [ ] **100% test coverage** on core pipeline
- [ ] **Performance benchmarks** — Track pipeline latency
- [ ] **Error recovery** — Graceful degradation on partial failures

### Plugin System

- [ ] **Plugin directory** — Auto-discover tools from `plugins/` directory
- [ ] **Plugin manifest** — `plugin.json` with metadata, version, dependencies
- [ ] **Plugin hot-reload** — Register/unregister without restart
- [ ] **Plugin marketplace** — Browse and install community plugins

### GUI

- [ ] **Onboarding flow** — First-run setup wizard
- [ ] **Keyboard-first UX** — Full keyboard navigation
- [ ] **Accessibility** — Screen reader support, high contrast mode
- [ ] **Localization** — i18n framework for multi-language support
- [ ] **Auto-updater** — Check for new versions on startup

### Distribution

- [ ] **Windows installer** (MSI/NSIS) — One-click install
- [ ] **Portable build** — Single `.exe` via PyInstaller
- [ ] **Chocolatey package** — `choco install jarvis`
- [ ] **Docker image** — For headless/CLI deployments

### Documentation

- [ ] **Comprehensive README** — Badges, screenshots, GIFs
- [ ] **Changelog** — Maintain `CHANGELOG.md` with every release
- [ ] **Community guidelines** — Issue templates, PR templates, CoC

---

## v2.0 — Intelligence & Multimodal

> **Theme**: Advanced AI capabilities — vision, voice, learning, multi-agent.

### 🔮 Vision

- [ ] **Vision Tool** — Screenshot capture and analysis
- [ ] **Screen understanding** — Describe what's on screen using multimodal LLM
- [ ] **Element detection** — Find buttons, text, inputs by description
- [ ] **OCR** — Read text from any screen region
- [ ] **Visual grounding** — Click on elements identified by vision

### 🎤 Voice

- [ ] **Voice Input** — Speech-to-text via Whisper (local)
- [ ] **Voice Output** — Text-to-speech via Piper/Bark
- [ ] **Wake Word** — "Hey Jarvis" detection
- [ ] **Continuous listening** — Background voice monitoring
- [ ] **Voice-controlled navigation** — Navigate GUI with voice

### 🧠 Learning (Jarvis Academy)

- [ ] **User pattern learning** — Learn from repeated corrections
- [ ] **Command shortcuts** — User-defined macros
- [ ] **Workflow recording** — Record and replay multi-step workflows
- [ ] **Preference learning** — Remember user preferences (default browser, preferred apps)
- [ ] **Adaptive prompting** — Refine system prompt based on usage patterns

### 🤖 Multi-Agent

- [ ] **Agent specialization** — Different agents for different domains
- [ ] **Agent coordination** — Agents delegating to each other
- [ ] **Agent memory sharing** — Shared context across agents
- [ ] **Hierarchical planning** — Meta-agent decomposes complex goals

### 🌐 Integrations

- [ ] **REST API** — HTTP server for remote control
- [ ] **WebSocket streaming** — Real-time updates for web clients
- [ ] **Discord/Slack bot** — Chat platform integration
- [ ] **Home automation** — IoT device control
- [ ] **Calendar/Email** — Productivity integrations

---

## Contributing to the Roadmap

Roadmap items are tracked as GitHub Issues with milestone labels. To propose a new feature:

1. Open an Issue with the `[Feature Request]` prefix
2. Tag it with the target milestone (`v0.8`, `v0.9`, `v1.0`, `v2.0`)
3. Describe the use case and proposed implementation
4. Community votes (👍) help prioritize

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.
