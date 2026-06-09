from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonschema
import requests
from requests import Session

from engines.base_engine import BaseEngine
from models.test_case import TestCase, TestType
from models.test_result import EngineReport, TestResult, TestStatus
from utils.retry import retry


class RestEngine(BaseEngine):
    name = "api_rest"

    def __init__(self, config: dict[str, Any], base_url: str = "") -> None:
        super().__init__(config)
        self.base_url = base_url.rstrip("/")
        self.session: Session | None = None
        self.timeout = config.get("timeout", 30)
        self.retry_count = config.get("retry_count", 3)

    def setup(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
        self.log.info("REST session opened", base_url=self.base_url)

    def teardown(self) -> None:
        if self.session:
            self.session.close()
        self.log.info("REST session closed")

    def run(self, test_cases: list[TestCase]) -> EngineReport:
        report = EngineReport(engine=self.name, environment=self.base_url)
        api_cases = [tc for tc in test_cases if tc.type == TestType.API_REST and tc.api]

        for tc in api_cases:
            result = self._execute(tc)
            report.results.append(result)

        report.finished_at = datetime.utcnow()
        self.log.info("REST run complete", total=report.total, passed=report.passed, failed=report.failed)
        return report

    def _execute(self, tc: TestCase) -> TestResult:
        assert tc.api is not None
        assert self.session is not None

        url = self.base_url + tc.api.endpoint
        start = time.monotonic()

        try:
            response = self._send(tc, url)
            duration_ms = (time.monotonic() - start) * 1000
            return self._validate(tc, response, duration_ms)
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            self.log.error("Request failed", test_id=tc.id, error=str(exc))
            return TestResult(
                test_case_id=tc.id,
                title=tc.title,
                status=TestStatus.ERROR,
                duration_ms=duration_ms,
                error_message=str(exc),
            )

    @retry(attempts=3, delay=2.0, exceptions=(requests.Timeout, requests.ConnectionError))
    def _send(self, tc: TestCase, url: str) -> requests.Response:
        assert tc.api is not None
        assert self.session is not None
        return self.session.request(
            method=tc.api.method.value,
            url=url,
            headers=tc.api.headers,
            params=tc.api.query_params,
            json=tc.api.body,
            timeout=self.timeout,
        )

    def _validate(self, tc: TestCase, response: requests.Response, duration_ms: float) -> TestResult:
        assert tc.api is not None
        errors: list[str] = []

        if response.status_code != tc.api.expected_status:
            errors.append(f"Status {response.status_code} != expected {tc.api.expected_status}")

        try:
            body = response.json()
        except ValueError:
            body = {}

        if tc.api.expected_schema:
            try:
                jsonschema.validate(body, tc.api.expected_schema)
            except jsonschema.ValidationError as exc:
                errors.append(f"Schema validation: {exc.message}")

        for field, expected in tc.api.expected_fields.items():
            actual = body.get(field)
            if actual != expected:
                errors.append(f"Field '{field}': got {actual!r}, expected {expected!r}")

        attachments: list[Path] = []
        if errors:
            log_path = Path("outputs/artifacts") / f"{tc.id}_response.txt"
            log_path.write_text(f"URL: {response.url}\nStatus: {response.status_code}\nBody:\n{response.text}")
            attachments.append(log_path)

        return TestResult(
            test_case_id=tc.id,
            title=tc.title,
            status=TestStatus.FAILED if errors else TestStatus.PASSED,
            duration_ms=duration_ms,
            error_message="\n".join(errors),
            attachments=attachments,
            metadata={"status_code": response.status_code, "url": response.url},
        )
