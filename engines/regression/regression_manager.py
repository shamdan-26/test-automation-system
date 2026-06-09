from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from engines.base_engine import BaseEngine
from models.test_case import TestCase, TestType
from models.test_result import EngineReport, TestResult, TestStatus
from utils.helpers import file_hash


class RegressionManager(BaseEngine):
    """Compares current run results against a saved baseline."""

    name = "regression"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.baseline_dir = Path(config.get("baseline_dir", "outputs/baselines"))
        self.diff_threshold = float(config.get("diff_threshold", 0.05))
        self.baseline_dir.mkdir(parents=True, exist_ok=True)

    def setup(self) -> None:
        self.log.info("Regression manager ready", baseline_dir=str(self.baseline_dir))

    def teardown(self) -> None:
        pass

    def run(self, test_cases: list[TestCase]) -> EngineReport:
        report = EngineReport(engine=self.name, environment="regression")
        regression_cases = [tc for tc in test_cases if tc.type == TestType.REGRESSION]

        for tc in regression_cases:
            baseline_path = self.baseline_dir / f"{tc.id}.json"
            if not baseline_path.exists():
                self.log.info("No baseline found, creating", test_id=tc.id)
                self._save_baseline(tc, baseline_path)
                report.results.append(TestResult(
                    test_case_id=tc.id,
                    title=tc.title,
                    status=TestStatus.SKIPPED,
                    duration_ms=0,
                    error_message="Baseline created — will compare on next run",
                ))
                continue

            result = self._compare(tc, baseline_path)
            report.results.append(result)

        report.finished_at = datetime.utcnow()
        return report

    def save_run_as_baseline(self, engine_report: EngineReport) -> None:
        """Promote a passing run's results to the new baseline."""
        for result in engine_report.results:
            if result.status == TestStatus.PASSED:
                baseline_path = self.baseline_dir / f"{result.test_case_id}.json"
                baseline_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2))
        self.log.info("Baseline updated", engine=engine_report.engine)

    def _save_baseline(self, tc: TestCase, path: Path) -> None:
        path.write_text(json.dumps(tc.model_dump(mode="json"), indent=2))

    def _compare(self, tc: TestCase, baseline_path: Path) -> TestResult:
        baseline: dict[str, Any] = json.loads(baseline_path.read_text())
        current: dict[str, Any] = tc.model_dump(mode="json")
        diffs = self._diff(baseline, current, prefix="")

        if not diffs:
            return TestResult(
                test_case_id=tc.id,
                title=tc.title,
                status=TestStatus.PASSED,
                duration_ms=0,
            )

        return TestResult(
            test_case_id=tc.id,
            title=tc.title,
            status=TestStatus.FAILED,
            duration_ms=0,
            error_message="Regression detected:\n" + "\n".join(diffs),
        )

    def _diff(self, baseline: Any, current: Any, prefix: str) -> list[str]:
        diffs: list[str] = []
        if isinstance(baseline, dict) and isinstance(current, dict):
            for key in set(baseline) | set(current):
                path = f"{prefix}.{key}" if prefix else key
                if key not in current:
                    diffs.append(f"REMOVED: {path}")
                elif key not in baseline:
                    diffs.append(f"ADDED: {path} = {current[key]!r}")
                else:
                    diffs.extend(self._diff(baseline[key], current[key], path))
        elif baseline != current:
            diffs.append(f"CHANGED: {prefix}: {baseline!r} -> {current!r}")
        return diffs
