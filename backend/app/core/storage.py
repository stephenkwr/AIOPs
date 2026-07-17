"""Raw-file storage behind a small interface.

LocalStorage (dev) writes under STORAGE_DIR. In production this swaps for a
SupabaseStorage implementation with the same three methods — nothing else changes.
"""

from pathlib import Path
from typing import Protocol

from app.config import settings


class Storage(Protocol):
    def save(self, key: str, data: bytes) -> None: ...
    def load(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / key

    def save(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def load(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()


def get_storage() -> Storage:
    return LocalStorage(settings.storage_dir)
