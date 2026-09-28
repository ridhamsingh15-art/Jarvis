import threading
from dataclasses import dataclass


@dataclass
class LeaderboardEntry:
    """A single entry on the leaderboard."""

    name: str
    category: str
    score: float


class Leaderboard:
    """Thread-safe leaderboard ranking providers, planners, prompts, reasoning
    strategies, coding agents, and mission strategies by aggregated scores."""

    def __init__(self) -> None:
        self._entries: list[LeaderboardEntry] = []
        self._lock = threading.RLock()

    def submit(self, name: str, category: str, score: float) -> None:
        with self._lock:
            self._entries.append(LeaderboardEntry(name=name, category=category, score=score))

    def top(self, category: str, limit: int = 5) -> list[LeaderboardEntry]:
        with self._lock:
            filtered = [e for e in self._entries if e.category == category]
            filtered.sort(key=lambda e: e.score, reverse=True)
            return filtered[:limit]

    def best(self, category: str) -> LeaderboardEntry | None:
        results = self.top(category, limit=1)
        if results:
            return results[0]
        return None

    def all_categories(self) -> list[str]:
        with self._lock:
            return list({e.category for e in self._entries})

    def all_entries(self) -> list[LeaderboardEntry]:
        with self._lock:
            return list(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
