from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pytest

from backend.app.governance.settings import get_settings
from tests.helpers import load_module
from tests.test_balance_analysis_materialize_flow import _seed_snapshot_and_fx_tables


@dataclass(frozen=True)
class BalanceAnalysisSeed:
    duckdb_path: Path
    governance_dir: Path


def _clear_settings_caches() -> None:
    get_settings.cache_clear()
    settings_mod = sys.modules.get("backend.app.governance.settings")
    module_get_settings = getattr(settings_mod, "get_settings", None)
    if module_get_settings is not None and hasattr(module_get_settings, "cache_clear"):
        module_get_settings.cache_clear()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_files(root: Path) -> dict[str, tuple[int, int, str]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            path.stat().st_mtime_ns,
            _file_sha256(path),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".locks" not in path.parts
    }


@pytest.fixture(scope="session")
def balance_analysis_shared_materialized_seed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[BalanceAnalysisSeed]:
    seed_dir = tmp_path_factory.mktemp("balance-analysis-shared-seed")
    duckdb_path = seed_dir / "moss.duckdb"
    governance_dir = seed_dir / "governance"

    _seed_snapshot_and_fx_tables(str(duckdb_path))
    task_mod = load_module(
        "backend.app.tasks.balance_analysis_materialize",
        "backend/app/tasks/balance_analysis_materialize.py",
    )
    original_fx_materialize = task_mod.materialize_fx_mid_for_report_date.fn
    task_mod.materialize_fx_mid_for_report_date.fn = lambda **_kwargs: None
    try:
        task_mod.materialize_balance_analysis_facts.fn(
            report_date="2025-12-31",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )
    finally:
        task_mod.materialize_fx_mid_for_report_date.fn = original_fx_materialize
        _clear_settings_caches()

    before = _snapshot_files(seed_dir)
    yield BalanceAnalysisSeed(duckdb_path=duckdb_path, governance_dir=governance_dir)
    after = _snapshot_files(seed_dir)
    if after != before:
        changed = sorted(set(before) ^ set(after))
        changed.extend(path for path in sorted(before) if path in after and before[path] != after[path])
        pytest.fail(
            "balance_analysis shared materialized seed was modified: "
            + ", ".join(changed[:10])
        )


@pytest.fixture()
def balance_analysis_shared_materialized_read_seed(
    balance_analysis_shared_materialized_seed: BalanceAnalysisSeed,
) -> Iterator[BalanceAnalysisSeed]:
    _clear_settings_caches()
    yield balance_analysis_shared_materialized_seed
    _clear_settings_caches()
