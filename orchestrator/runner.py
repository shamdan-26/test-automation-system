from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from input_parser.task_parser import ParserRegistry
from models.bug_report import BugReport, BugSeverity
from models.test_result import RunSummary, TestStatus
from orchestrator.pipeline import build_engines, run_pipeline
from reporters.html_reporter import HtmlReporter
from reporters.pdf_reporter import PdfReporter
from test_generator.generator import TestCaseGenerator
from utils.helpers import ensure_dir, generate_run_id
from utils.logger import get_logger

log = get_logger("orchestrator.runner")


def load_config(config_path: Path) -> dict[str, Any]:
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def get_git_info() -> tuple[str, str]:
    def _run(cmd: list[str]) -> str:
        try:
            return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
        except Exception:
            return ""

    return _run(["git", "rev-parse", "HEAD"]), _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def run(
    config: dict[str, Any],
    input_paths: list[Path],
    engines_override: list[str] | None = None,
    triggered_by: str = "manual",
) -> RunSummary:
    run_id = generate_run_id()
    git_commit, git_branch = get_git_info()

    output_dir = Path(config["system"]["output_dir"])
    ensure_dir(output_dir)
    ensure_dir(output_dir / "artifacts")
    ensure_dir(output_dir / "reports" / "html")
    ensure_dir(output_dir / "reports" / "pdf")

    log.info("Run starting", run_id=run_id, environment=config.get("environment", ""), git=git_commit[:7] or "N/A")

    # ── Parse inputs ──────────────────────────────────────────────
    registry = ParserRegistry()
    parsed_inputs = []
    for path in input_paths:
        try:
            parsed_inputs.extend(registry.parse(path))
        except ValueError as exc:
            log.warning("Skipping unparseable file", path=str(path), error=str(exc))

    # ── Generate test cases ───────────────────────────────────────
    tc_dir = output_dir / "test_cases"
    generator = TestCaseGenerator(tc_dir)
    test_cases = generator.generate(parsed_inputs)
    log.info("Test cases ready", count=len(test_cases))

    # ── Build and filter engines ──────────────────────────────────
    api_url = config.get("api", {}).get("base_url", "")
    ui_url = config.get("engines", {}).get("ui", {}).get("base_url", "")
    all_engines = build_engines(config, api_url=api_url, ui_url=ui_url)

    if engines_override:
        all_engines = [e for e in all_engines if e.name in engines_override]

    # ── Run pipeline ──────────────────────────────────────────────
    summary = RunSummary(
        run_id=run_id,
        environment=config.get("environment", ""),
        triggered_by=triggered_by,
        git_commit=git_commit,
        git_branch=git_branch,
    )
    parallel = config.get("system", {}).get("parallel", True)
    summary = run_pipeline(all_engines, test_cases, summary, parallel=parallel)
    summary.finished_at = datetime.utcnow()

    # ── Submit bugs ───────────────────────────────────────────────
    jira_cfg = config.get("integrations", {}).get("jira", {})
    if jira_cfg.get("enabled") and jira_cfg.get("auto_submit"):
        summary.bugs_submitted = _submit_bugs(summary, jira_cfg, git_commit, git_branch, config.get("environment", ""))

    # ── GitHub status ─────────────────────────────────────────────
    gh_cfg = config.get("integrations", {}).get("github", {})
    if gh_cfg.get("enabled") and gh_cfg.get("post_commit_status") and git_commit:
        _post_github_status(summary, gh_cfg, git_commit)

    # ── Reports ───────────────────────────────────────────────────
    rep_cfg = config.get("reporters", {})
    if rep_cfg.get("html", {}).get("enabled", True):
        html_path = HtmlReporter(rep_cfg.get("html", {})).generate(summary)
        summary.report_paths["html"] = str(html_path)

    if rep_cfg.get("pdf", {}).get("enabled", True):
        pdf_path = PdfReporter(rep_cfg.get("pdf", {})).generate(summary)
        summary.report_paths["pdf"] = str(pdf_path)

    log.info(
        "Run complete",
        run_id=run_id,
        status=summary.overall_status.value,
        passed=summary.total_passed,
        failed=summary.total_failed,
        bugs=summary.bugs_submitted,
    )
    return summary


def _submit_bugs(
    summary: RunSummary,
    jira_cfg: dict[str, Any],
    git_commit: str,
    git_branch: str,
    environment: str,
) -> int:
    from integrations.bug_tracker.factory import create_tracker

    tracker = create_tracker("jira", jira_cfg)
    tracker.connect()
    count = 0
    for report in summary.engine_reports:
        for result in report.results:
            if not result.failed:
                continue
            bug = BugReport(
                title=f"[AUTO] {result.title} failed in {report.engine}",
                description=result.error_message,
                severity=BugSeverity.HIGH if report.engine == "performance" else BugSeverity.MEDIUM,
                environment=environment,
                test_case_id=result.test_case_id,
                engine=report.engine,
                actual_result=result.error_message,
                expected_result="Test should pass",
                error_message=result.error_message,
                stacktrace=result.error_stacktrace,
                attachments=result.attachments,
                git_commit=git_commit,
                git_branch=git_branch,
            )
            try:
                tracker.submit_bug(bug)
                count += 1
            except Exception as exc:
                log.error("Bug submission failed", test_id=result.test_case_id, error=str(exc))
    return count


def _post_github_status(summary: RunSummary, gh_cfg: dict[str, Any], git_commit: str) -> None:
    from integrations.github.github_client import GitHubClient

    client = GitHubClient(gh_cfg)
    try:
        client.connect()
        state = "success" if summary.overall_status == TestStatus.PASSED else "failure"
        description = f"{summary.total_passed}/{summary.total_tests} tests passed"
        client.post_commit_status(git_commit, state=state, description=description)
    except Exception as exc:
        log.error("GitHub status update failed", error=str(exc))
