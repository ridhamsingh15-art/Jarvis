from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("source", "expected_code", "summary"),
    [
        ("def test_probe():\n    assert True\n", 0, r"1 passed in "),
        ("def test_probe():\n    assert False, 'intentional probe failure'\n", 1, r"1 failed in "),
    ],
    ids=("all-passing-session-exits-zero", "failing-session-exits-nonzero"),
)
def test_real_pytest_subprocess_prints_summary_and_returns_correct_code(
    tmp_path: Path, source: str, expected_code: int, summary: str
) -> None:
    """Exercise real pytest CLI startup, sessionfinish, terminal output and exit code."""
    probe = ROOT / "tests" / f"test__pytest_exit_probe_{uuid.uuid4().hex}.py"
    child_temp = tmp_path / "child-temp"
    child_temp.mkdir()
    env = os.environ.copy()
    env["TEMP"] = str(child_temp)
    env["TMP"] = str(child_temp)
    try:
        probe.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "-c",
                str(ROOT / "pytest.ini"),
                str(probe),
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    finally:
        probe.unlink(missing_ok=True)

    output = result.stdout + "\n" + result.stderr
    assert result.returncode == expected_code, output
    assert re.search(summary + r"\d+(?:\.\d+)?s", output), output
