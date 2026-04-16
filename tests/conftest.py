"""Pytest hooks: skip storage migrations on app/worker startup during unit tests."""

from __future__ import annotations

import os

os.environ.setdefault("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", "1")
os.environ.setdefault("MOSS_SKIP_POSTGRES_MIGRATIONS", "1")
