from skills.windows import open_app

def execute(plan):

    tool = plan["tool"]

    if tool == "windows":

        action = plan["action"]

        if action == "open_app":
            return open_app(plan["args"]["app"])

    if tool == "none":
        return plan["args"]["message"]

    return "Unknown tool."
