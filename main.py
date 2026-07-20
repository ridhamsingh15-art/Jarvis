from core.agent import Agent

agent = Agent()

print("=" * 40)
print("Jarvis AI v2")
print("=" * 40)

while True:

    prompt = input("\nYou: ")

    if prompt.lower() == "exit":
        break

    try:

        results = agent.run(prompt)

        for result in results:
            print("Jarvis:", result)

    except Exception as e:
        print("Error:", e)