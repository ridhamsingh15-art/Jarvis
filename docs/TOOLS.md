# 🔧 Tools Reference

> Complete documentation for every Jarvis tool plugin.

---

## Tool Architecture

All tools implement the `BaseTool` abstract base class:

```
BaseTool (ABC)
├── name: str              → Unique identifier (e.g. "windows")
├── description: str       → Human-readable description for LLM prompts
├── get_actions() → dict   → Available actions with descriptions
└── execute(action, args)  → Execute an action, return result string
```

Tools are self-contained plugins. They communicate with the framework **only** through the `BaseTool` interface. To add a new tool:

1. Create a new file in `tools/`
2. Implement `BaseTool`
3. Register it in `main.py` with `registry.register(MyTool())`

---

## 🪟 Windows Tool

**Module**: `tools/windows.py`
**Registry Name**: `windows`
**Description**: Control Windows desktop applications

### Actions

| Action | Args | Description |
|---|---|---|
| `open_app` | `app: str` | Launch a Windows application by name |

### Known Applications

| App Name | Windows Command | Example Input |
|---|---|---|
| `notepad` | `notepad` | "open notepad" |
| `calculator` | `calc` | "open calculator" |
| `paint` | `mspaint` | "open paint" |
| `cmd` | `cmd` | "open cmd" |
| `terminal` | `wt` | "open terminal" |
| `explorer` | `explorer` | "open explorer" |
| `task manager` | `taskmgr` | "open task manager" |
| `snipping tool` | `snippingtool` | "open snipping tool" |

### Aliases That Resolve to This Tool

```
"application", "app", "desktop", "program", "system" → windows
```

### Action Aliases

```
"open", "launch", "start", "run" → open_app
```

### Argument Aliases

```
"name", "program", "application", "app_name" → app
```

### Implementation Details

- Uses `subprocess.Popen(command)` for non-blocking app launch
- Dispatch pattern: action → handler function via dict lookup
- `OSError` caught and wrapped in `ExecutionError`

### Error Handling

| Error | Cause | Result |
|---|---|---|
| Missing `app` argument | LLM didn't provide app name | `ExecutionError("Missing required argument: 'app'")` |
| Unknown application | App name not in `_APP_COMMANDS` | `ExecutionError("Unknown application: '...'")` |
| Launch failure | OS-level failure | `ExecutionError("Failed to open ...: ...")` |

### Example Execution

```python
# Input:
tool.execute("open_app", {"app": "calculator"})

# Internal:
# app_name = "calculator" → _APP_COMMANDS["calculator"] = "calc"
# subprocess.Popen("calc")

# Output:
"Opened calculator"
```

---

## 🌐 Browser Tool

**Module**: `tools/browser.py`
**Registry Name**: `browser`
**Description**: Open websites, URLs, and perform Google searches

### Actions

| Action | Args | Description |
|---|---|---|
| `open_url` | `url: str` | Open a URL in the default browser |
| `open_site` | `site: str` | Open a known website by friendly name |
| `search_google` | `query: str` | Search Google with a query string |

### Known Sites

| Site Name | URL |
|---|---|
| `google` | `https://www.google.com` |
| `youtube` | `https://www.youtube.com` |
| `github` | `https://github.com` |
| `gmail` | `https://mail.google.com` |
| `stackoverflow` | `https://stackoverflow.com` |
| `reddit` | `https://www.reddit.com` |
| `twitter` / `x` | `https://twitter.com` |
| `linkedin` | `https://www.linkedin.com` |
| `wikipedia` | `https://www.wikipedia.org` |
| `chatgpt` | `https://chat.openai.com` |
| `amazon` | `https://www.amazon.com` |
| `netflix` | `https://www.netflix.com` |
| `whatsapp` | `https://web.whatsapp.com` |

### Aliases That Resolve to This Tool

```
"web", "internet", "chrome", "edge", "firefox" → browser
```

### Action Aliases

```
"search", "google", "search_web"  → search_google
"navigate", "go_to", "browse"     → open_url
"visit"                           → open_site
```

### Argument Aliases

```
"link", "address", "website", "webpage" → url
"site_name", "website_name"            → site
"search_query", "search_term", "search", "text" → query
```

### Implementation Details

- Uses Python's `webbrowser.open()` for cross-platform browser launch
- URLs without scheme get `https://` prepended automatically
- Google search uses `urllib.parse.quote_plus()` for query encoding
- Google search URL: `https://www.google.com/search?q={query}`

### Error Handling

| Error | Cause | Result |
|---|---|---|
| Missing `url` | No URL provided | `ExecutionError("Missing required argument: 'url'")` |
| Missing `site` | No site name provided | `ExecutionError("Missing required argument: 'site'")` |
| Unknown site | Site not in `_KNOWN_SITES` | `ExecutionError("Unknown site: '...'")` |
| Missing `query` | No search query provided | `ExecutionError("Missing required argument: 'query'")` |
| Browser failure | `webbrowser.Error` | `ExecutionError("Failed to ...")` |

### Example Executions

```python
# Open URL:
tool.execute("open_url", {"url": "github.com"})
# → webbrowser.open("https://github.com")
# → "Opened https://github.com"

# Open known site:
tool.execute("open_site", {"site": "youtube"})
# → webbrowser.open("https://www.youtube.com")
# → "Opened youtube"

# Google search:
tool.execute("search_google", {"query": "python tutorials"})
# → webbrowser.open("https://www.google.com/search?q=python+tutorials")
# → "Searched Google for 'python tutorials'"
```

---

## 📂 File Tool

**Module**: `tools/file.py`
**Registry Name**: `file`
**Description**: Manage files and directories on the local filesystem

