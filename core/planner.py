from core.registry import TOOLS


def build_system_prompt():

    prompt = """
You are Jarvis.

You must ONLY use the tools listed below.

Return ONLY valid JSON.

Schema:

{
  "tool":"",
  "action":"",
  "args":{}
}

For multiple actions return a JSON array.
"""

    prompt += "\n\nAvailable Tools:\n"

    for tool_name, tool in TOOLS.items():

        prompt += f"\nTool: {tool_name}\n"
        prompt += f"Description: {tool['description']}\n"

        for action, values in tool["actions"].items():

            prompt += f"\nAction: {action}\n"

            for value in values:
                prompt += f"  - {value}\n"

    return prompt