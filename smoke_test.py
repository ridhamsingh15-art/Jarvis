"""Safe smoke test for the currently wired AIOS runtime. No desktop actions are triggered."""
from core.autonomy import AutonomousGoalManager
from core.bootstrap.bootstrapper import Bootstrap


def main() -> int:
    print("Starting JARVIS AIOS bootstrap...")
    result = Bootstrap.start()
    if not result.success or result.runtime is None:
        print(f"BOOTSTRAP=FAILED reason={result.error_message}")
        return 1

    runtime = result.runtime
    try:
        manager = runtime.container.resolve(AutonomousGoalManager)
        print("BOOTSTRAP=PASS")
        print(f"RUNTIME={type(runtime).__name__}")
        print(f"AUTONOMY_MANAGER={type(manager).__name__}")
        print("SMOKE_TEST=PASS; no external or state-changing actions were executed")
        return 0
    except (KeyError, RuntimeError, TypeError, ValueError) as exc:
        print(f"SMOKE_TEST=FAILED error={type(exc).__name__}: {exc}")
        return 1
    finally:
        runtime.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
