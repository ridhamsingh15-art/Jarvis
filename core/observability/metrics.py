import threading


class Gauge:
    def __init__(self, name: str):
        self.name = name
        self.value: float = 0.0

    def set(self, val: float) -> None:
        self.value = val

class Counter:
    def __init__(self, name: str):
        self.name = name
        self.value: int = 0

    def inc(self, val: int = 1) -> None:
        self.value += val

class Histogram:
    def __init__(self, name: str):
        self.name = name
        self.values: list[float] = []

    def observe(self, val: float) -> None:
        self.values.append(val)

class MetricsRegistry:
    def __init__(self) -> None:
        self.gauges: dict[str, Gauge] = {}
        self.counters: dict[str, Counter] = {}
        self.histograms: dict[str, Histogram] = {}
        self._lock = threading.Lock()

    def get_gauge(self, name: str) -> Gauge:
        with self._lock:
            if name not in self.gauges:
                self.gauges[name] = Gauge(name)
            return self.gauges[name]

    def get_counter(self, name: str) -> Counter:
        with self._lock:
            if name not in self.counters:
                self.counters[name] = Counter(name)
            return self.counters[name]

    def get_histogram(self, name: str) -> Histogram:
        with self._lock:
            if name not in self.histograms:
                self.histograms[name] = Histogram(name)
            return self.histograms[name]
