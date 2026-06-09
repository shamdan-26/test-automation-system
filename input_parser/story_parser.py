from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from input_parser.base_parser import BaseParser, ParsedInput


class StoryParser(BaseParser):
    """
    Parses user stories in plain text or YAML format.

    Plain text format expected:
        Story: <title>
        As a <actor> I want <goal> so that <benefit>
        Acceptance Criteria:
          - <criterion>
        Endpoints:
          - method: GET
            endpoint: /api/resource
            expected_status: 200
    """

    name = "story"

    def can_parse(self, source: Path | str) -> bool:
        path = Path(source)
        if path.suffix.lower() in (".yml", ".yaml"):
            return True
        if path.suffix.lower() in (".txt", ".md"):
            text = path.read_text(encoding="utf-8")
            return bool(re.search(r"(?i)^\s*(story|as a|acceptance criteria)", text, re.MULTILINE))
        return False

    def parse(self, source: Path | str) -> list[ParsedInput]:
        path = Path(source)
        if path.suffix.lower() in (".yml", ".yaml"):
            return self._parse_yaml(path)
        return self._parse_text(path.read_text(encoding="utf-8"), path.name)

    def _parse_yaml(self, path: Path) -> list[ParsedInput]:
        data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        stories = data if isinstance(data, list) else [data]
        return [ParsedInput({**s, "source": path.name}) for s in stories if isinstance(s, dict)]

    def _parse_text(self, text: str, source: str) -> list[ParsedInput]:
        inputs: list[ParsedInput] = []
        blocks = re.split(r"(?im)^Story\s*:", text)
        for block in blocks[1:]:
            lines = block.strip().splitlines()
            title = lines[0].strip() if lines else "Untitled Story"
            story_id = re.sub(r"\W+", "_", title.lower())[:40]

            criteria = re.findall(r"(?m)^\s*[-*]\s+(.+)", block)

            endpoints: list[dict[str, Any]] = []
            ep_section = re.search(r"(?is)endpoints?\s*:(.*?)(?=\n[A-Z]|\Z)", block)
            if ep_section:
                for line in ep_section.group(1).splitlines():
                    m = re.match(r"\s*(GET|POST|PUT|PATCH|DELETE)\s+(\S+)", line, re.I)
                    if m:
                        endpoints.append({
                            "method": m.group(1).upper(),
                            "endpoint": m.group(2),
                            "title": f"{m.group(1).upper()} {m.group(2)}",
                            "expected_status": 200,
                        })

            inputs.append(ParsedInput({
                "source": source,
                "story_id": story_id,
                "title": title,
                "acceptance_criteria": criteria,
                "endpoints": endpoints,
                "test_type": "api_rest" if endpoints else "generic",
                "tags": ["story", story_id],
            }))
        return inputs
