import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script", ["bond_risk_shadow_candidate.py", "bond_risk_shadow_batch.py"])
def test_shadow_cli_help_runs_outside_repo_without_pythonpath(script, tmp_path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.update(
        MOSS_DUCKDB_PATH=str(tmp_path / "unused.duckdb"),
        MOSS_POSTGRES_DSN=f"sqlite:///{(tmp_path / 'unused.db').as_posix()}",
        MOSS_GOVERNANCE_SQL_DSN="",
        MOSS_GOVERNANCE_PATH=str(tmp_path / "governance"),
        MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS="1",
        MOSS_SKIP_POSTGRES_MIGRATIONS="1",
    )
    result = subprocess.run(
        [sys.executable, "-E", str(ROOT / "scripts" / script), "--help"],
        cwd=tmp_path, env=env, text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--source-duckdb-path" in result.stdout
    assert not (tmp_path / "unused.duckdb").exists()
    assert not (tmp_path / "unused.db").exists()
