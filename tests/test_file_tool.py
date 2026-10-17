from pathlib import Path

from tools.file import FileTool


def test_create_and_write_file(tmp_path: Path) -> None:
    tool = FileTool()
    target = tmp_path / "test.txt"

    assert "Created file" in tool.execute("create_file", {"path": str(target)})
    assert target.exists()
    assert "Wrote 11 character(s)" in tool.execute(
        "write_file", {"path": str(target), "content": "hello world"}
    )
    assert target.read_text(encoding="utf-8") == "hello world"
