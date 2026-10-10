"""Shared streaming content hash for source-file fingerprints.

Mirrors the fixed pattern in
``backend/app/core_finance/source_preview_parsers.py`` (``_sha256_file``)
so service-level source versions can include a content hash instead of
relying on name/size/mtime alone.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_SOURCE_HASH_CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        while chunk := source_file.read(_SOURCE_HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()
