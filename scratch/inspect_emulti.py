import sys, os
sys.path.insert(0, ".")
os.environ["JARVIS_MODEL"] = "qwen3-coder:30b-a3b-q4_K_M"

import logging
logging.basicConfig(level=logging.INFO)
from main import build_agent

ctx = build_agent()
agent = ctx["agent"]
res = agent.run("Create a text file at 'C:/Users/ridha/AppData/Local/Temp/test.txt' containing exactly 'JARVIS_PHASE4_TEST', then read it back and tell me what it contains.")
for t in res:
    print("TASK:", t.tool, t.action, t.args, t.status, t.error)