### Actions

| Action | Args | Description |
|---|---|---|
| `list_directory` | `path: str` | List contents of a directory |
| `create_folder` | `path: str` | Create a new folder (and parents) |
| `rename` | `path: str`, `new_name: str` | Rename a file or folder |
| `move` | `path: str`, `dest: str` | Move a file or folder |
| `copy` | `path: str`, `dest: str` | Copy a file or folder |
| `delete` | `path: str` | Delete a file or empty folder |
| `open_file` | `path: str` | Open a file with the default application |

### Aliases That Resolve to This Tool

```
"folder", "directory", "filesystem", "files", "folders", "fs" → file
```

### Action Aliases

```
"ls", "dir", "list", "list_files"                      → list_directory
"mkdir", "make_folder", "create_directory", "new_folder" → create_folder
"rm", "remove"                                          → delete
"mv"                                                    → move
"cp", "duplicate"                                       → copy
```

### Argument Aliases

```
"folder", "directory", "file_path", "folder_path", "dir", "source", "from" → path
"destination", "target", "to" → dest
"new_name", "filename"        → new_name
```

### Safety: Protected Paths

The File tool blocks operations on critical system paths:

```
Protected by prefix match:
  - C:\Windows (or %SYSTEMROOT%)
  - C:\Program Files
  - C:\Program Files (x86)

Protected by exact match:
  - C:\ (drive root)

Protected by containment:
  - The Jarvis project directory itself
```

All paths are resolved to absolute paths before validation.

### Implementation Details

| Operation | Library | Details |
|---|---|---|
| List directory | `pathlib.Path.iterdir()` | Sorted, `[DIR]` prefix for directories |
| Create folder | `pathlib.Path.mkdir(parents=True)` | Creates parent dirs if needed |
| Rename | `pathlib.Path.rename()` | Validates both old and new paths |
| Move | `shutil.move()` | Works for files and directories |
| Copy | `shutil.copy2()` / `shutil.copytree()` | `copy2` for files, `copytree` for dirs |
| Delete | `Path.unlink()` / `Path.rmdir()` | Only empty directories (safety) |
| Open file | `os.startfile()` | Windows-specific, launches default app |

### Error Handling

| Error | Cause | Result |
|---|---|---|
| Empty path | No path provided | `ExecutionError("Path cannot be empty")` |
| Protected path | System/project directory | `ExecutionError("Operation blocked: ...")` |
| Path not found | File/dir doesn't exist | `ExecutionError("Path does not exist: ...")` |
| Not a directory | `list_directory` on a file | `ExecutionError("Not a directory: ...")` |
| Already exists | `create_folder` on existing path | `ExecutionError("Already exists: ...")` |
| Target exists | `rename` target already taken | `ExecutionError("Target already exists: ...")` |
| Not a file | `open_file` on a directory | `ExecutionError("Not a file: ...")` |
| OS error | Permission denied, etc. | `ExecutionError("Failed to ...")` |

### Example Executions

```python
# List directory:
tool.execute("list_directory", {"path": "C:\\Users\\ridha\\Desktop"})
# → "Contents of C:\Users\ridha\Desktop:\n  [DIR] Projects\n       notes.txt"

# Create folder:
tool.execute("create_folder", {"path": "C:\\Users\\ridha\\Desktop\\NewFolder"})
# → "Created folder: C:\Users\ridha\Desktop\NewFolder"

# Rename:
tool.execute("rename", {"path": "C:\\Users\\ridha\\notes.txt", "new_name": "todo.txt"})
# → "Renamed 'notes.txt' to 'todo.txt'"

# Delete:
tool.execute("delete", {"path": "C:\\Users\\ridha\\Desktop\\old_file.txt"})
# → "Deleted 'old_file.txt'"
```

---

## 🔮 Future: Vision Tool

> **Status**: Planned for v2.0

The Vision Tool will add screenshot analysis and screen understanding capabilities.

### Planned Actions

| Action | Description |
|---|---|
| `capture_screen` | Take a screenshot of the current display |
| `describe_screen` | Use a vision LLM to describe what's on screen |
| `find_element` | Locate a UI element by description |
| `read_text` | OCR text from a screen region |

### Architecture Considerations

- Will require a multimodal LLM (e.g. `llava`, `moondream`)
- Screenshot capture via `PIL.ImageGrab` or `mss`
- Integration with Planner for vision-guided task planning
- Must remain optional (graceful degradation if no vision model)

---

## 🎤 Future: Voice Tool

> **Status**: Planned for v2.0

The Voice Tool will add speech-to-text input and text-to-speech output.

### Planned Actions

| Action | Description |
|---|---|
| `listen` | Capture speech from microphone and transcribe |
| `speak` | Convert text to speech and play through speakers |
| `wake_word` | Listen for a wake word ("Hey Jarvis") |

### Architecture Considerations

- STT via Whisper (local) or Vosk
- TTS via Piper, Bark, or system TTS
- Continuous listening mode with wake word detection
- Must run on a separate thread to avoid blocking the GUI
- Integration with InputWidget for voice-triggered messages

---

## Tool Dispatch Pattern

All tools use the same internal dispatch pattern:

```python
class SomeTool(BaseTool):
    def execute(self, action: str, args: dict) -> str:
        dispatch = {
            "action_one": self._action_one,
            "action_two": self._action_two,
        }

        handler = dispatch.get(action)

        if handler is None:
            raise ExecutionError(f"Unknown action: '{action}'")

        return handler(args)
```

This pattern ensures:
- Clean separation of concerns per action
- Easy addition of new actions
- Consistent error handling for unknown actions
- Static analysis compatibility (no `getattr` magic)
