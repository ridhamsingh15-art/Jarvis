class MissionAnalytics:
    def __init__(self) -> None:
        self.completed = 0
        self.failed = 0

    def record_completion(self) -> None:
        self.completed += 1

    def record_failure(self) -> None:
        self.failed += 1

    def success_rate(self) -> float:
        total = self.completed + self.failed
        if total == 0:
            return 1.0
        return self.completed / total
