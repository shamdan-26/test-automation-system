from __future__ import annotations

from pathlib import Path
from typing import Any
import webbrowser

import yaml
from flask import Flask, flash, redirect, render_template, request, url_for

from orchestrator.runner import load_config, run as execute_run
from utils.logger import setup_logging

app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
app.secret_key = "tas-web-ui-secret-key"

DEFAULT_ENGINES = ["api_rest", "api_soap", "ui", "mobile", "performance", "regression"]


def start_ui(config_path: Path | None = None, host: str = "127.0.0.1", port: int = 5000) -> None:
    if config_path is None:
        config_path = Path.cwd() / "tas_config.yml"
    app.config["DEFAULT_CONFIG_PATH"] = str(config_path)
    app.config["RUNNING_CONFIG"] = str(config_path)
    url = f"http://{host}:{port}/"
    try:
        webbrowser.open(url)
    except Exception:
        pass
    app.run(host=host, port=port)


def _load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    return load_config(config_path)


def _engine_options(config: dict[str, Any] | None) -> list[dict[str, Any]]:
    engines = []
    config_engines = config.get("engines", {}) if config else {}
    for name in DEFAULT_ENGINES:
        enabled = bool(config_engines.get(name, {}).get("enabled", False))
        engines.append({"name": name, "enabled": enabled})
    return engines


@app.route("/", methods=["GET", "POST"])
def index() -> str:
    config_path = Path(request.form.get("config_path") or request.args.get("config_path") or app.config.get("DEFAULT_CONFIG_PATH", "tas_config.yml"))
    action = request.form.get("action")
    inputs_value = request.form.get("input_paths", "")
    selected_engines = request.form.getlist("engines")
    config: dict[str, Any] | None = None
    config_text = ""
    summary = None

    try:
        config = _load_config(config_path)
        config_text = yaml.safe_dump(config, sort_keys=False)
    except Exception as exc:
        flash(str(exc), "error")

    if action == "run" and config:
        engine_override = selected_engines or None
        input_paths = [Path(p.strip()) for p in inputs_value.split(",") if p.strip()]
        try:
            setup_logging(level=config.get("system", {}).get("log_level", "INFO"))
            summary = execute_run(
                config=config,
                input_paths=input_paths,
                engines_override=engine_override,
                triggered_by="web-ui",
            )
        except Exception as exc:
            flash(f"Run failed: {exc}", "error")

    engine_options = _engine_options(config)
    return render_template(
        "ui.html",
        config_path=str(config_path),
        config_text=config_text,
        engine_options=engine_options,
        selected_engines=selected_engines,
        inputs_value=inputs_value,
        summary=summary,
    )
