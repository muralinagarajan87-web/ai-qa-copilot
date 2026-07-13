from __future__ import annotations

import difflib
from datetime import datetime

from agents.base.schemas import ArtifactKind, ArtifactRef
from services.file_service import FileService
from services.interfaces import DiffResult


class ArtifactManager:
    """Save / version / load / compare / delete for every artifact the
    system produces (PRD, test cases, generated code, review comments).

    No separate database -- versions are derived from the filesystem layout
    (`artifacts/runs/<run_id>/<kind>/v<n>.json`) via FileService, so there is
    exactly one place artifact state can live. This is also what the
    Revision History read-model (backend/app/domain/revision_history.py)
    is built on top of.
    """

    def __init__(self, file_service: FileService, base_dir: str = "artifacts/runs"):
        self.file_service = file_service
        self.base_dir = base_dir

    def _dir(self, run_id: str, kind: ArtifactKind) -> str:
        return f"{self.base_dir}/{run_id}/{kind.value}"

    def save(self, run_id: str, kind: ArtifactKind, content: bytes | str, version: int | None = None) -> ArtifactRef:
        if version is None:
            version = self._next_version(run_id, kind)
        path = f"{self._dir(run_id, kind)}/v{version}.json"
        text = content if isinstance(content, str) else content.decode("utf-8")
        self.file_service.write(path, text, run_id)
        return ArtifactRef(run_id=run_id, kind=kind, version=version, path=path)

    def load(self, ref: ArtifactRef) -> bytes:
        return self.file_service.read(ref.path).encode("utf-8")

    def list_versions(self, run_id: str, kind: ArtifactKind) -> list[ArtifactRef]:
        refs = []
        for file_path in self.file_service.list(self._dir(run_id, kind)):
            stem = file_path.rsplit("/", 1)[-1].removesuffix(".json")
            if stem.startswith("v") and stem[1:].isdigit():
                refs.append(ArtifactRef(run_id=run_id, kind=kind, version=int(stem[1:]), path=file_path))
        return sorted(refs, key=lambda ref: ref.version)

    def compare(self, ref_a: ArtifactRef, ref_b: ArtifactRef) -> DiffResult:
        text_a = self.load(ref_a).decode("utf-8").splitlines(keepends=True)
        text_b = self.load(ref_b).decode("utf-8").splitlines(keepends=True)
        diff = list(difflib.unified_diff(text_a, text_b, fromfile=ref_a.path, tofile=ref_b.path))
        additions = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
        deletions = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
        return DiffResult(additions=additions, deletions=deletions, unified_diff="".join(diff))

    def delete(self, ref: ArtifactRef) -> None:
        self.file_service.delete(ref.path)

    def saved_at(self, ref: ArtifactRef) -> datetime:
        return self.file_service.modified_at(ref.path)

    def _next_version(self, run_id: str, kind: ArtifactKind) -> int:
        existing = self.list_versions(run_id, kind)
        return (existing[-1].version + 1) if existing else 1
