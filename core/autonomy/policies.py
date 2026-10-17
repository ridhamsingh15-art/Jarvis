from .interfaces import IRetryPolicy


class LinearRetryPolicy(IRetryPolicy):
    """Maps linear intervals."""
    def get_delay(self, current_retry: int) -> float:
        return float(current_retry * 2)

class ExponentialBackoffPolicy(IRetryPolicy):
    """Maps exponentially increasing intervals."""
    def get_delay(self, current_retry: int) -> float:
        return float(2 ** current_retry)
