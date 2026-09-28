import os
import sys
import tempfile
import time

# Ensure imports work from the project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.agent import Agent
from core.task import TaskStatus
from main import build_agent


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def assert_result(description: str, condition: bool):
    if condition:
        print(f"[\033[92mPASS\033[0m] {description}")
    else:
        print(f"[\033[91mFAIL\033[0m] {description}")
        sys.exit(1)

def run_scenario(agent: Agent, prompt: str) -> list:
    print(f"\nUser > {prompt}")
    start = time.time()
    results = agent.run(prompt)
    elapsed = time.time() - start
    
    for r in results:
        status_str = r.status.value if hasattr(r.status, "value") else str(r.status)
        if r.status == TaskStatus.COMPLETED:
            print(f"  [{status_str}] {r.result}")
        elif r.status == TaskStatus.FAILED:
            print(f"  [{status_str}] {r.error}")
        else:
            print(f"  [{status_str}] {r.tool}.{r.action}")
            
    print(f"(Took {elapsed:.2f}s)")
    return results

def main():
    print_header("JARVIS AIOS - Live End-to-End Verification")
    
    # Bootstrap JARVIS (pulls from JARVIS_PROVIDER env var)
    print("Bootstrapping JARVIS...")
    ctx = build_agent()
    agent: Agent = ctx["agent"]
    config = ctx["config"]
    print(f"Configured Provider: {config.provider}")
    print(f"Configured Model: {config.model}")
    print(f"Active Tools: {ctx['tool_count']}")
    
    # ---------------------------------------------------------
    # SCENARIO 1: Identity & Cognition
    # ---------------------------------------------------------
    print_header("Scenario 1: Identity & Cognition")
    res = run_scenario(agent, "Who are you and what model are you running?")
    assert_result("Agent returned a response", len(res) > 0)
    
    reply = res[0].result.lower()
    assert_result("Guardrails active (identifies as JARVIS)", "jarvis" in reply)
    assert_result("Model disclosure active", config.model.lower() in reply)
    
    # ---------------------------------------------------------
    # SCENARIO 2: Tool Execution (File System)
    # ---------------------------------------------------------
    print_header("Scenario 2: Tool Execution (File System)")
    test_file = os.path.join(tempfile.gettempdir(), "jarvis_e2e_test.txt")
    
    # Ensure clean state
    if os.path.exists(test_file):
        os.remove(test_file)
        
    test_file_fwd = test_file.replace("\\", "/")
    res = run_scenario(agent, f"Create a text file at '{test_file_fwd}' with the exact contents 'E2E_TEST_SUCCESS'.")
    assert_result("Agent executed action", len(res) > 0)
    assert_result("Task completed successfully", res[0].status == TaskStatus.COMPLETED)
    assert_result("File was actually created on disk", os.path.exists(test_file))
    
    with open(test_file, "r") as f:
        content = f.read().strip()
    assert_result("File contains correct content", "E2E_TEST_SUCCESS" in content)
    
    # ---------------------------------------------------------
    # SCENARIO 3: Multi-step Planning
    # ---------------------------------------------------------
    print_header("Scenario 3: Multi-step Planning")
    # Ask a question that requires reading a file we just made
    res = run_scenario(agent, f"Read the file I just asked you to create at '{test_file_fwd}' and tell me what the content is.")
    assert_result("Agent planned and executed", len(res) >= 1)
    
    # Usually planning might result in multiple tasks (read file + respond), or a single task that incorporates the answer
    # As long as the agent didn't fail, and successfully found the file.
    combined_results = " ".join([r.result for r in res if r.result])
    assert_result("Agent successfully retrieved file contents", "E2E_TEST_SUCCESS" in combined_results)
    
    # ---------------------------------------------------------
    # SCENARIO 4: Memory Layer
    # ---------------------------------------------------------
    print_header("Scenario 4: Memory Layer")
    res = run_scenario(agent, "My favorite color is neon magenta. Please remember this.")
    assert_result("Agent acknowledged memory storage", res[0].status == TaskStatus.COMPLETED)
    
    res = run_scenario(agent, "What did I say my favorite color was?")
    reply = res[0].result.lower()
    assert_result("Agent recalled fact from memory", "magenta" in reply)
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)
        
    print_header("ALL E2E VERIFICATIONS PASSED")

if __name__ == "__main__":
    main()
