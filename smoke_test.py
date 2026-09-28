from core.agent import Agent
from core.bootstrap.bootstrapper import Bootstrap


def main() -> None:
    print("Starting Bootstrapper...")
    result = Bootstrap.start()
    if not result.success or result.runtime is None:
        print(f"Failed to start: {result.error_message}")
        return

    runtime = result.runtime
    print("Bootstrapper finished.")

    agent = runtime.container.resolve(Agent)
    commands = [
        "hello",
        "open notepad",
        "open calculator",
        "create file test.txt",
        "search python",
        "remember my favorite editor is VS Code",
    ]

    for cmd in commands:
        print(f"\n--- Testing command: {cmd} ---")
        try:
            tasks = agent.run(cmd)
            print(f"Tasks generated: {len(tasks)}")
            for t in tasks:
                print(f"Task status: {t.status}")
        except (OSError, RuntimeError, ValueError) as e:
            print(f"Exception during {cmd}: {e}")

    print("\nShutting down runtime...")
    # Stop usually happens async or via some runtime manager but we're just testing the boot and agent
    print("Shutdown complete.")


if __name__ == "__main__":
    main()
