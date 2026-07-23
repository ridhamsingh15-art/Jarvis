<p align="center">
  <h1 align="center">🤖 JARVIS</h1>
  <p align="center"><strong>Local AI Operating System</strong></p>
  <p align="center">
    A modular, privacy-first AI agent framework that runs entirely on your local machine.<br/>
    Powered by <a href="https://ollama.com">Ollama</a> · Built with <a href="https://wiki.qt.io/Qt_for_Python">PySide6</a> · No cloud. No API keys. No compromises.
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Ollama-local_LLM-black?logo=ollama" alt="Ollama" />
  <img src="https://img.shields.io/badge/PySide6-GUI-41CD52?logo=qt" alt="PySide6" />
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License" />
  <img src="https://img.shields.io/badge/version-1.0.0-brightgreen" alt="Version" />
</p>

---

## 📖 Overview

**Jarvis** is a local AI operating system that converts natural language into real desktop actions. Type `"open calculator"` and it opens Calculator. Say `"search google for Python tutorials"` and it launches a Google search in your browser. Ask it to create a folder, list files, or rename documents — all through natural conversation.

Unlike cloud-based AI assistants, Jarvis runs **100% locally** using Ollama for inference. Your data never leaves your machine.

### Why Jarvis?

- **🔒 Privacy-First** — All processing happens on your hardware. No telemetry, no cloud APIs.
- **🧠 Intelligent Planning** — LLM-powered planner converts fuzzy intent into structured task plans.
- **🔌 Extensible Tools** — Plugin architecture lets you add new capabilities without touching core code.
- **💾 Persistent Memory** — SQLite-backed conversation history with search and context injection.
- **🎨 Beautiful GUI** — Modern PySide6 desktop app with dark/light/AMOLED themes.
- **⌨️ CLI Mode** — Prefer the terminal? Use `--cli` for a lightweight REPL.

---

## ✨ Features

### Core Pipeline
| Feature | Description |
|---|---|
| **Natural Language Understanding** | LLM parses freeform text into structured JSON task plans |
| **Multi-Step Execution** | Single input can trigger multiple sequential actions |
| **Alias Normalization** | `"open chrome"` → `browser.open_site`, `"launch notepad"` → `windows.open_app` |
| **Validation Gate** | Every task is validated against the Registry before execution |
| **Conversation Memory** | Recent interactions are injected as LLM context for continuity |

### Tools
| Tool | Capabilities |
|---|---|
| **🪟 Windows** | Launch desktop applications (Notepad, Calculator, Paint, Terminal, etc.) |
| **🌐 Browser** | Open URLs, visit known sites (Google, YouTube, GitHub, etc.), Google search |
| **📂 File** | List directories, create/rename/move/copy/delete files and folders |

### GUI
| Feature | Description |
|---|---|
| **Chat Interface** | Rich bubbles with markdown, code blocks, copy buttons, and animations |
| **Memory Browser** | Search and browse stored conversation history |
| **Live Logs** | Color-coded real-time log viewer |
| **Plugin Inspector** | View registered tools and their available actions |
| **Theme Engine** | Dark, Light, and AMOLED themes via semantic color tokens |
| **Keyboard Shortcuts** | `Ctrl+K` focus chat, `Ctrl+L` clear chat |

---

