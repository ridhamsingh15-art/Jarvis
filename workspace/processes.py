class ProcessTracker:
    def get_running_processes(self) -> list[str]:
        # Mocks psutil for deterministic enterprise tests
        return ["code.exe", "chrome.exe", "explorer.exe"]
