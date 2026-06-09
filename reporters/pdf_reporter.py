from __future__ import annotations

from pathlib import Path

from weasyprint import HTML

from models.test_result import RunSummary
from reporters.base_reporter import BaseReporter
from reporters.html_reporter import HtmlReporter


class PdfReporter(BaseReporter):
    """Converts the HTML report to PDF via WeasyPrint."""

    name = "pdf"

    def generate(self, summary: RunSummary) -> Path:
        html_config = {**self.config, "output_dir": str(self.output_dir)}
        html_reporter = HtmlReporter(html_config)
        html_path = html_reporter.generate(summary)

        pdf_path = self.output_dir / f"report_{summary.run_id}.pdf"
        HTML(filename=str(html_path)).write_pdf(str(pdf_path))

        self.log.info("PDF report written", path=str(pdf_path))
        return pdf_path
