from core.llm import plan
from core.executor import execute

print("="*40)
print("Jarvis AI v1.0")
print("="*40)

while True:

    prompt = input("\nYou: ")

    if prompt.lower() == "exit":
        break

    task = plan(prompt)

    print("\nPlan:", task)

    result = execute(task)

    print("\nJarvis:", result)
