from ollama import chat
from core.parser import parse_json
from core.normalizer import normalize

MODEL = "qwen3:8b"

SYSTEM_PROMPT = """
You are Jarvis.

Return ONLY valid JSON.

Single action:

{
  "tool": "",
  "action": "",
  "args": {}
}

Multiple actions:

[
  {
    "tool":"",
    "action":"",
    "args":{}
  }
]

Never explain.
Never use markdown.
Never use ```json.
Only output JSON.
"""

def plan(prompt: str):

    response = chat(
        model=MODEL,
        messages=[
            {
                "role":"system",
                "content":SYSTEM_PROMPT
            },
            {
                "role":"user",
                "content":prompt
            }
        ]
    )

    return normalize(parse_json(response.message.content))
