from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from input_parser.base_parser import BaseParser, ParsedInput


class TaskParser(BaseParser):
    """
    Parses task files (YAML or structured plain text) into test inputs.

    YAML format:
        - task_id: TASK-001
          title: Validate login endpoint
          type: api_rest        # api_rest | api_soap | ui | mobile | performance
          endpoints:
            - method: POST
              endpoint: /auth/login
              expected_status: 200
              body: { username: "test", password: "pass" }
              expected_fields: { token: null }
    """

    name = "task"

    def can_parse(self, source: Path | str) -> bool:
        path = Path(source)
        if path.suffix.lower() in (".yml", ".yaml"):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return isinstance(data, list) and any("task_id" in (i or {}) for i in data)
        if path.suffix.lower() in (".txt",):
            return "task:" in path.read_text(encoding="utf-8").lower()
        return False

    def parse(self, source: Path | str) -> list[ParsedInput]:
        path = Path(source)
        if path.suffix.lower() in (".yml", ".yaml"):
            return self._parse_yaml(path)
        return self._parse_text(path.read_text(encoding="utf-8"), path.name)

    def _parse_yaml(self, path: Path) -> list[ParsedInput]:
        tasks: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        return [
            ParsedInput({
                **task,
                "source": path.name,
                "story_id": task.get("task_id", ""),
                "test_type": task.get("type", "api_rest"),
                "tags": ["task", task.get("task_id", "")],
            })
            for task in tasks if isinstance(task, dict)
        ]

    def _parse_text(self, text: str, source: str) -> list[ParsedInput]:
        inputs: list[ParsedInput] = []
        blocks = re.split(r"(?im)^Task\s*:", text)
        for block in blocks[1:]:
            lines = block.strip().splitlines()
            title = lines[0].strip() if lines else "Untitled Task"
            task_id = re.sub(r"\W+", "_", title.lower())[:40]
            inputs.append(ParsedInput({
                "source": source,
                "story_id": task_id,
                "title": title,
                "test_type": "api_rest",
                "endpoints": [],
                "tags": ["task"],
            }))
        return inputs


class ParserRegistry:
    """Picks the correct parser for a given source file."""

    def __init__(self) -> None:
        from input_parser.document_parser import DocumentParser
        from input_parser.story_parser import StoryParser
        self._parsers = [StoryParser(), TaskParser(), DocumentParser()]

    def parse(self, source: Path | str) -> list[ParsedInput]:
        path = Path(source)
        for parser in self._parsers:
            if parser.can_parse(path):
                return parser.parse(path)
        raise ValueError(f"No parser available for: {path}")
