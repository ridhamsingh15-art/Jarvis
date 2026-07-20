from core.registry import get_tool


def execute(plan):

    # Handle multiple actions
    if isinstance(plan, list):

        results = []

        for step in plan:
            result = execute(step)
            results.append(result)

        return "\n".join(results)

    # Handle normal chat
    if plan["tool"] == "none":
        return plan["args"]["message"]

    tool = get_tool(plan["tool"])

    if tool is None:
        return f"Unknown tool: {plan['tool']}"

    return tool(
        plan["action"],
        plan["args"]
    )
