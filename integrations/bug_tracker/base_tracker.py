from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from models.bug_report import BugReport
from utils.logger import get_logger


class BaseBugTracker(ABC):
    """Contract every bug tracker integration must implement."""

    name: str = "base"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.log = get_logger(f"tracker.{self.name}")

    @abstractmethod
    def connect(self) -> None:
        """Establish connection / authenticate."""

    @abstractmethod
    def submit_bug(self, bug: BugReport) -> str:
        """Create a bug and return the tracker issue ID/key."""

    @abstractmethod
    def update_bug(self, tracker_id: str, fields: dict[str, Any]) -> None:
        """Update an existing bug by tracker ID."""

    @abstractmethod
    def find_duplicate(self, bug: BugReport) -> str | None:
        """Return tracker ID if a duplicate already exists, else None."""

    def is_enabled(self) -> bool:
        return bool(self.config.get("enabled", False))
