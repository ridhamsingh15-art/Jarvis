with open('core/execution_summary.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    "return self.status in (TaskStatus.PENDING, TaskStatus.CANCELLED)",
    "return self.status in (TaskStatus.PENDING, TaskStatus.RETRYING)",
)

with open('core/execution_summary.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)
print("Updated skipped property in execution_summary.py")
