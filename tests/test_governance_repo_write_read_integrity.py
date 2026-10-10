"""Governance repo integrity guards: corrupted JSONL reads and dual-write rollback.

Covers:
- torn trailing JSONL line (interrupted append) is skipped with a warning;
- corrupted interior JSONL line raises a stable RuntimeError with file/line context;
- SQL commit failure in ``append`` rolls the JSONL write back (no divergence).
"""

from __future__ import annotations

import json
import logging

import pytest
from sqlalchemy import event

from tests.helpers import load_module


def _load_governance_repo_module():
    return load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )


def test_read_all_skips_truncated_trailing_jsonl_line(tmp_path, caplog):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    target = tmp_path / "job_runs.jsonl"
    target.write_text(
        json.dumps({"job_name": "first"}) + "\n"
        + json.dumps({"job_name": "second"}) + "\n"
        + '{"job_name": "torn-wri',  # interrupted append: no trailing newline
        encoding="utf-8",
    )

    with caplog.at_level(
        logging.WARNING,
        logger="backend.app.repositories.governance_repo",
    ):
        rows = repo.read_all("job_runs")

    assert [row["job_name"] for row in rows] == ["first", "second"]
    assert any(
        "truncated trailing governance JSONL line" in message
        for message in caplog.messages
    )


def test_read_all_wraps_corrupted_interior_jsonl_line_with_context(tmp_path):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    target = tmp_path / "job_runs.jsonl"
    target.write_text(
        json.dumps({"job_name": "first"}) + "\n"
        + "{not json}\n"
        + json.dumps({"job_name": "third"}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match=r"Corrupted governance JSONL line at .*job_runs\.jsonl:2",
    ) as excinfo:
        repo.read_all("job_runs")

    assert isinstance(excinfo.value.__cause__, json.JSONDecodeError)


def test_read_all_wraps_corrupted_final_line_with_newline_as_corruption(tmp_path):
    """A malformed final line that *is* newline-terminated is corruption,
    not a torn write, and must fail closed like an interior corrupted line."""
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    target = tmp_path / "job_runs.jsonl"
    target.write_text(
        json.dumps({"job_name": "first"}) + "\n" + "{not json}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match=r"Corrupted governance JSONL line at .*job_runs\.jsonl:2",
    ):
        repo.read_all("job_runs")


def test_append_rolls_back_jsonl_when_sql_commit_fails(tmp_path):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(
        base_dir=tmp_path,
        sql_dsn=f"sqlite:///{tmp_path / 'governance.sqlite'}",
        backend_mode="sql-authority",
    )

    def fail_commit(_connection):
        raise RuntimeError("simulated SQL commit failure")

    # Fires on transaction commit (context-manager exit), i.e. after both the
    # SQL insert and the JSONL append already succeeded.
    event.listen(repo._sql_engine, "commit", fail_commit)

    with pytest.raises(RuntimeError, match="simulated SQL commit failure"):
        repo.append(
            module.CACHE_MANIFEST_STREAM,
            {"cache_key": "demo:key", "source_version": "sv_1"},
        )

    jsonl_target = tmp_path / f"{module.CACHE_MANIFEST_STREAM}.jsonl"
    assert (
        not jsonl_target.exists()
        or jsonl_target.read_text(encoding="utf-8") == ""
    ), "JSONL row must be rolled back when the SQL commit fails"
    event.remove(repo._sql_engine, "commit", fail_commit)
    assert repo.read_all(module.CACHE_MANIFEST_STREAM) == []
