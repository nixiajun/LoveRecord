from __future__ import annotations
from pathlib import Path

from app.config import settings
from app.integrations.base import StorageProvider


class LocalStorageProvider(StorageProvider):
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base = Path(base_dir or settings.upload_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, key: str, data: bytes) -> str:
        path = self._base / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path.resolve())
