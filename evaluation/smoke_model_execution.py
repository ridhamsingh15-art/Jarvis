from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from config.config import load_config
from core.llm import LLMClient
from mission_control.crash_cli import execute_objective
from mission_control.objective_planner import build_objective_plan


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jarvis-model-e2e-") as temporary:
        root = Path(temporary)
        workspace = root / "workspace"
        workspace.mkdir()
        target = workspace / "known-content.txt"
        target.write_text("JARVIS_MODEL_DRIVEN_EXECUTION_MARKER\\n", encoding="utf-8")
        objective = f"Find the largest file in {workspace}, then read that exact file and return its contents."
        encoded_steps = build_objective_plan(objective, llm_client=LLMClient(load_config()))
        steps = [json.loads(encoded) for encoded in encoded_steps]

        # Execute only the exact, read-only plan under test; fail closed on any
        # unexpected model-generated action or target path.
        sequence = [(step.get("tool"), step.get("action")) for step in steps]
        expected = [("file", "list_largest_files"), ("file", "read_file")]
        if sequence != expected:
            raise RuntimeError(f"Refusing execution: unexpected model tool sequence {sequence!r}")
        if Path(steps[0]["args"]["path"]).resolve() != workspace.resolve():
            raise RuntimeError("Refusing execution: model changed the fixture workspace path.")
        first_id = steps[0]["id"]
        reference = steps[1]["args"].get("path")
        if reference != {"$ref": f"{first_id}.result.files.0.path"}:
            raise RuntimeError(f"Refusing execution: dependency path was not the validated full-path reference: {reference!r}")
        if first_id not in steps[1].get("depends_on", []):
            raise RuntimeError("Refusing execution: dependent read step omitted its dependency edge.")

        result = execute_objective(
            objective,
            mission_db=root / "missions.sqlite3",
            mission_id="model-generated-read-only-e2e",
            workspace_root=workspace,
            steps=encoded_steps,
        )
        mission = result.get("mission") or {}
        rows = result.get("steps", [])
        assert mission.get("state") == "COMPLETED", mission
        assert mission.get("verification_status") == "verified", mission
        assert len(rows) == 2
        assert all(row.get("status") == "completed" for row in rows)
        assert all(row.get("verification", {}).get("status") == "verified" for row in rows)
        assert "JARVIS_MODEL_DRIVEN_EXECUTION_MARKER" in str(rows[1].get("result"))
        print(json.dumps({
            "model": load_config().model,
            "objective": objective,
            "planned_sequence": [f"{tool}.{action}" for tool, action in sequence],
            "dependency_reference": reference,
            "mission_state": mission.get("state"),
            "verification_status": mission.get("verification_status"),
            "step_verification": [row.get("verification") for row in rows],
            "execution_performed": True,
            "result": "PASS",
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
