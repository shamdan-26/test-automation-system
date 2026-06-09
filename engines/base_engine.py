from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from models.test_case import TestCase
from models.test_result import EngineReport
from utils.logger import get_logger


class BaseEngine(ABC):
    """Contract every test engine must implement."""

    name: str = "base"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.log = get_logger(f"engine.{self.name}")

    @abstractmethod
    def setup(self) -> None:
        """One-time setup before any tests run (sessions, browsers, etc.)."""

    @abstractmethod
    def teardown(self) -> None:
        """Cleanup after all tests have run."""

    @abstractmethod
    def run(self, test_cases: list[TestCase]) -> EngineReport:
        """Execute test cases and return a populated EngineReport."""

    def is_enabled(self) -> bool:
        return bool(self.config.get("enabled", True))
