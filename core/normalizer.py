def normalize(plan):

    if isinstance(plan, list):
        return [normalize(step) for step in plan]

    tool_map = {
        "application": "windows",
        "app": "windows",
        "desktop": "windows",
        "program": "windows",
        "windows": "windows"
    }

    action_map = {
        "open": "open_app",
        "launch": "open_app",
        "start": "open_app",
        "open_app": "open_app"
    }

    if "tool" in plan:
        plan["tool"] = tool_map.get(plan["tool"].lower(), plan["tool"].lower())

    if "action" in plan:
        plan["action"] = action_map.get(plan["action"].lower(), plan["action"].lower())

    if "args" in plan:

        args = plan["args"]

        if "name" in args:
            args["app"] = args.pop("name").lower()

        if "program" in args:
            args["app"] = args.pop("program").lower()

    return plan
