with open('core/execution_summary.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_fail = """    def _build_failure_response(self, initial_claim: str) -> str:
        \"\"\"Build response when all tools failed (model claims of success are discarded).\"\"\"
        if len(self.failed) == 1:
            rec = self.failed[0]
            err = rec.error or "an error occurred"
            return f"I couldn't complete {rec.tool}.{rec.action}: {err}"

        items = [f"{r.tool}.{r.action}: {r.error or 'Failed'}" for r in self.failed]
        return "I couldn't complete the requested actions:\\n" + "\\n".join(f"- {it}" for it in items)

    def _build_partial_response(self, initial_claim: str) -> str:
        \"\"\"Build response for partial multi-tool execution.\"\"\"
        lines = ["Partially completed:"]
        if self.completed:
            succeeded_str = ", ".join(self._format_task_summary(r) for r in self.completed)
            lines.append(f"Completed: {succeeded_str}")
        if self.failed:
            failed_str = ", ".join(f"{r.tool}.{r.action} ({r.error or 'Failed'})" for r in self.failed)
            lines.append(f"Failed: {failed_str}")
        if self.skipped:
            skipped_str = ", ".join(f"{r.tool}.{r.action}" for r in self.skipped)
            lines.append(f"Not executed: {skipped_str}")
        return "\\n".join(lines)"""

new_fail = """    def _build_failure_response(self, initial_claim: str) -> str:
        \"\"\"Build response when all tools failed (model claims of success are discarded).\"\"\"
        if len(self.failed) == 1:
            rec = self.failed[0]
            err = rec.error or "an error occurred"
            target = rec.args.get("path") or rec.args.get("filepath") or rec.args.get("app")
            target_str = f" on '{target}'" if target else ""
            return f"I couldn't complete {rec.tool}.{rec.action}{target_str}: {err}"

        items = []
        for r in self.failed:
            target = r.args.get("path") or r.args.get("filepath") or r.args.get("app")
            target_str = f" on '{target}'" if target else ""
            items.append(f"{r.tool}.{r.action}{target_str}: {r.error or 'Failed'}")
        return "I couldn't complete the requested actions:\\n" + "\\n".join(f"- {it}" for it in items)

    def _build_partial_response(self, initial_claim: str) -> str:
        \"\"\"Build response for partial multi-tool execution.\"\"\"
        lines = ["Partially completed:"]
        if self.completed:
            succeeded_str = ", ".join(self._format_task_summary(r) for r in self.completed)
            lines.append(f"Completed: {succeeded_str}")
        if self.failed:
            failed_items = []
            for r in self.failed:
                target = r.args.get("path") or r.args.get("filepath") or r.args.get("app")
                target_str = f" on '{target}'" if target else ""
                failed_items.append(f"{r.tool}.{r.action}{target_str} ({r.error or 'Failed'})")
            lines.append(f"Failed: {', '.join(failed_items)}")
        if self.skipped:
            skipped_str = ", ".join(f"{r.tool}.{r.action}" for r in self.skipped)
            lines.append(f"Not executed: {skipped_str}")
        return "\\n".join(lines)"""

assert old_fail in text, "old_fail not found"
text = text.replace(old_fail, new_fail, 1)

with open('core/execution_summary.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)
print("Updated failure and partial responses in execution_summary.py")
