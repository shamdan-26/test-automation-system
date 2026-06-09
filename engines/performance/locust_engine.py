from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from engines.base_engine import BaseEngine
from models.test_case import TestCase, TestType
from models.test_result import EngineReport, PerformanceStats, TestResult, TestStatus


_LOCUSTFILE_TEMPLATE = '''\
from locust import HttpUser, task, between
import json

class GeneratedUser(HttpUser):
    wait_time = between(1, 3)
    host = {host!r}

{tasks}
'''

_TASK_TEMPLATE = '''\
    @task({weight})
    def {name}(self):
        self.client.{method}(
            {endpoint!r},
            {body_arg}
            name={endpoint!r},
        )
'''


class LocustEngine(BaseEngine):
    name = "performance"

    def __init__(self, config: dict[str, Any], host: str = "") -> None:
        super().__init__(config)
        self.host = host.rstrip("/")
        self.duration = config.get("duration", 60)
        self.users = config.get("users", 10)
        self.spawn_rate = config.get("spawn_rate", 2)
        self.thresholds = config.get("thresholds", {})

    def setup(self) -> None:
        self.log.info("Locust engine ready", host=self.host, users=self.users)

    def teardown(self) -> None:
        pass

    def run(self, test_cases: list[TestCase]) -> EngineReport:
        report = EngineReport(engine=self.name, environment=self.host)
        perf_cases = [tc for tc in test_cases if tc.type == TestType.PERFORMANCE and tc.performance]

        if not perf_cases:
            report.finished_at = datetime.utcnow()
            return report

        locustfile = self._generate_locustfile(perf_cases)
        lf_path = Path("outputs/artifacts/locustfile.py")
        lf_path.write_text(locustfile)

        stats_path = Path("outputs/artifacts/locust_stats.json")
        cmd = [
            "locust",
            "--headless",
            "--locustfile", str(lf_path),
            "--host", self.host,
            "--users", str(self.users),
            "--spawn-rate", str(self.spawn_rate),
            "--run-time", f"{self.duration}s",
            "--json",
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.duration + 60)
            raw_stats = json.loads(proc.stdout) if proc.stdout else []
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            self.log.error("Locust run failed", error=str(exc))
            raw_stats = []

        perf_stats = self._parse_stats(raw_stats)
        report.performance_stats = perf_stats

        thresholds_passed = perf_stats.thresholds_passed if perf_stats else True
        for tc in perf_cases:
            report.results.append(TestResult(
                test_case_id=tc.id,
                title=tc.title,
                status=TestStatus.PASSED if thresholds_passed else TestStatus.FAILED,
                duration_ms=self.duration * 1000,
                error_message="" if thresholds_passed else "Performance thresholds exceeded",
            ))

        report.finished_at = datetime.utcnow()
        self.log.info("Performance run complete", thresholds_passed=thresholds_passed)
        return report

    def _generate_locustfile(self, test_cases: list[TestCase]) -> str:
        tasks: list[str] = []
        for tc in test_cases:
            assert tc.performance is not None
            body_arg = f"json={tc.performance.body!r}," if tc.performance.body else ""
            tasks.append(_TASK_TEMPLATE.format(
                weight=tc.performance.weight,
                name=tc.id.replace("-", "_"),
                method=tc.performance.method.value.lower(),
                endpoint=tc.performance.endpoint,
                body_arg=body_arg,
            ))
        return _LOCUSTFILE_TEMPLATE.format(host=self.host, tasks="\n".join(tasks))

    def _parse_stats(self, raw: list[dict[str, Any]]) -> PerformanceStats | None:
        if not raw:
            return None
        aggregated = next((s for s in raw if s.get("name") == "Aggregated"), raw[0])
        p95 = aggregated.get("response_time_percentile_95", 0)
        error_rate = aggregated.get("fail_ratio", 0)
        rps = aggregated.get("current_rps", 0)

        thresholds_passed = (
            p95 <= self.thresholds.get("response_time_p95", float("inf"))
            and error_rate <= self.thresholds.get("error_rate", 1.0)
            and rps >= self.thresholds.get("requests_per_second", 0)
        )

        return PerformanceStats(
            total_requests=aggregated.get("num_requests", 0),
            failed_requests=aggregated.get("num_failures", 0),
            avg_response_time_ms=aggregated.get("avg_response_time", 0),
            min_response_time_ms=aggregated.get("min_response_time", 0),
            max_response_time_ms=aggregated.get("max_response_time", 0),
            p50_ms=aggregated.get("response_time_percentile_50", 0),
            p95_ms=p95,
            p99_ms=aggregated.get("response_time_percentile_99", 0),
            requests_per_second=rps,
            error_rate=error_rate,
            thresholds_passed=thresholds_passed,
        )
