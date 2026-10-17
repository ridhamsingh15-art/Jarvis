import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationCase:
    """A single input/expected-output evaluation pair."""

    id: str
    category: str
    input_data: str
    expected_output: str
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class BenchmarkDataset:
    """Immutable collection of evaluation cases for a named benchmark."""

    name: str
    category: str
    cases: tuple[EvaluationCase, ...] = ()


class DatasetRegistry:
    """Thread-safe registry for benchmark datasets."""

    def __init__(self) -> None:
        self._datasets: dict[str, BenchmarkDataset] = {}
        self._lock = threading.RLock()

    def register(self, dataset: BenchmarkDataset) -> None:
        with self._lock:
            self._datasets[dataset.name] = dataset

    def get(self, name: str) -> BenchmarkDataset | None:
        with self._lock:
            return self._datasets.get(name)

    def get_by_category(self, category: str) -> list[BenchmarkDataset]:
        with self._lock:
            return [d for d in self._datasets.values() if d.category == category]

    def all_datasets(self) -> list[BenchmarkDataset]:
        with self._lock:
            return list(self._datasets.values())

    def categories(self) -> list[str]:
        with self._lock:
            return list({d.category for d in self._datasets.values()})


def build_default_datasets() -> list[BenchmarkDataset]:
    """Constructs the built-in benchmark datasets for all evaluation categories."""
    return [
        BenchmarkDataset(
            name="reasoning_basic",
            category="reasoning",
            cases=(
                EvaluationCase(id="r1", category="reasoning", input_data="What is 2+2?", expected_output="4"),
                EvaluationCase(id="r2", category="reasoning", input_data="If A implies B and A is true, what is B?", expected_output="true"),
            ),
        ),
        BenchmarkDataset(
            name="planning_basic",
            category="planning",
            cases=(
                EvaluationCase(id="p1", category="planning", input_data="Create a 3-step plan to build a CLI tool", expected_output="plan"),
                EvaluationCase(id="p2", category="planning", input_data="Order these tasks: test, implement, design", expected_output="design,implement,test"),
            ),
        ),
        BenchmarkDataset(
            name="coding_basic",
            category="coding",
            cases=(
                EvaluationCase(id="c1", category="coding", input_data="Write a Python function to reverse a string", expected_output="def reverse"),
                EvaluationCase(id="c2", category="coding", input_data="Fix: def add(a, b): return a - b", expected_output="return a + b"),
            ),
        ),
        BenchmarkDataset(
            name="memory_basic",
            category="memory",
            cases=(
                EvaluationCase(id="m1", category="memory", input_data="Store and retrieve key 'user_name'", expected_output="retrieved"),
                EvaluationCase(id="m2", category="memory", input_data="Search memory for 'project deadline'", expected_output="found"),
            ),
        ),
        BenchmarkDataset(
            name="mission_basic",
            category="mission",
            cases=(
                EvaluationCase(id="ms1", category="mission", input_data="Complete a 3-step mission", expected_output="COMPLETED"),
                EvaluationCase(id="ms2", category="mission", input_data="Recover a crashed mission", expected_output="RECOVERED"),
            ),
        ),
        BenchmarkDataset(
            name="workspace_basic",
            category="workspace",
            cases=(
                EvaluationCase(id="w1", category="workspace", input_data="Detect active window", expected_output="detected"),
                EvaluationCase(id="w2", category="workspace", input_data="Snapshot workspace state", expected_output="snapshot_created"),
            ),
        ),
        BenchmarkDataset(
            name="knowledge_basic",
            category="knowledge",
            cases=(
                EvaluationCase(id="k1", category="knowledge", input_data="Search for Python asyncio docs", expected_output="found"),
                EvaluationCase(id="k2", category="knowledge", input_data="Retrieve chunked document", expected_output="chunks_returned"),
            ),
        ),
        BenchmarkDataset(
            name="internet_basic",
            category="internet",
            cases=(
                EvaluationCase(id="i1", category="internet", input_data="Search for latest Python release", expected_output="results"),
                EvaluationCase(id="i2", category="internet", input_data="Crawl documentation page", expected_output="content_extracted"),
            ),
        ),
        BenchmarkDataset(
            name="tool_usage_basic",
            category="tool_usage",
            cases=(
                EvaluationCase(id="t1", category="tool_usage", input_data="Execute git commit", expected_output="committed"),
                EvaluationCase(id="t2", category="tool_usage", input_data="Run pytest on project", expected_output="tests_passed"),
            ),
        ),
        BenchmarkDataset(
            name="voice_basic",
            category="voice",
            cases=(
                EvaluationCase(id="v1", category="voice", input_data="Transcribe audio sample", expected_output="transcribed"),
            ),
        ),
        BenchmarkDataset(
            name="vision_basic",
            category="vision",
            cases=(
                EvaluationCase(id="vi1", category="vision", input_data="Describe screenshot", expected_output="description"),
            ),
        ),
        BenchmarkDataset(
            name="collaboration_basic",
            category="collaboration",
            cases=(
                EvaluationCase(id="co1", category="collaboration", input_data="Coordinate 3 agents on a task", expected_output="coordinated"),
            ),
        ),
    ]
