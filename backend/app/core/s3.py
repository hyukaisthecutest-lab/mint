from __future__ import annotations
from pathlib import Path
from app.core.config import settings


def _base() -> Path:
    p = Path(settings.LOCAL_RECEIPTS_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def upload_receipt(key: str, data: bytes, content_type: str) -> None:
    dest = _base() / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def download_receipt(key: str) -> bytes:
    return (_base() / key).read_bytes()


def delete_receipt(key: str) -> None:
    try:
        (_base() / key).unlink(missing_ok=True)
    except Exception:
        pass
