import time
from pathlib import Path

import pytest

from tests.helpers import load_module


def test_governance_repository_appends_jsonl_records(tmp_path):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    repo = module.GovernanceRepository(base_dir=tmp_path)

    repo.append("job_runs", {"job_name": "ingest", "status": "completed"})
    repo.append("cache_build_run", {"job_name": "materialize", "status": "completed"})

    job_log = tmp_path / "job_runs.jsonl"
    build_log = tmp_path / "cache_build_run.jsonl"
    assert job_log.exists()
    assert build_log.exists()
    assert "ingest" in job_log.read_text(encoding="utf-8")
    assert "materialize" in build_log.read_text(encoding="utf-8")


def test_build_run_record_uses_fresh_created_at_per_instance():
    module = load_module("backend.app.tasks.build_runs", "backend/app/tasks/build_runs.py")

    first = module.BuildRunRecord(job_name="materialize", status="completed")
    time.sleep(0.001)
    second = module.BuildRunRecord(job_name="materialize", status="completed")

    assert first.created_at != second.created_at


def test_append_many_atomic_rolls_back_without_deleting_existing_records(tmp_path, monkeypatch):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    repo = module.GovernanceRepository(base_dir=tmp_path)
    repo.append(module.CACHE_BUILD_RUN_STREAM, {"job_name": "existing", "status": "completed"})

    original_append_unlocked = repo._append_unlocked

    def failing_append_unlocked(stream: str, payload: dict[str, object]):
        if stream == module.CACHE_MANIFEST_STREAM:
            raise RuntimeError("manifest failed")
        return original_append_unlocked(stream, payload)

    monkeypatch.setattr(repo, "_append_unlocked", failing_append_unlocked)

    with pytest.raises(RuntimeError, match="manifest failed"):
        repo.append_many_atomic(
            [
                (module.CACHE_BUILD_RUN_STREAM, {"job_name": "new", "status": "completed"}),
                (module.CACHE_MANIFEST_STREAM, {"cache_key": "k"}),
            ]
        )

    records = repo.read_all(module.CACHE_BUILD_RUN_STREAM)
    assert records == [{"job_name": "existing", "status": "completed"}]


def test_governance_batch_lock_uses_canonical_base_dir(tmp_path):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    relative_repo = module.GovernanceRepository(base_dir=tmp_path)
    absolute_repo = module.GovernanceRepository(base_dir=tmp_path.resolve())

    assert relative_repo._batch_lock().key == absolute_repo._batch_lock().key
