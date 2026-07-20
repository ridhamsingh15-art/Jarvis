import subprocess

APPS = {
    "notepad": "notepad",
    "calculator": "calc",
    "paint": "mspaint",
    "cmd": "cmd"
}


def open_app(app):

    app = app.lower()

    if app in APPS:
        subprocess.Popen(APPS[app])
        return f"Opened {app}"

    return f"Unknown app: {app}"


def execute(action, args):

    if action == "open_app":
        return open_app(args["app"])

    return f"Unknown Windows action: {action}"
