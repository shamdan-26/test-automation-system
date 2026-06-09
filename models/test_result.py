from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestResult(BaseModel):
    test_case_id: str
    title: str
    status: TestStatus
    duration_ms: float
    started_at: datetime = Field(default_factory=datetime.utcnow)
    error_message: str = ""
    error_stacktrace: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)
    attachments: list[Path] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == TestStatus.PASSED

    @property
    def failed(self) -> bool:
        return self.status in (TestStatus.FAILED, TestStatus.ERROR)


class PerformanceStats(BaseModel):
    total_requests: int
    failed_requests: int
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    requests_per_second: float
    error_rate: float
    thresholds_passed: bool


class EngineReport(BaseModel):
    engine: str
    environment: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    results: list[TestResult] = Field(default_factory=list)
    performance_stats: PerformanceStats | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.PASSED)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.failed)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.SKIPPED)

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total * 100) if self.total else 0.0

    @property
    def duration_s(self) -> float:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0


class RunSummary(BaseModel):
    run_id: str
    environment: str
    triggered_by: str = "manual"   # manual | nightly | webhook
    git_commit: str = ""
    git_branch: str = ""
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    engine_reports: list[EngineReport] = Field(default_factory=list)
    bugs_submitted: int = 0
    report_paths: dict[str, str] = Field(default_factory=dict)

    @property
    def overall_status(self) -> TestStatus:
        for report in self.engine_reports:
            if report.failed > 0:
                return TestStatus.FAILED
        return TestStatus.PASSED

    @property
    def total_tests(self) -> int:
        return sum(r.total for r in self.engine_reports)

    @property
    def total_passed(self) -> int:
        return sum(r.passed for r in self.engine_reports)

    @property
    def total_failed(self) -> int:
        return sum(r.failed for r in self.engine_reports)
