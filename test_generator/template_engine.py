from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from models.test_case import TestCase
from utils.helpers import slugify
from utils.logger import get_logger

log = get_logger("test_generator.template_engine")

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class TemplateEngine:
    """Renders Jinja2 templates into YAML test case files."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )
        self._env.filters["tojson"] = lambda v: __import__("json").dumps(v)

    def render_api_cases(self, context: dict[str, Any], source: str = "") -> Path:
        return self._render("api_test.j2", context, source, "api")

    def render_ui_cases(self, context: dict[str, Any], source: str = "") -> Path:
        return self._render("ui_test.j2", context, source, "ui")

    def render_feature_file(self, context: dict[str, Any], source: str = "") -> Path:
        return self._render("feature.j2", context, source, "feature", ext=".feature")

    def _render(
        self, template_name: str, context: dict[str, Any], source: str, prefix: str, ext: str = ".yml"
    ) -> Path:
        template = self._env.get_template(template_name)
        content = template.render(
            **context,
            source=source,
            generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        )
        slug = slugify(source or prefix)
        out_path = self.output_dir / f"{prefix}_{slug}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{ext}"
        out_path.write_text(content, encoding="utf-8")
        log.info("Template rendered", template=template_name, output=str(out_path))
        return out_path


class TestCaseLoader:
    """Loads TestCase objects from rendered YAML files."""

    @staticmethod
    def load(yaml_path: Path) -> list[TestCase]:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        cases: list[TestCase] = []
        for item in raw.get("test_cases", []):
            try:
                cases.append(TestCase(**item))
            except Exception as exc:
                log.warning("Skipping invalid test case", error=str(exc), item=item.get("id"))
        return cases
