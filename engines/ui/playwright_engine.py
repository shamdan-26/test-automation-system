from __future__ import annotations

import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Playwright, sync_playwright

from engines.base_engine import BaseEngine
from models.test_case import TestCase, TestType
from models.test_result import EngineReport, TestResult, TestStatus


class PlaywrightEngine(BaseEngine):
    name = "ui"

    def __init__(self, config: dict[str, Any], base_url: str = "") -> None:
        super().__init__(config)
        self.base_url = base_url.rstrip("/")
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def setup(self) -> None:
        self._playwright = sync_playwright().start()
        browser_type = self.config.get("browser", "chromium")
        launcher = getattr(self._playwright, browser_type)
        self._browser = launcher.launch(headless=self.config.get("headless", True))
        self.log.info("Playwright browser launched", browser=browser_type)

    def teardown(self) -> None:
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self.log.info("Playwright browser closed")

    def run(self, test_cases: list[TestCase]) -> EngineReport:
        report = EngineReport(engine=self.name, environment=self.base_url)
        ui_cases = [tc for tc in test_cases if tc.type == TestType.UI and tc.ui]

        for tc in ui_cases:
            result = self._execute(tc)
            report.results.append(result)

        report.finished_at = datetime.utcnow()
        self.log.info("UI run complete", total=report.total, passed=report.passed, failed=report.failed)
        return report

    def _execute(self, tc: TestCase) -> TestResult:
        assert tc.ui is not None
        assert self._browser is not None

        video_dir = "outputs/artifacts/videos"
        Path(video_dir).mkdir(parents=True, exist_ok=True)

        record_video = self.config.get("video", "on-failure")
        context_options: dict[str, Any] = {}
        if record_video in ("always", "on-failure"):
            context_options["record_video_dir"] = video_dir

        context = self._browser.new_context(**context_options)
        page = context.new_page()
        page.set_default_timeout(self.config.get("timeout", 30000))

        start = time.monotonic()
        attachments: list[Path] = []
        errors: list[str] = []

        try:
            target_url = tc.ui.url if tc.ui.url.startswith("http") else self.base_url + tc.ui.url
            page.goto(target_url)
            page.wait_for_load_state("networkidle")

            for step in tc.ui.steps:
                self._execute_step(page, step.action, step.data)

            for assertion in tc.ui.assertions:
                if not page.locator(assertion).is_visible():
                    errors.append(f"Assertion failed: element '{assertion}' not visible")

        except Exception as exc:
            errors.append(str(exc))
            tb = traceback.format_exc()
            screenshot_cfg = self.config.get("screenshot", "on-failure")
            if screenshot_cfg in ("always", "on-failure"):
                shot_path = Path("outputs/artifacts") / f"{tc.id}_failure.png"
                page.screenshot(path=str(shot_path), full_page=True)
                attachments.append(shot_path)
            context.close()
            duration_ms = (time.monotonic() - start) * 1000
            return TestResult(
                test_case_id=tc.id,
                title=tc.title,
                status=TestStatus.ERROR,
                duration_ms=duration_ms,
                error_message=str(exc),
                error_stacktrace=tb,
                attachments=attachments,
            )
        finally:
            context.close()

        duration_ms = (time.monotonic() - start) * 1000
        return TestResult(
            test_case_id=tc.id,
            title=tc.title,
            status=TestStatus.FAILED if errors else TestStatus.PASSED,
            duration_ms=duration_ms,
            error_message="\n".join(errors),
            attachments=attachments,
        )

    def _execute_step(self, page: Any, action: str, data: dict[str, Any]) -> None:
        action_map = {
            "click": lambda: page.locator(data["selector"]).click(),
            "fill": lambda: page.locator(data["selector"]).fill(data["value"]),
            "select": lambda: page.locator(data["selector"]).select_option(data["value"]),
            "navigate": lambda: page.goto(data["url"]),
            "wait": lambda: page.wait_for_timeout(data.get("ms", 1000)),
            "assert_text": lambda: page.locator(data["selector"]).inner_text(),
            "assert_visible": lambda: page.locator(data["selector"]).is_visible(),
        }
        handler = action_map.get(action)
        if handler:
            handler()
        else:
            self.log.warning("Unknown UI action", action=action)
