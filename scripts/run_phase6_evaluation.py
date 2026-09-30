"""
Phase 6 Real-World Regression Runner.

Evaluates Result Grounding and Completion Quality across the core scenarios:
- E-MULTI
- F-RECOVER
- H-SWE
- L-VERIFY
- N-ESCALATE

Uses the real JARVIS pipeline with qwen3-coder:30b-a3b-q4_K_M.
Verifies that final responses reflect actual execution facts.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Set working directory to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure Ollama model directory is set
os.environ["OLLAMA_MODELS"] = r"D:\Ollama\Models"

from core.mission_verifier import MissionCompletionVerifier
from core.task import Task as JT, TaskStatus
from main import build_agent


class LogCaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record):
        try:
            self.lines.append(self.format(record))
        except Exception:
            pass


@dataclass
class ScenarioResult:
    scenario_id: str
    route: str = "UNKNOWN"
    status: str = "UNKNOWN"
    success: bool = False
    verification: str = "UNKNOWN"
    latency_s: float = 0.0
    llm_calls: int = 1
    tool_calls: int = 0
    retries: int = 0
    tokens_generated: int = 0
    tokens_per_sec: float = 0.0
    tools_selected: list[str] = field(default_factory=list)
    raw_tasks: list[dict] = field(default_factory=list)
    response_text: str = ""
    notes: str = ""
    emitted_tool_call: bool = False
    normalized: bool = False
    validation_passed: bool = False
    tool_executed: bool = False
    physical_state_changed: bool = False
    verification_passed: bool = False
    final_response_reported: bool = False
    swe_metrics: dict[str, Any] = field(default_factory=dict)
    grounded_in_facts: bool = False


def detect_route(logs: list[str]) -> str:
    for line in logs:
        if "[PIPELINE] Conversational Fast-Path" in line:
            return "CHAT"
        if "[PIPELINE] Tool Execution" in line:
            return "TOOL"
        if "[PIPELINE] Autonomous Mission" in line:
            return "MISSION"
        if "[PIPELINE] Memory Management" in line:
            return "MEMORY"
    return "TOOL"


def run_scenario(agent, scenario_id: str, request: str) -> tuple[ScenarioResult, list[str]]:
    r = ScenarioResult(scenario_id=scenario_id)
    cap = LogCaptureHandler()
    root_logger = logging.getLogger()
    root_logger.addHandler(cap)

    t0 = time.perf_counter()
    tasks = []
    try:
        tasks = agent.run(request)
    except Exception as exc:
        r.status = "EXCEPTION"
        r.notes = str(exc)
    finally:
        r.latency_s = time.perf_counter() - t0
        root_logger.removeHandler(cap)

    logs = cap.lines
    r.route = detect_route(logs)

    for l in logs:
        m = re.search(r"\[LLM\].*calls=(\d+)", l)
        if m:
            r.llm_calls = int(m.group(1))
            break

    r.tools_selected = [f"{t.tool}.{t.action}" for t in tasks if t.tool != "system"]
    r.tool_calls = len(r.tools_selected)
    r.emitted_tool_call = len(r.tools_selected) > 0

    r.normalized = any("[NORMALIZER]" in l for l in logs) or any("repair" in l.lower() for l in logs)

    r.raw_tasks = [
        {
            "tool": t.tool,
            "action": t.action,
            "status": t.status.value if hasattr(t.status, "value") else str(t.status),
            "result": str(t.result)[:200],
            "error": t.error,
            "retry_count": getattr(t, "retry_count", 0),
        }
        for t in tasks
    ]

    r.retries = sum(getattr(t, "retry_count", 0) for t in tasks)

    # Extract response text
    for t in tasks:
        if t.tool == "system" and t.action == "respond" and t.status == TaskStatus.COMPLETED:
            r.response_text = str(t.result or t.args.get("message", ""))[:600]
            break

    if tasks:
        r.status = (
            "PARTIAL_FAIL"
            if any(t.status == TaskStatus.FAILED for t in tasks if t.tool != "system")
            else "COMPLETED"
        )
    elif r.status == "UNKNOWN":
        r.status = "NO_TASKS"

    r.tokens_generated = len(r.response_text) // 4
    if r.latency_s > 0:
        r.tokens_per_sec = round(r.tokens_generated / r.latency_s, 2)

    r.validation_passed = not any("Validation failed" in l for l in logs)
    r.tool_executed = any(t["status"] == "completed" for t in r.raw_tasks if t["tool"] != "system")

    return r, logs


def main():
    print("\n" + "=" * 70)
    print("  JARVIS PHASE 6 — RESULT GROUNDING & COMPLETION QUALITY EVALUATION")
    print("  Model: qwen3-coder:30b-a3b-q4_K_M")
    print("=" * 70)

    ctx = build_agent()
    agent = ctx["agent"]
    tmp = Path(tempfile.mkdtemp(prefix="jarvis_phase6_"))
    results: dict[str, ScenarioResult] = {}

    try:
        # 1. E-MULTI
        print("\n--> Running E-MULTI...")
        tf = tmp / "jarvis_e2e_test.txt"
        tf_fwd = str(tf).replace("\\", "/")
        r, logs = run_scenario(
            agent,
            "E-MULTI",
            f"Create a text file at '{tf_fwd}' containing exactly 'JARVIS_PHASE4_TEST', "
            f"then read it back and tell me what it contains.",
        )
        fc = tf.exists()
        cc = fc and "JARVIS_PHASE4_TEST" in tf.read_text(errors="replace")
        
        # Grounding check: response must state the creation or content fact
        resp_grounded = any(k in r.response_text.lower() for k in ["created file", "created", "jarvis_phase4_test", "done"])
        r.physical_state_changed = fc
        r.verification_passed = cc
        r.final_response_reported = resp_grounded
        r.grounded_in_facts = resp_grounded
        r.success = cc and resp_grounded
        r.verification = "PASS" if cc else "FAIL"
        r.notes = f"file_exists={fc} correct_content={cc} in_response={resp_grounded} tool_calls={r.tool_calls}"
        print(f"    E-MULTI: success={r.success} status={r.status} latency={r.latency_s:.1f}s tools={r.tools_selected}")
        print(f"    Response: {r.response_text[:120]}")
        tf.unlink(missing_ok=True)
        results["E-MULTI"] = r

        # 2. F-RECOVER
        print("\n--> Running F-RECOVER...")
        ghost = str(tmp / "definitely_not_exist_xyz.txt").replace("\\", "/")
        r, logs = run_scenario(agent, "F-RECOVER", f"Read the file at '{ghost}' and tell me what it contains.")
        fg = r.status in ("PARTIAL_FAIL", "COMPLETED") and bool(r.response_text)
        
        # Grounding check: response must report failure / unable to read, NOT claim success
        failure_reported = any(k in r.response_text.lower() for k in ["couldn't", "failed", "error", "not exist", "cannot"])
        r.physical_state_changed = False
        r.verification_passed = fg and failure_reported
        r.final_response_reported = failure_reported
        r.grounded_in_facts = failure_reported
        r.success = fg and failure_reported
        r.verification = "PASS" if r.success else "FAIL"
        r.notes = f"graceful_recovery={fg} failure_reported={failure_reported} response_len={len(r.response_text)}"
        print(f"    F-RECOVER: success={r.success} status={r.status} latency={r.latency_s:.1f}s")
        print(f"    Response: {r.response_text[:120]}")
        results["F-RECOVER"] = r

        # 3. H-SWE
        print("\n--> Running H-SWE...")
        sd = tmp / "swe_project"
        sd.mkdir(exist_ok=True)
        calc_path = sd / "calc.py"
        test_path = sd / "test_calc.py"
        calc_path.write_text("def add(a, b):\n    return a - b  # BUG\n", encoding="utf-8")
        test_path.write_text("from calc import add\ndef test_add():\n    assert add(2,3)==5\n", encoding="utf-8")

        r, logs = run_scenario(
            agent,
            "H-SWE",
            f"There is a small Python project at '{str(sd).replace(chr(92),'/')}'. "
            f"The add function in calc.py has a bug (uses subtraction instead of addition). "
            f"Fix it and report what you changed.",
        )
        calc_content = calc_path.read_text(errors="replace")
        op_changed = "a + b" in calc_content and "a - b" not in calc_content
        syntax_valid = False
        try:
            ast.parse(calc_content)
            syntax_valid = True
        except SyntaxError:
            pass

        test_run_res = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "-v"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(sd),
        )
        tests_pass_on_disk = test_run_res.returncode == 0
        tests_invoked_by_jarvis = any("test" in str(t).lower() or "pytest" in str(t).lower() for t in r.raw_tasks)
        
        # Grounding check: response must reflect the change / write action
        result_reported = any(w in r.response_text.lower() for w in ["wrote", "calc.py", "fixed", "addition", "+", "done"])

        r.physical_state_changed = op_changed
        r.verification_passed = op_changed and syntax_valid and tests_pass_on_disk
        r.final_response_reported = result_reported
        r.grounded_in_facts = result_reported
        swe_ok = op_changed and syntax_valid and tests_pass_on_disk
        r.success = swe_ok and result_reported
        r.verification = "PASS" if swe_ok else "FAIL"
        r.swe_metrics = {
            "calc_modified": op_changed,
            "operator_fixed": op_changed,
            "syntax_valid": syntax_valid,
            "tests_invoked_by_jarvis": tests_invoked_by_jarvis,
            "tests_pass_on_disk": tests_pass_on_disk,
            "result_reported": result_reported,
        }
        r.notes = f"fixed={op_changed} syntax={syntax_valid} disk_tests_pass={tests_pass_on_disk} reported={result_reported}"
        print(f"    H-SWE: success={r.success} op_fixed={op_changed} tests_pass={tests_pass_on_disk} latency={r.latency_s:.1f}s")
        print(f"    Response: {r.response_text[:120]}")
        shutil.rmtree(sd, ignore_errors=True)
        results["H-SWE"] = r

        # 4. L-VERIFY
        print("\n--> Running L-VERIFY...")
        gout = tmp / "mission_out.txt"
        r, logs = run_scenario(
            agent,
            "L-VERIFY",
            f"Create a file at '{str(gout).replace(chr(92),'/')}' with exact content 'MISSION_COMPLETE_MARKER'.",
        )
        verifier = MissionCompletionVerifier()
        jts = []
        for td in r.raw_tasks:
            jt = JT(tool=td["tool"], action=td["action"], args={})
            jt.start()
            if td["status"] == "completed":
                jt.complete(td["result"])
            else:
                jt.fail(td.get("error", "unknown"))
            jts.append(jt)
        vr = verifier.verify(tasks=jts, response_text=r.response_text, expected_files=[str(gout)])
        fe = gout.exists()
        cc3 = fe and "MISSION_COMPLETE_MARKER" in gout.read_text(errors="replace")
        
        # Grounding check: response must confirm creation
        resp_grounded_l = any(k in r.response_text.lower() for k in ["created file", "mission_out.txt", "done"])
        r.physical_state_changed = fe
        r.verification_passed = cc3
        r.final_response_reported = resp_grounded_l
        r.grounded_in_facts = resp_grounded_l
        r.success = cc3 and resp_grounded_l
        r.verification = vr.status.value.upper()
        r.notes = f"file_exists={fe} correct_content={cc3} verifier={vr.status.value}"
        print(f"    L-VERIFY: success={r.success} file_created={fe} content_correct={cc3} latency={r.latency_s:.1f}s")
        print(f"    Response: {r.response_text[:120]}")
        if fe:
            gout.unlink(missing_ok=True)
        results["L-VERIFY"] = r

        # 5. N-ESCALATE
        print("\n--> Running N-ESCALATE...")
        sd3 = tmp / "escalation"
        sd3.mkdir(exist_ok=True)
        (sd3 / "main.py").write_text("def greet(n):\n    return f'Hello, {n}!'\n", encoding="utf-8")
        (sd3 / "test_main.py").write_text(
            "from main import greet\ndef test_greet():\n    assert greet('World')=='Hello, World!'\n",
            encoding="utf-8",
        )
        r, logs = run_scenario(
            agent,
            "N-ESCALATE",
            f"Can you figure out what is going on with the project at '{str(sd3).replace(chr(92),'/')}' and tell me if the tests pass?",
        )
        r.physical_state_changed = False
        r.verification_passed = r.status != "EXCEPTION"
        resp_grounded_n = any(k in r.response_text.lower() for k in ["main.py", "contents", "done", "list", "test"])
        r.final_response_reported = resp_grounded_n
        r.grounded_in_facts = resp_grounded_n
        r.success = r.status != "EXCEPTION" and resp_grounded_n
        r.verification = "PASS" if r.success else "FAIL"
        r.notes = f"route={r.route} status={r.status} response_len={len(r.response_text)}"
        print(f"    N-ESCALATE: success={r.success} status={r.status} latency={r.latency_s:.1f}s")
        print(f"    Response: {r.response_text[:120]}")
        shutil.rmtree(sd3, ignore_errors=True)
        results["N-ESCALATE"] = r

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # Save output JSON
    out_file = PROJECT_ROOT / "docs" / "architecture" / "evaluation" / "phase6_scenario_results.json"
    data = {}
    for sid, r in results.items():
        data[sid] = {
            "scenario_id": r.scenario_id,
            "route": r.route,
            "status": r.status,
            "success": r.success,
            "verification": r.verification,
            "latency_s": round(r.latency_s, 2),
            "llm_calls": r.llm_calls,
            "tool_calls": r.tool_calls,
            "retries": r.retries,
            "tokens_generated": r.tokens_generated,
            "tokens_per_sec": r.tokens_per_sec,
            "tools_selected": r.tools_selected,
            "raw_tasks": r.raw_tasks,
            "response": r.response_text,
            "notes": r.notes,
            "emitted_tool_call": r.emitted_tool_call,
            "normalized": r.normalized,
            "validation_passed": r.validation_passed,
            "tool_executed": r.tool_executed,
            "physical_state_changed": r.physical_state_changed,
            "verification_passed": r.verification_passed,
            "final_response_reported": r.final_response_reported,
            "grounded_in_facts": r.grounded_in_facts,
            "swe_metrics": r.swe_metrics,
        }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"\n[OK] Phase 6 Scenario Results saved to: {out_file}")


if __name__ == "__main__":
    main()
