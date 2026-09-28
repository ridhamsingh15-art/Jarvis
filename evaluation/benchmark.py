from .datasets import BenchmarkDataset, DatasetRegistry
from .scenarios import Scenario, ScenarioResult, ScenarioRunner, ScenarioType


class BenchmarkSuite:
    """Orchestrates dataset loading, scenario execution, and result collection
    across all benchmark categories."""

    def __init__(self, registry: DatasetRegistry) -> None:
        self._registry = registry
        self._runner = ScenarioRunner()

    def run_dataset(self, dataset: BenchmarkDataset) -> list[ScenarioResult]:
        """Run all cases in a single dataset."""
        results: list[ScenarioResult] = []
        scenario_type = self._category_to_type(dataset.category)

        for case in dataset.cases:
            scenario = Scenario(
                id=f"{dataset.name}_{case.id}",
                scenario_type=scenario_type,
                case=case,
            )
            result = self._runner.run(scenario)
            results.append(result)

        return results

    def run_category(self, category: str) -> list[ScenarioResult]:
        """Run all datasets in a given category."""
        datasets = self._registry.get_by_category(category)
        results: list[ScenarioResult] = []
        for ds in datasets:
            results.extend(self.run_dataset(ds))
        return results

    def run_all(self) -> dict[str, list[ScenarioResult]]:
        """Run every registered dataset, grouped by category."""
        all_results: dict[str, list[ScenarioResult]] = {}
        for ds in self._registry.all_datasets():
            if ds.category not in all_results:
                all_results[ds.category] = []
            all_results[ds.category].extend(self.run_dataset(ds))
        return all_results

    def _category_to_type(self, category: str) -> ScenarioType:
        mapping: dict[str, ScenarioType] = {
            "reasoning": ScenarioType.SIMPLE_COMMAND,
            "planning": ScenarioType.SIMPLE_COMMAND,
            "coding": ScenarioType.CODING,
            "memory": ScenarioType.SIMPLE_COMMAND,
            "mission": ScenarioType.LONG_RUNNING_MISSION,
            "workspace": ScenarioType.DESKTOP_AUTOMATION,
            "knowledge": ScenarioType.SIMPLE_COMMAND,
            "internet": ScenarioType.SIMPLE_COMMAND,
            "tool_usage": ScenarioType.SIMPLE_COMMAND,
            "voice": ScenarioType.SIMPLE_COMMAND,
            "vision": ScenarioType.SIMPLE_COMMAND,
            "collaboration": ScenarioType.MULTI_AGENT,
        }
        return mapping.get(category, ScenarioType.SIMPLE_COMMAND)
