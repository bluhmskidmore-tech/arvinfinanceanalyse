from pathlib import Path

from tests.helpers import load_module


def _load_governance_repo_module():
    return load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )


def test_read_all_jsonl_cache_hit(tmp_path, monkeypatch):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    repo.append("job_runs", {"job_name": "ingest", "status": "completed"})

    read_count = {"n": 0}
    original_read_text = Path.read_text

    def counting_read_text(self, *args, **kwargs):
        read_count["n"] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)

    first = repo.read_all("job_runs")
    second = repo.read_all("job_runs")

    assert first == second
    assert read_count["n"] == 1


def test_read_all_jsonl_cache_invalidates_after_append(tmp_path, monkeypatch):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    repo.append("job_runs", {"job_name": "ingest", "status": "completed"})

    read_count = {"n": 0}
    original_read_text = Path.read_text

    def counting_read_text(self, *args, **kwargs):
        read_count["n"] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)

    repo.read_all("job_runs")
    assert read_count["n"] == 1

    repo.append("job_runs", {"job_name": "follow-up", "status": "running"})
    rows = repo.read_all("job_runs")

    assert read_count["n"] == 2
    assert len(rows) == 2
    assert rows[-1]["job_name"] == "follow-up"


def test_read_all_jsonl_cache_returns_mutation_safe_copies(tmp_path):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    repo.append("job_runs", {"job_name": "ingest", "status": "completed"})

    rows = repo.read_all("job_runs")
    rows[0]["job_name"] = "mutated"

    rows_again = repo.read_all("job_runs")
    assert rows_again[0]["job_name"] == "ingest"
