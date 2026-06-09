from __future__ import annotations

import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from appium import webdriver
from appium.options import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy

from engines.base_engine import BaseEngine
from models.test_case import TestCase, TestType
from models.test_result import EngineReport, TestResult, TestStatus


class AppiumEngine(BaseEngine):
    name = "mobile"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.driver: webdriver.Remote | None = None
        self.server = config.get("appium_server", "http://localhost:4723")

    def setup(self) -> None:
        options = AppiumOptions()
        options.platform_name = self.config.get("platform", "android")
        options.platform_version = self.config.get("platform_version", "13.0")
        options.device_name = self.config.get("device_name", "Android Emulator")
        options.app = self.config.get("app_path", "")
        options.automation_name = "UiAutomator2" if options.platform_name == "android" else "XCUITest"
        self.driver = webdriver.Remote(self.server, options=options)
        self.log.info("Appium session started", platform=options.platform_name, server=self.server)

    def teardown(self) -> None:
        if self.driver:
            self.driver.quit()
        self.log.info("Appium session closed")

    def run(self, test_cases: list[TestCase]) -> EngineReport:
        report = EngineReport(engine=self.name, environment=self.config.get("platform", "android"))
        mobile_cases = [tc for tc in test_cases if tc.type == TestType.MOBILE]

        for tc in mobile_cases:
            result = self._execute(tc)
            report.results.append(result)

        report.finished_at = datetime.utcnow()
        self.log.info("Mobile run complete", total=report.total, passed=report.passed, failed=report.failed)
        return report

    def _execute(self, tc: TestCase) -> TestResult:
        assert self.driver is not None
        start = time.monotonic()
        attachments: list[Path] = []

        try:
            for step in tc.steps:
                self._execute_step(step.action, step.data)

            duration_ms = (time.monotonic() - start) * 1000
            return TestResult(
                test_case_id=tc.id,
                title=tc.title,
                status=TestStatus.PASSED,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            shot_path = Path("outputs/artifacts") / f"{tc.id}_mobile_failure.png"
            self.driver.save_screenshot(str(shot_path))
            attachments.append(shot_path)
            duration_ms = (time.monotonic() - start) * 1000
            return TestResult(
                test_case_id=tc.id,
                title=tc.title,
                status=TestStatus.ERROR,
                duration_ms=duration_ms,
                error_message=str(exc),
                error_stacktrace=traceback.format_exc(),
                attachments=attachments,
            )

    def _execute_step(self, action: str, data: dict[str, Any]) -> None:
        assert self.driver is not None
        by_map = {
            "id": AppiumBy.ID,
            "xpath": AppiumBy.XPATH,
            "accessibility_id": AppiumBy.ACCESSIBILITY_ID,
            "class_name": AppiumBy.CLASS_NAME,
        }
        locator_type = by_map.get(data.get("by", "id"), AppiumBy.ID)
        selector = data.get("selector", "")

        action_map = {
            "click": lambda: self.driver.find_element(locator_type, selector).click(),  # type: ignore[union-attr]
            "send_keys": lambda: self.driver.find_element(locator_type, selector).send_keys(data.get("value", "")),  # type: ignore[union-attr]
            "clear": lambda: self.driver.find_element(locator_type, selector).clear(),  # type: ignore[union-attr]
            "swipe": lambda: self.driver.swipe(  # type: ignore[union-attr]
                data["start_x"], data["start_y"], data["end_x"], data["end_y"]
            ),
        }
        handler = action_map.get(action)
        if handler:
            handler()
        else:
            self.log.warning("Unknown mobile action", action=action)
