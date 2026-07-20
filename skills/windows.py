import subprocess

def open_app(app_name: str):
    apps = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "paint": "mspaint.exe",
        "cmd": "cmd.exe",
    }

    app = apps.get(app_name.lower())

    if app:
        subprocess.Popen(app)
        return f"Opening {app_name}."
    else:
        return f"I don't know how to open '{app_name}' yet."
