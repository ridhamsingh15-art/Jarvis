from tools.windows import execute as windows_execute

TOOLS = {
    "windows": windows_execute,
}

def get_tool(name):
    return TOOLS.get(name)
