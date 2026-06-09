from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from models.test_result import RunSummary
from reporters.base_reporter import BaseReporter


class HtmlReporter(BaseReporter):
    name = "html"

    def generate(self, summary: RunSummary) -> Path:
        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
        template = env.get_template("report.html.j2")

        html = template.render(summary=summary, generated_at=datetime.utcnow())
        filename = f"report_{summary.run_id}.html"
        out_path = self.output_dir / filename
        out_path.write_text(html, encoding="utf-8")

        self.log.info("HTML report written", path=str(out_path))
        return out_path
