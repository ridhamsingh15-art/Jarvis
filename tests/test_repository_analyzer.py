from pathlib import Path

from applications.software_engineer.repository_analyzer import RepositoryAnalyzer


def test_analyzer_does_not_exclude_github_directory_or_similarly_named_paths(tmp_path: Path):
    github = tmp_path / ".github" / "workflows"
    github.mkdir(parents=True)
    (github / "check.py").write_text('if __name__ == "__main__":\n    pass\n', encoding="utf-8")
    similarly_named = tmp_path / "my.venv.notes"
    similarly_named.mkdir()
    (similarly_named / "module.py").write_text("import json\n", encoding="utf-8")
    ignored = tmp_path / ".venv" / "lib"
    ignored.mkdir(parents=True)
    (ignored / "third_party.py").write_text("import unknown\n", encoding="utf-8")

    result = RepositoryAnalyzer(str(tmp_path)).analyze()

    assert ".github/workflows/check.py" in result.dependency_graph.modules or ".github\\workflows\\check.py" in result.dependency_graph.modules
    assert any(path.endswith("module.py") for path in result.dependency_graph.modules)
    assert not any(path.endswith("third_party.py") for path in result.dependency_graph.modules)
    assert any(path.endswith("check.py") for path in result.entry_points)


def test_requirements_parser_ignores_comments_options_and_direct_urls(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(
        "# comment only\n"
        "requests>=2.0 # inline comment\n"
        "numpy==1.26.0\n"
        "-r requirements-dev.txt\n"
        "--index-url https://packages.example/simple\n"
        "git+https://example.invalid/org/project.git#egg=internal-lib\n"
        "https://example.invalid/packages/custom.whl\n"
        "invalid package name\n"
        "Pillow[extra]>=10; python_version >= '3.11'\n",
        encoding="utf-8",
    )

    packages = RepositoryAnalyzer(str(tmp_path))._detect_external_packages()

    assert packages == ["requests", "numpy", "Pillow"]


def test_analyzer_logs_parse_errors_and_continues(tmp_path: Path, caplog):
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    (tmp_path / "valid.py").write_text("import pathlib\n", encoding="utf-8")

    result = RepositoryAnalyzer(str(tmp_path)).analyze()

    assert any(path.endswith("valid.py") for path in result.dependency_graph.modules)
    assert "Syntax error while parsing broken.py" in caplog.text
