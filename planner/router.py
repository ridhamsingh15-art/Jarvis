from tools.windows import open_app
from core.llm import ask

def handle(prompt: str):
    text = prompt.lower()

    if text.startswith("open "):
        app = text.replace("open ", "").strip()
        return open_app(app)

    return ask(prompt)
