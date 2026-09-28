with open('core/tool_feedback_loop.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = """            if all_succeeded:
                logger.info(
                    "[TOOL_LOOP] request_id=%s completed successfully on iteration %d",
                    request_id, iteration,
                )
                return ToolLoopResult(
                    tasks=executed,
                    iterations_used=iteration,
                    succeeded=True,
                    iterations=iterations_log,
                )"""

new_block = """            if all_succeeded:
                logger.info(
                    "[TOOL_LOOP] request_id=%s completed successfully on iteration %d",
                    request_id, iteration,
                )
                from core.execution_summary import ExecutionSummary
                summary = ExecutionSummary.from_tasks(executed)
                for t in executed:
                    if t.tool == "system" and t.action == "respond":
                        t.result = summary.ground_response(str(t.result or t.args.get("message", "")))
                return ToolLoopResult(
                    tasks=executed,
                    iterations_used=iteration,
                    succeeded=True,
                    iterations=iterations_log,
                )"""

assert old_block in text, "old_block not found in tool_feedback_loop.py"
text = text.replace(old_block, new_block, 1)

with open('core/tool_feedback_loop.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)
print("Updated tool_feedback_loop.py with grounding")
