with open('core/agent.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add import of ExecutionSummary
old_import = "from core.validator import Validator"
new_import = "from core.validator import Validator\nfrom core.execution_summary import ExecutionSummary"
assert old_import in text, "old_import not found"
text = text.replace(old_import, new_import, 1)

# 2. Add self._last_execution_summary in __init__
old_init = "self._semantic_search_disabled = False"
new_init = """self._semantic_search_disabled = False
        self._last_execution_summary: ExecutionSummary | None = None"""
assert old_init in text, "old_init not found"
text = text.replace(old_init, new_init, 1)

# 3. Add last_execution_summary property
old_prop_target = "    def run("
new_prop_target = """    @property
    def last_execution_summary(self) -> ExecutionSummary | None:
        \"\"\"Return the ExecutionSummary from the most recent run() execution.\"\"\"
        return self._last_execution_summary

    def run("""
assert old_prop_target in text, "old_prop_target not found"
text = text.replace(old_prop_target, new_prop_target, 1)

# 4. Update execution loop in run() to build summary and ground response tasks
old_loop = """            for task in resp_tasks:
                res = self._process_task(task)
                results_by_id[id(task)] = res"""

new_loop = """            # Phase 6: Build ExecutionSummary from executed non-system tools
            executed_tools = [results_by_id.get(id(t), t) for t in exec_tasks]
            summary = ExecutionSummary.from_tasks(executed_tools)
            self._last_execution_summary = summary

            for task in resp_tasks:
                res = self._process_task(task, execution_summary=summary)
                results_by_id[id(task)] = res"""
assert old_loop in text, "old_loop not found"
text = text.replace(old_loop, new_loop, 1)

# 5. Update _process_task definition and handling of system.respond
old_proc = """    def _process_task(self, task: Task) -> Task:
        \"\"\"Validate and execute a single task.

        Args:
            task: A Task in PENDING state.

        Returns:
            The Task with updated status after execution.
        \"\"\"
        # Handle conversational responses from the LLM directly —
        # these don't go through validation or execution.
        if task.tool == "system" and task.action == "respond":
            raw_msg = (
                task.args.get("message")
                or task.args.get("content")
                or task.args.get("response")
                or task.args.get("text")
                or ""
            )
            message = str(raw_msg)
            if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                task.start()
            task.complete(message)
            return task"""

new_proc = """    def _process_task(
        self,
        task: Task,
        execution_summary: ExecutionSummary | None = None,
    ) -> Task:
        \"\"\"Validate and execute a single task.

        Args:
            task: A Task in PENDING state.
            execution_summary: Optional ExecutionSummary to ground response tasks.

        Returns:
            The Task with updated status after execution.
        \"\"\"
        # Handle conversational responses from the LLM directly —
        # these don't go through validation or execution.
        if task.tool == "system" and task.action == "respond":
            raw_msg = (
                task.args.get("message")
                or task.args.get("content")
                or task.args.get("response")
                or task.args.get("text")
                or ""
            )
            initial_claim = str(raw_msg)
            if execution_summary is not None and execution_summary.total_tasks > 0:
                final_message = execution_summary.ground_response(initial_claim)
            else:
                final_message = initial_claim

            if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                task.start()
            task.complete(final_message)
            return task"""
assert old_proc in text, "old_proc not found"
text = text.replace(old_proc, new_proc, 1)

with open('core/agent.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)
print("Successfully updated core/agent.py with ExecutionSummary and Grounding")