## 🛠 Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Language** | Python 3.11+ | Core application language |
| **LLM Runtime** | [Ollama](https://ollama.com) | Local model inference (default: `qwen3:8b`) |
| **LLM Client** | `ollama` Python SDK | Chat API communication |
| **GUI Framework** | PySide6 (Qt 6) | Desktop application and theming |
| **Database** | SQLite3 (stdlib) | Conversation memory persistence |
| **File Ops** | `pathlib`, `shutil` | Cross-platform file management |
| **Process Control** | `subprocess` | Application launching |
| **Web** | `webbrowser` (stdlib) | Browser automation |
| **Config** | Environment variables + `dataclass` | Zero-dependency configuration |

---

## 📦 Installation

### Prerequisites

1. **Python 3.11+** — [Download](https://www.python.org/downloads/)
2. **Ollama** — [Download](https://ollama.com/download)
3. **A local LLM model** — e.g. `qwen3:8b`

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-username/Jarvis.git
cd Jarvis

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Pull an Ollama model
ollama pull qwen3:8b

# 5. Start Ollama (if not already running)
ollama serve
```

### Environment Variables (Optional)

| Variable | Default | Description |
|---|---|---|
| `JARVIS_MODEL` | `qwen3:8b` | Ollama model name |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `JARVIS_MAX_RETRIES` | `3` | Max LLM retry attempts |
| `JARVIS_TIMEOUT` | `30` | Request timeout (seconds) |
| `JARVIS_MEMORY_DB` | `~/.jarvis/memory.db` | Path to memory database |

---

## 🚀 Running the Project

### Desktop GUI (Default)

```bash
python main.py
```

A splash screen appears, followed by the full desktop application.

### Terminal REPL

```bash
python main.py --cli
```

```
  JARVIS — Local AI Operating System
  Type 'exit' or 'quit' to stop.

  You > open calculator
    ✓ Opened calculator

  You > search google for Python tutorials
    ✓ Searched Google for 'python tutorials'
```

---

## 📁 Folder Structure

```
Jarvis/
├── main.py                         # Entry point — wires components, launches GUI or CLI
├── requirements.txt                # Python dependencies (ollama, PySide6)
├── .env                            # Environment variable overrides
├── pyrightconfig.json              # Type checker configuration
│
├── config/                         # Configuration management
│   ├── __init__.py                 # Exports JarvisConfig, load_config
│   └── config.py                   # Frozen dataclass + env var loader
│
├── core/                           # Agent pipeline (brain of the system)
│   ├── __init__.py                 # Exports Agent
│   ├── agent.py                    # Top-level orchestrator (Planner → Validator → Executor)
│   ├── planner.py                  # Converts natural language → Task objects via LLM
│   ├── parser.py                   # Extracts JSON from raw LLM output
│   ├── normalizer.py               # Maps aliases to canonical tool/action/arg names
│   ├── validator.py                # Validates Tasks against the Registry
│   ├── executor.py                 # Runs validated Tasks via registered tools
│   ├── registry.py                 # Tool registration, lookup, and description
│   ├── task.py                     # Task dataclass with state machine lifecycle
│   ├── llm.py                      # Thin Ollama client (pure I/O boundary)
│   └── exceptions.py               # Custom exception hierarchy
│
├── tools/                          # Tool plugins (system capabilities)
│   ├── __init__.py                 # Exports BaseTool
│   ├── base_tool.py                # Abstract base class — contract for all tools
│   ├── browser.py                  # Web browsing: URLs, known sites, Google search
│   ├── file.py                     # File management: list, create, rename, move, copy, delete
│   └── windows.py                  # Windows app control: launch desktop applications
│
├── memory/                         # Conversation memory subsystem
│   ├── __init__.py                 # Exports BaseMemory, MemoryManager
│   ├── base_memory.py              # Abstract base class — backend contract
│   ├── models.py                   # MemoryEntry and MemoryContext dataclasses
│   ├── memory_manager.py           # High-level API: serialize, store, retrieve, format
│   └── sqlite_memory.py            # SQLite implementation of BaseMemory
│
├── gui/                            # PySide6 desktop application
│   ├── __init__.py                 # launch_gui() entry point
│   ├── main_window.py              # Application shell: sidebar + header + stack + footer
│   ├── splash.py                   # Branded splash screen with progress
│   ├── header.py                   # Top bar: title, model info, connection status
│   ├── sidebar.py                  # Navigation panel with page links
│   ├── footer.py                   # Status strip: state, model, tools, response time
│   ├── themes/                     # Theme engine
│   │   ├── __init__.py
│   │   ├── theme.py                # Theme dataclass, ThemeManager singleton, QSS builder
│   │   ├── dark.py                 # GitHub Dark-inspired palette
│   │   ├── light.py                # Clean white + blue accent palette
│   │   └── amoled.py               # Pure black OLED palette
│   ├── views/                      # Stacked page views
│   │   ├── __init__.py
│   │   ├── chat_view.py            # Main chat page with Agent worker thread
│   │   ├── memory_view.py          # Memory browser with search
│   │   ├── history_view.py         # Conversation history grouped by date
│   │   ├── logs_view.py            # Live color-coded log viewer
│   │   ├── plugins_view.py         # Registered tools inspector
│   │   └── settings_view.py        # Theme selector, model info, about
│   └── widgets/                    # Reusable UI components
│       ├── __init__.py
│       ├── chat_widget.py          # Scrollable bubble history with rich text
│       ├── input_widget.py         # Auto-growing message input
│       ├── task_card.py            # Task result display card
│       └── thinking_indicator.py   # Animated "Thinking..." indicator
│
└── docs/                           # Project documentation (you are here)
    ├── README.md
    ├── ARCHITECTURE.md
    ├── MODULES.md
    ├── FLOW.md
    ├── TOOLS.md
    ├── MEMORY.md
    ├── ROADMAP.md
    ├── CONTRIBUTING.md
    ├── API.md
    └── LEARNING.md
```

---

## 📚 Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture, diagrams, design principles |
| [MODULES.md](MODULES.md) | Detailed module reference |
| [FLOW.md](FLOW.md) | Complete execution flow with diagrams |
| [TOOLS.md](TOOLS.md) | Tool plugin documentation |
| [MEMORY.md](MEMORY.md) | Memory subsystem internals |
| [ROADMAP.md](ROADMAP.md) | Development milestones |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contributing guidelines |
| [API.md](API.md) | Internal interface reference |
| [LEARNING.md](LEARNING.md) | Jarvis Academy subsystem |

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](../LICENSE) file for details.

---

<p align="center">
  Built with ❤️ by the Jarvis team
</p>
