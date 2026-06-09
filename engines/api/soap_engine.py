from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import zeep
from zeep import Client
from zeep.exceptions import Fault

from engines.base_engine import BaseEngine
from models.test_case import TestCase, TestType
from models.test_result import EngineReport, TestResult, TestStatus


class SoapEngine(BaseEngine):
    name = "api_soap"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._clients: dict[str, Client] = {}

    def setup(self) -> None:
        self.log.info("SOAP engine ready")

    def teardown(self) -> None:
        self._clients.clear()
        self.log.info("SOAP engine torn down")

    def run(self, test_cases: list[TestCase]) -> EngineReport:
        report = EngineReport(engine=self.name, environment="soap")
        soap_cases = [tc for tc in test_cases if tc.type == TestType.API_SOAP and tc.soap]

        for tc in soap_cases:
            result = self._execute(tc)
            report.results.append(result)

        report.finished_at = datetime.utcnow()
        self.log.info("SOAP run complete", total=report.total, passed=report.passed, failed=report.failed)
        return report

    def _client_for(self, wsdl: str) -> Client:
        if wsdl not in self._clients:
            self._clients[wsdl] = zeep.Client(wsdl=wsdl)
        return self._clients[wsdl]

    def _execute(self, tc: TestCase) -> TestResult:
        assert tc.soap is not None
        client = self._client_for(tc.soap.wsdl)
        service = getattr(client.service, tc.soap.operation)
        start = time.monotonic()

        try:
            response = service(**tc.soap.payload)
            duration_ms = (time.monotonic() - start) * 1000
            return self._validate(tc, response, duration_ms)
        except Fault as exc:
            duration_ms = (time.monotonic() - start) * 1000
            return TestResult(
                test_case_id=tc.id,
                title=tc.title,
                status=TestStatus.FAILED,
                duration_ms=duration_ms,
                error_message=f"SOAP Fault: {exc.message}",
            )
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            return TestResult(
                test_case_id=tc.id,
                title=tc.title,
                status=TestStatus.ERROR,
                duration_ms=duration_ms,
                error_message=str(exc),
            )

    def _validate(self, tc: TestCase, response: Any, duration_ms: float) -> TestResult:
        assert tc.soap is not None
        errors: list[str] = []

        response_dict: dict[str, Any] = {}
        if hasattr(response, "__dict__"):
            response_dict = {k: v for k, v in response.__dict__.items() if not k.startswith("_")}
        elif isinstance(response, dict):
            response_dict = response

        for field, expected in tc.soap.expected_fields.items():
            actual = response_dict.get(field)
            if actual != expected:
                errors.append(f"Field '{field}': got {actual!r}, expected {expected!r}")

        return TestResult(
            test_case_id=tc.id,
            title=tc.title,
            status=TestStatus.FAILED if errors else TestStatus.PASSED,
            duration_ms=duration_ms,
            error_message="\n".join(errors),
        )
