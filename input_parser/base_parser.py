from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from utils.logger import get_logger


class ParsedInput(dict):  # type: ignore[type-arg]
    """Typed alias for the structured dict returned by every parser."""


class BaseParser(ABC):
    """Contract every input parser must implement."""

    name: str = "base"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.log = get_logger(f"parser.{self.name}")

    @abstractmethod
    def can_parse(self, source: Path | str) -> bool:
        """Return True if this parser handles the given source."""

    @abstractmethod
    def parse(self, source: Path | str) -> list[ParsedInput]:
        """Parse the source and return a list of structured input dicts."""
