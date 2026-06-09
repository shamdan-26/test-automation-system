from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from engines.base_engine import BaseEngine
from models.test_case import TestCase, TestType
from models.test_result import EngineReport, RunSummary
from utils.logger import get_logger

log = get_logger("orchestrator.pipeline")


def build_engines(config: dict[str, Any], api_url: str, ui_url: str) -> list[BaseEngine]:
    engines: list[BaseEngine] = []
    eng_cfg = config.get("engines", {})

    if eng_cfg.get("api_rest", {}).get("enabled"):
        from engines.api.rest_engine import RestEngine
        engines.append(RestEngine(eng_cfg["api_rest"], base_url=api_url))

    if eng_cfg.get("api_soap", {}).get("enabled"):
        from engines.api.soap_engine import SoapEngine
        engines.append(SoapEngine(eng_cfg["api_soap"]))

    if eng_cfg.get("ui", {}).get("enabled"):
        from engines.ui.playwright_engine import PlaywrightEngine
        engines.append(PlaywrightEngine(eng_cfg["ui"], base_url=ui_url))

    if eng_cfg.get("mobile", {}).get("enabled"):
        from engines.mobile.appium_engine import AppiumEngine
        engines.append(AppiumEngine(eng_cfg["mobile"]))

    if eng_cfg.get("performance", {}).get("enabled"):
        from engines.performance.locust_engine import LocustEngine
        engines.append(LocustEngine(eng_cfg["performance"], host=api_url))

    if eng_cfg.get("regression", {}).get("enabled"):
        from engines.regression.regression_manager import RegressionManager
        engines.append(RegressionManager(eng_cfg["regression"]))

    return engines


def run_pipeline(
    engines: list[BaseEngine],
    test_cases: list[TestCase],
    summary: RunSummary,
    parallel: bool = True,
) -> RunSummary:
    """Run all engines (in parallel if enabled) and collect results into summary."""

    if parallel and len(engines) > 1:
        with ThreadPoolExecutor(max_workers=len(engines)) as pool:
            futures = {pool.submit(_run_engine, eng, test_cases): eng for eng in engines}
            for future in as_completed(futures):
                eng = futures[future]
                try:
                    report = future.result()
                    summary.engine_reports.append(report)
                except Exception as exc:
                    log.error("Engine crashed", engine=eng.name, error=str(exc))
    else:
        for eng in engines:
            try:
                report = _run_engine(eng, test_cases)
                summary.engine_reports.append(report)
            except Exception as exc:
                log.error("Engine crashed", engine=eng.name, error=str(exc))

    return summary


def _run_engine(engine: BaseEngine, test_cases: list[TestCase]) -> EngineReport:
    engine.setup()
    try:
        return engine.run(test_cases)
    finally:
        engine.teardown()
