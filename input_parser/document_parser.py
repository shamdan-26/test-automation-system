from __future__ import annotations

from pathlib import Path

import PyPDF2
import yaml
from docx import Document

from input_parser.base_parser import BaseParser, ParsedInput


class DocumentParser(BaseParser):
    """Parses PDF, Word (.docx), plain text, and YAML files into structured test inputs."""

    name = "document"
    _SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".yml", ".yaml"}

    def can_parse(self, source: Path | str) -> bool:
        return Path(source).suffix.lower() in self._SUPPORTED

    def parse(self, source: Path | str) -> list[ParsedInput]:
        path = Path(source)
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            text = self._read_pdf(path)
        elif suffix == ".docx":
            text = self._read_docx(path)
        elif suffix in (".yml", ".yaml"):
            return self._parse_yaml(path)
        else:
            text = path.read_text(encoding="utf-8")

        return [ParsedInput({"source": path.name, "raw_text": text, "test_type": "api_rest"})]

    def _read_pdf(self, path: Path) -> str:
        reader = PyPDF2.PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _read_docx(self, path: Path) -> str:
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    def _parse_yaml(self, path: Path) -> list[ParsedInput]:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(data, list):
            return [ParsedInput({**item, "source": path.name}) for item in data]
        return [ParsedInput({**data, "source": path.name})]
