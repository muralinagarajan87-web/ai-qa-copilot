from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from services.interfaces import FileRef

logger = logging.getLogger("file_service")


class FileService:
    """Disk I/O scoped under a single root (the repo root). All paths passed
    in are relative to that root and are resolved defensively so a caller
    can never write outside of it.
    """

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        resolved = (self.root / path).resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise ValueError(f"Path '{path}' escapes FileService root '{self.root}'")
        return resolved

    def write(self, path: str, content: str, run_id: str) -> FileRef:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        ref = FileRef(path=str(target.relative_to(self.root)), size_bytes=target.stat().st_size)
        logger.info("write run_id=%s path=%s bytes=%d", run_id, ref.path, ref.size_bytes)
        return ref

    def read(self, path: str) -> str:
        return self._resolve(path).read_text()

    def list(self, directory: str) -> list[str]:
        base = self._resolve(directory)
        if not base.exists():
            return []
        return sorted(str(p.relative_to(self.root)) for p in base.rglob("*") if p.is_file())

    def delete(self, path: str) -> None:
        target = self._resolve(path)
        if target.exists():
            target.unlink()

    def modified_at(self, path: str) -> datetime:
        target = self._resolve(path)
        return datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc)
