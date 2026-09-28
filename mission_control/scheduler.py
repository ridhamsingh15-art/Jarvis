import asyncio


class MissionScheduler:
    def __init__(self) -> None:
        self.tasks: list[asyncio.Task] = []

    def schedule(self, coro) -> None: # type: ignore
        loop = asyncio.get_running_loop()
        task = loop.create_task(coro)
        self.tasks.append(task)
