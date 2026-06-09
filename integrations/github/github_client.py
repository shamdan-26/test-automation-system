from __future__ import annotations

from typing import Any

from github import Github, GithubException
from github.Repository import Repository

from utils.logger import get_logger
from utils.retry import retry

log = get_logger("integration.github")


class GitHubClient:
    """GitHub integration — token and repo are resolved from wizard config at runtime."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self._gh: Github | None = None
        self._repo: Repository | None = None

    def connect(self) -> None:
        self._gh = Github(self.config["token"])
        self._repo = self._gh.get_repo(self.config["repository"])
        log.info("GitHub connected", repo=self.config["repository"])

    @retry(attempts=3, delay=2.0, exceptions=(GithubException,))
    def post_commit_status(
        self,
        commit_sha: str,
        state: str,         # "success" | "failure" | "pending" | "error"
        description: str,
        context: str = "test-automation-system",
    ) -> None:
        assert self._repo is not None, "Call connect() first"
        commit = self._repo.get_commit(commit_sha)
        commit.create_status(
            state=state,
            description=description[:139],   # GitHub 140-char limit
            context=context,
        )
        log.info("Commit status posted", sha=commit_sha[:7], state=state)

    @retry(attempts=3, delay=2.0, exceptions=(GithubException,))
    def create_issue(self, title: str, body: str, labels: list[str] | None = None) -> str:
        assert self._repo is not None
        issue = self._repo.create_issue(
            title=title,
            body=body,
            labels=labels or [],
        )
        log.info("GitHub issue created", issue=issue.number, url=issue.html_url)
        return issue.html_url

    def get_open_issues(self, label: str = "automated") -> list[dict[str, Any]]:
        assert self._repo is not None
        return [
            {"number": i.number, "title": i.title, "url": i.html_url}
            for i in self._repo.get_issues(state="open", labels=[label])
        ]
