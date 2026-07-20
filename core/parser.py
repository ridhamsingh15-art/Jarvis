import json
import re


def parse_json(text):

    # Remove markdown code fences
    text = re.sub(r"```json", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "").strip()

    # Find first JSON object or array
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)

    if not match:
        raise ValueError("No JSON found.")

    return json.loads(match.group(1))
