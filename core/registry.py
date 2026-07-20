from tools.windows import execute

TOOLS = {
    "windows": {
        "description": "Control Windows applications",

        "actions": {
            "open_app": [
                "notepad",
                "calculator",
                "paint",
                "cmd"
            ]
        },

        "execute": execute
    }
}


def get_tool(name):

    if name not in TOOLS:
        return None

    return TOOLS[name]["execute"]