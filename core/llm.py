from ollama import chat
import json

MODEL = "qwen3:8b"

SYSTEM_PROMPT = """
You are Jarvis.

Always answer ONLY with valid JSON.

Schema:

{
  "tool": "",
  "action": "",
  "args": {}
}

Examples:

Open Notepad

{
 "tool":"windows",
 "action":"open_app",
 "args":{
   "app":"notepad"
 }
}

Open Calculator

{
 "tool":"windows",
 "action":"open_app",
 "args":{
   "app":"calculator"
 }
}

If no tool is required:

{
 "tool":"none",
 "action":"chat",
 "args":{
   "message":"..."
 }
}
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

    return json.loads(response.message.content)
