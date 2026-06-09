from __future__ import annotations

from pathlib import Path
from typing import Any

from input_parser.base_parser import ParsedInput
from models.test_case import HttpMethod, TestCase, TestStep, TestType, UiTestCase, ApiTestCase
from test_generator.template_engine import TemplateEngine, TestCaseLoader
from utils.helpers import slugify
from utils.logger import get_logger

log = get_logger("test_generator.generator")


class TestCaseGenerator:
    """Converts parsed inputs into TestCase objects via Jinja2 templates."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.engine = TemplateEngine(output_dir)

    def generate(self, parsed_inputs: list[ParsedInput]) -> list[TestCase]:
        all_cases: list[TestCase] = []

        for inp in parsed_inputs:
            test_type = inp.get("test_type", "api_rest")
            if test_type in ("api_rest", "api_soap"):
                cases = self._generate_api(inp)
            elif test_type == "ui":
                cases = self._generate_ui(inp)
            else:
                cases = self._generate_generic(inp)
            all_cases.extend(cases)

        log.info("Test cases generated", count=len(all_cases))
        return all_cases

    def _generate_api(self, inp: ParsedInput) -> list[TestCase]:
        story_id = inp.get("story_id", "")
        source = inp.get("source", "unknown")
        endpoints: list[dict[str, Any]] = inp.get("endpoints", [])
        cases: list[TestCase] = []

        for ep in endpoints:
            tc_id = f"{slugify(story_id or source)}_{slugify(ep.get('endpoint', 'unknown'))}"
            steps = [
                TestStep(order=1, description="Send request", action="request", expected_result=f"HTTP {ep.get('expected_status', 200)}"),
                TestStep(order=2, description="Validate response", action="validate", expected_result="All fields match expected values"),
            ]
            cases.append(TestCase(
                id=tc_id,
                title=ep.get("title", f"API test: {ep.get('endpoint', '')}"),
                description=ep.get("description", ""),
                type=TestType.API_REST,
                tags=inp.get("tags", []),
                priority=ep.get("priority", "medium"),
                steps=steps,
                expected_result=f"HTTP {ep.get('expected_status', 200)} with correct payload",
                story_id=story_id,
                source=source,
                api=ApiTestCase(
                    method=HttpMethod(ep.get("method", "GET").upper()),
                    endpoint=ep.get("endpoint", ""),
                    expected_status=ep.get("expected_status", 200),
                    expected_fields=ep.get("expected_fields", {}),
                    body=ep.get("body"),
                ),
            ))

        yaml_path = self.engine.render_api_cases({"test_cases": [self._to_template_ctx(c) for c in cases]}, source)
        log.info("API test cases rendered", file=str(yaml_path), count=len(cases))
        return cases

    def _generate_ui(self, inp: ParsedInput) -> list[TestCase]:
        source = inp.get("source", "unknown")
        flows: list[dict[str, Any]] = inp.get("flows", [])
        cases: list[TestCase] = []

        for flow in flows:
            tc_id = slugify(f"{inp.get('story_id', source)}_{flow.get('title', 'flow')}")
            raw_steps = flow.get("steps", [])
            steps = [
                TestStep(order=i + 1, description=s.get("description", ""), action=s.get("action", ""), expected_result=s.get("expected", ""))
                for i, s in enumerate(raw_steps)
            ]
            cases.append(TestCase(
                id=tc_id,
                title=flow.get("title", "UI Flow"),
                description=flow.get("description", ""),
                type=TestType.UI,
                tags=inp.get("tags", []),
                priority=flow.get("priority", "medium"),
                steps=steps,
                expected_result=flow.get("expected_result", ""),
                story_id=inp.get("story_id", ""),
                source=source,
                ui=UiTestCase(url=flow.get("url", "/"), steps=steps, assertions=flow.get("assertions", [])),
            ))

        self.engine.render_ui_cases({"test_cases": [self._to_template_ctx(c) for c in cases]}, source)
        return cases

    def _generate_generic(self, inp: ParsedInput) -> list[TestCase]:
        return []

    @staticmethod
    def _to_template_ctx(tc: TestCase) -> dict[str, Any]:
        d = tc.model_dump(mode="json")
        if tc.api:
            d.update(tc.api.model_dump())
        if tc.ui:
            d.update(tc.ui.model_dump())
        return d
