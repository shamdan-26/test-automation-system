from __future__ import annotations

from typing import Any

from integrations.bug_tracker.base_tracker import BaseBugTracker


def create_tracker(tracker_type: str, config: dict[str, Any]) -> BaseBugTracker:
    """Instantiate the correct bug tracker based on type string from wizard config."""
    if tracker_type == "jira":
        from integrations.bug_tracker.jira_client import JiraClient
        return JiraClient(config)
    raise ValueError(f"Unsupported tracker type: {tracker_type!r}. Supported: jira")
