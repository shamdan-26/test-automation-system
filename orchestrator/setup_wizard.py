from __future__ import annotations

from pathlib import Path
from typing import Any

import click
import yaml


def run_setup_wizard() -> tuple[Path, dict[str, Any]]:
    """
    Interactive first-run wizard.
    Asks for every setting and writes tas_config.yml to a user-chosen folder.
    Returns (config_path, config_dict).
    """
    click.clear()
    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo(click.style("  Test Automation System — Setup Wizard", fg="cyan", bold=True))
    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo()

    # ── Output folder ────────────────────────────────────────────
    click.echo(click.style("Step 1 of 6: Output location", fg="yellow", bold=True))
    output_dir = click.prompt(
        "Where should reports and artifacts be saved?",
        default=str(Path.cwd() / "outputs"),
        type=click.Path(),
    )
    config_dir = click.prompt(
        "Where should the config file be saved?",
        default=str(Path.cwd()),
        type=click.Path(),
    )
    click.echo()

    # ── Environment ──────────────────────────────────────────────
    click.echo(click.style("Step 2 of 6: Target environment", fg="yellow", bold=True))
    environment = click.prompt("Environment", type=click.Choice(["dev", "staging", "prod"]), default="staging")
    api_base_url = click.prompt("API base URL (REST)", default="https://api.example.com")
    soap_wsdl = click.prompt("SOAP WSDL URL (leave blank to skip)", default="", show_default=False)
    ui_base_url = click.prompt("UI base URL", default="https://example.com")
    click.echo()

    # ── Engines ──────────────────────────────────────────────────
    click.echo(click.style("Step 3 of 6: Which engines to enable by default?", fg="yellow", bold=True))
    enable_api_rest = click.confirm("Enable REST API tests?", default=True)
    enable_api_soap = click.confirm("Enable SOAP API tests?", default=bool(soap_wsdl))
    enable_ui = click.confirm("Enable UI tests (Playwright)?", default=True)
    enable_mobile = click.confirm("Enable Mobile tests (Appium)?", default=False)
    enable_performance = click.confirm("Enable Performance tests (Locust)?", default=True)
    enable_regression = click.confirm("Enable Regression tests?", default=True)
    click.echo()

    # ── Jira ─────────────────────────────────────────────────────
    click.echo(click.style("Step 4 of 6: Jira integration", fg="yellow", bold=True))
    enable_jira = click.confirm("Enable Jira bug submission?", default=False)
    jira_cfg: dict[str, Any] = {"enabled": False}
    if enable_jira:
        jira_cfg = {
            "enabled": True,
            "server_url": click.prompt("Jira server URL", default="https://yourcompany.atlassian.net"),
            "username": click.prompt("Jira username (email)"),
            "api_token": click.prompt("Jira API token", hide_input=True),
            "project_key": click.prompt("Jira project key (e.g. QA)"),
            "issue_type": click.prompt("Issue type", default="Bug"),
            "auto_submit": click.confirm("Auto-submit bugs after each run?", default=False),
            "attach_screenshots": True,
            "labels": ["automated"],
        }
    click.echo()

    # ── GitHub ───────────────────────────────────────────────────
    click.echo(click.style("Step 5 of 6: GitHub integration", fg="yellow", bold=True))
    enable_github = click.confirm("Enable GitHub integration?", default=False)
    github_cfg: dict[str, Any] = {"enabled": False}
    if enable_github:
        github_cfg = {
            "enabled": True,
            "token": click.prompt("GitHub personal access token", hide_input=True),
            "repository": click.prompt("Repository (owner/repo)", default="myorg/myrepo"),
            "post_commit_status": click.confirm("Post commit status checks?", default=True),
            "create_issues": click.confirm("Create GitHub Issues for bugs?", default=False),
        }
    click.echo()

    # ── Notifications ─────────────────────────────────────────────
    click.echo(click.style("Step 6 of 6: Email notifications", fg="yellow", bold=True))
    enable_email = click.confirm("Enable email notifications?", default=False)
    email_cfg: dict[str, Any] = {"enabled": False}
    if enable_email:
        email_cfg = {
            "enabled": True,
            "smtp_host": click.prompt("SMTP host"),
            "smtp_port": click.prompt("SMTP port", default=587, type=int),
            "use_tls": click.confirm("Use TLS?", default=True),
            "username": click.prompt("SMTP username"),
            "password": click.prompt("SMTP password", hide_input=True),
            "from_address": click.prompt("From address"),
            "to_addresses": click.prompt("To addresses (comma-separated)").split(","),
            "on_failure": True,
            "on_success": False,
        }
    click.echo()

    # ── Build config dict ─────────────────────────────────────────
    config: dict[str, Any] = {
        "system": {"output_dir": output_dir, "log_level": "INFO", "parallel": True},
        "environment": environment,
        "api": {"base_url": api_base_url, "soap_wsdl": soap_wsdl},
        "engines": {
            "api_rest": {"enabled": enable_api_rest, "timeout": 30, "retry_count": 3},
            "api_soap": {"enabled": enable_api_soap, "timeout": 30},
            "ui": {"enabled": enable_ui, "base_url": ui_base_url, "browser": "chromium", "headless": True},
            "mobile": {"enabled": enable_mobile},
            "performance": {"enabled": enable_performance, "host": api_base_url, "users": 10, "duration": 60},
            "regression": {"enabled": enable_regression, "baseline_dir": str(Path(output_dir) / "baselines")},
        },
        "reporters": {
            "html": {"enabled": True, "output_dir": str(Path(output_dir) / "reports" / "html")},
            "pdf": {"enabled": True, "output_dir": str(Path(output_dir) / "reports" / "pdf")},
        },
        "integrations": {
            "jira": jira_cfg,
            "github": github_cfg,
        },
        "notifications": {"email": email_cfg},
    }

    config_path = Path(config_dir) / "tas_config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False), encoding="utf-8")

    click.echo(click.style("Setup complete!", fg="green", bold=True))
    click.echo(f"Config saved to: {config_path}")
    click.echo(f"Run tests with:  tas run --config {config_path}")
    return config_path, config
