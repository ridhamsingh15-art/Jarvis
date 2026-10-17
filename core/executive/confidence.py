class ConfidenceEstimator:
    def estimate(self, data_points: int, historical_success: float) -> float:
        if data_points == 0:
            return 0.1
        base = historical_success
        bonus = min(data_points * 0.05, 0.4)
        return min(base + bonus, 1.0)
