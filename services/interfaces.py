from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel

from agents.base.schemas import ArtifactKind, ArtifactRef, ReviewComment


class FileRef(BaseModel):
    path: str
    size_bytes: int


class PullRequestRef(BaseModel):
    number: int
    url: str
    branch: str


class DiffResult(BaseModel):
    additions: int
    deletions: int
    unified_diff: str


class FileServiceProtocol(Protocol):
    """The only component permitted to touch disk for generated content.
    Automation, Reviewer, and any future agent (Bug Analyzer, Migration
    Agent) all go through this instead of calling open() themselves.
    """

    def write(self, path: str, content: str, run_id: str) -> FileRef: ...
    def read(self, path: str) -> str: ...
    def list(self, directory: str) -> list[str]: ...
    def delete(self, path: str) -> None: ...
    def modified_at(self, path: str) -> datetime: ...


class GitServiceProtocol(Protocol):
    """Interface only -- see services/git_service.py. No implementation
    until the GitHub PR-comment feature is built (docs/architecture/design.md SS3).
    """

    def create_branch(self, run_id: str, base: str = "main") -> str: ...
    def commit(self, branch: str, message: str, files: list[str]) -> str: ...
    def push(self, branch: str) -> None: ...
    def open_pull_request(self, branch: str, title: str, body: str) -> PullRequestRef: ...
    def comment_on_pull_request(self, pr: PullRequestRef, comments: list[ReviewComment]) -> None: ...


class ArtifactManagerProtocol(Protocol):
    def save(
        self, run_id: str, kind: ArtifactKind, content: bytes | str, version: int | None = None
    ) -> ArtifactRef: ...
    def load(self, ref: ArtifactRef) -> bytes: ...
    def list_versions(self, run_id: str, kind: ArtifactKind) -> list[ArtifactRef]: ...
    def compare(self, ref_a: ArtifactRef, ref_b: ArtifactRef) -> DiffResult: ...
    def delete(self, ref: ArtifactRef) -> None: ...
    def saved_at(self, ref: ArtifactRef) -> datetime: ...
