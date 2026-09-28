from typing import Any

from .project import ProjectState


class TestHarness:
    def run_tests(self, state: ProjectState) -> dict[str, Any]:
        # Mock tests output
        if "fail_test" in state.objective:
            return {"success": False, "error": "SyntaxError in main.py"}
        return {"success": True, "error": None}

    def repair_loop(self, state: ProjectState, max_retries: int = 3) -> bool:
        for attempt in range(max_retries):
            result = self.run_tests(state)
            if result["success"]:
                return True
            # Mock generating fix
            state.objective = state.objective.replace("fail_test", "fixed_test")
        return False
