with open('core/agent.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_call = """            for task in resp_tasks:
                res = self._process_task(task, execution_summary=summary)
                results_by_id[id(task)] = res"""

new_call = """            for task in resp_tasks:
                try:
                    res = self._process_task(task, execution_summary=summary)
                except TypeError:
                    res = self._process_task(task)
                results_by_id[id(task)] = res"""

assert old_call in text, "old_call not found in agent.py"
text = text.replace(old_call, new_call, 1)

with open('core/agent.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)
print("Updated agent.py with graceful _process_task fallback")
