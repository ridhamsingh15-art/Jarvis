"""
Live Verification Script for JARVIS Second-Pass Routing & Acceptance.
Runs real Agent through main.build_agent() with full logging enabled.
"""
import logging
import os
import sys
import time

# Ensure imports work from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure logging to console so we see all exact logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

from main import build_agent
from core.agent import Agent
from core.task import TaskStatus

def main():
    print("=" * 80)
    print("  JARVIS AIOS - CRITICAL SECOND-PASS LIVE VERIFICATION")
    print("=" * 80)

    print("\nBootstrapping real JARVIS runtime via build_agent()...")
    ctx = build_agent()
    agent: Agent = ctx["agent"]

    test_inputs = [
        # 1. CHAT - fast greeting
        "Hi",
        # 2. CHAT - conversational explanation
        "Why do people enjoy watching documentaries?",
        # 3. MEMORY - fact storage
        "Remember that my favorite IDE is Antigravity.",
        # 4. MEMORY - contextual recall
        "What did I just tell you?",
        # 5. TOOL - OS app execution
        "Open the calculator",
        # 6. TOOL - browser navigation
        "Open GitHub",
        # 7. MISSION - complex research & generation
        "Research the history of artificial intelligence and give me a detailed report",
    ]

    for idx, prompt in enumerate(test_inputs, 1):
        print("\n" + "#" * 80)
        print(f"  TEST CASE {idx}: \"{prompt}\"")
        print("#" * 80)
        start = time.time()
        results = agent.run(prompt)
        elapsed = time.time() - start

        print(f"\n--- Output Tasks ({len(results)}) ---")
        for r in results:
            print(f"  [{r.status.value}] tool={r.tool}, action={r.action}, args={r.args}")
            if r.result:
                print(f"    -> Result: {r.result}")
            if r.error:
                print(f"    -> Error: {r.error}")
        print(f"--- Completed in {elapsed:.3f}s ---\n")

if __name__ == "__main__":
    main()
