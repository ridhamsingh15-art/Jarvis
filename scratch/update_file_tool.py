with open('tools/file.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_actions = """            "open_file": ActionDefinition(
                name="open_file",
                description="Opens a file with the default application.",
                required_args=["path"]
            ),
        }"""

new_actions = """            "open_file": ActionDefinition(
                name="open_file",
                description="Opens a file with the default application.",
                required_args=["path"]
            ),
            "read_file": ActionDefinition(
                name="read_file",
                description="Reads and returns text content from a file.",
                required_args=["path"]
            ),
        }"""

old_dispatch = """            "open_file": self._open_file,
        }"""

new_dispatch = """            "open_file": self._open_file,
            "read_file": self._read_file,
        }"""

old_method = """    @staticmethod
    def _open_file(args: dict) -> str:"""

new_method = """    @staticmethod
    def _read_file(args: dict) -> str:
        path = _resolve_path(args.get("path", ""))
        _validate_path(path, must_exist=True)
        if not path.is_file():
            raise ExecutionError(f"Not a file: '{path}'")
        try:
            content = path.read_text(encoding="utf-8")
            logger.info("Read file: %s (%d chars)", path, len(content))
            return content
        except OSError as exc:
            raise ExecutionError(f"Failed to read '{path.name}': {exc}") from exc

    @staticmethod
    def _open_file(args: dict) -> str:"""

assert old_actions in text, "old_actions not found"
assert old_dispatch in text, "old_dispatch not found"
assert old_method in text, "old_method not found"

text = text.replace(old_actions, new_actions, 1)
text = text.replace(old_dispatch, new_dispatch, 1)
text = text.replace(old_method, new_method, 1)

with open('tools/file.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)
print("Successfully updated tools/file.py with read_file")
