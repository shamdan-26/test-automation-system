from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class BugSeverity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class BugStatus(str, Enum):
    OPEN = "Open"
    SUBMITTED = "Submitted"
    DUPLICATE = "Duplicate"
    FAILED_SUBMISSION = "FailedSubmission"


class BugReport(BaseModel):
    title: str
    description: str
    severity: BugSeverity = BugSeverity.MEDIUM
    environment: str = ""
    test_case_id: str = ""
    engine: str = ""
    steps_to_reproduce: list[str] = Field(default_factory=list)
    actual_result: str = ""
    expected_result: str = ""
    error_message: str = ""
    stacktrace: str = ""
    attachments: list[Path] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    git_commit: str = ""
    git_branch: str = ""
    status: BugStatus = BugStatus.OPEN
    tracker_id: str = ""        # Jira issue key or TFS work item ID
    tracker_url: str = ""

    def to_jira_payload(self, project_key: str, issue_type: str = "Bug") -> dict:
        body = (
            f"*Environment:* {self.environment}\n\n"
            f"*Test Case ID:* {self.test_case_id}\n\n"
            f"*Git Commit:* {self.git_commit} ({self.git_branch})\n\n"
            f"*Steps to Reproduce:*\n"
            + "\n".join(f"# {s}" for s in self.steps_to_reproduce)
            + f"\n\n*Actual Result:*\n{self.actual_result}\n\n"
            f"*Expected Result:*\n{self.expected_result}\n\n"
            f"*Error:*\n{{code}}{self.error_message}\n{self.stacktrace}{{code}}"
        )
        return {
            "fields": {
                "project": {"key": project_key},
                "summary": self.title,
                "description": body,
                "issuetype": {"name": issue_type},
                "priority": {"name": self.severity.value},
                "labels": self.labels,
            }
        }
