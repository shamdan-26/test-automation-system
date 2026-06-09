from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from models.test_result import RunSummary
from utils.logger import get_logger


class BaseReporter(ABC):
    """Contract every reporter must implement."""

    name: str = "base"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.output_dir = Path(config.get("output_dir", f"outputs/reports/{self.name}"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log = get_logger(f"reporter.{self.name}")

    @abstractmethod
    def generate(self, summary: RunSummary) -> Path:
        """Generate the report and return the path to the output file."""

    def is_enabled(self) -> bool:
        return bool(self.config.get("enabled", True))
