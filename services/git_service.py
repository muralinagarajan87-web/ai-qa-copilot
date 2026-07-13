from __future__ import annotations

from agents.base.schemas import ReviewComment
from services.interfaces import PullRequestRef


class GitService:
    """Structural stub -- satisfies GitServiceProtocol so the rest of the
    system can depend on the interface today. Every method raises until the
    GitHub PR-comment feature is actually built (docs/architecture/design.md SS3).
    Kept as a real class (not just the Protocol) so it can be registered in
    the DI container now and swapped for a working implementation later
    without touching any caller.
    """

    def create_branch(self, run_id: str, base: str = "main") -> str:
        raise NotImplementedError("GitService is not implemented yet")

    def commit(self, branch: str, message: str, files: list[str]) -> str:
        raise NotImplementedError("GitService is not implemented yet")

    def push(self, branch: str) -> None:
        raise NotImplementedError("GitService is not implemented yet")

    def open_pull_request(self, branch: str, title: str, body: str) -> PullRequestRef:
        raise NotImplementedError("GitService is not implemented yet")

    def comment_on_pull_request(self, pr: PullRequestRef, comments: list[ReviewComment]) -> None:
        raise NotImplementedError("GitService is not implemented yet")
