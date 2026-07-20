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


def test_latest_jsonl_helpers_bypass_read_all_and_isolate_nested_mutation(tmp_path, monkeypatch):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    repo.append(
        module.CACHE_MANIFEST_STREAM,
        {
            "cache_key": "demo:key",
            "report_date": "2026-01-31",
            "source_version": "sv_latest",
            "lineage": {"steps": [{"name": "manifest-latest"}]},
            "custom": {"keep": [1, 2, 3]},
        },
    )
    repo.append(
        module.CACHE_MANIFEST_STREAM,
        {
            "cache_key": "demo:key",
            "report_date": "2026-02-28",
            "source_version": "sv_wrong_date_decoy",
        },
    )
    repo.append(
        module.CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "run-latest",
            "job_name": "job-a",
            "status": "completed",
            "cache_key": "demo:key",
            "report_date": "2026-01-31",
            "source_version": "sv_latest",
            "lineage": {"steps": [{"name": "run-latest"}]},
        },
    )
    repo.append(
        module.CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "run-running-decoy",
            "job_name": "job-a",
            "status": "running",
            "cache_key": "demo:key",
            "report_date": "2026-01-31",
            "source_version": "sv_running",
        },
    )
    repo.append(
        module.CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "run-empty-source-decoy",
            "job_name": "job-a",
            "status": "completed",
            "cache_key": "demo:key",
            "report_date": "2026-01-31",
            "source_version": " ",
        },
    )

    repo.read_all(module.CACHE_MANIFEST_STREAM)
    repo.read_all(module.CACHE_BUILD_RUN_STREAM)

    def fail_read_all(*_args, **_kwargs):
        raise AssertionError("latest helpers must not materialize read_all")

    monkeypatch.setattr(repo, "read_all", fail_read_all)

    manifest = repo.read_latest_manifest(" demo:key ", report_date=" 2026-01-31 ")
    completed = repo.read_latest_completed_run(
        " demo:key ",
        job_name=" job-a ",
        report_date=" 2026-01-31 ",
        require_source_version=True,
    )
    assert manifest is not None
    assert completed is not None
    assert manifest["source_version"] == "sv_latest"
    assert completed["run_id"] == "run-latest"

    manifest["lineage"]["steps"][0]["name"] = "mutated"
    manifest["custom"]["keep"].append(4)
    completed["lineage"]["steps"][0]["name"] = "mutated"

    manifest_again = repo.read_latest_manifest("demo:key", report_date="2026-01-31")
    completed_again = repo.read_latest_completed_run(
        "demo:key",
        job_name="job-a",
        report_date="2026-01-31",
        require_source_version=True,
    )
    assert manifest_again is not None
    assert completed_again is not None
    assert manifest_again["lineage"] == {"steps": [{"name": "manifest-latest"}]}
    assert manifest_again["custom"] == {"keep": [1, 2, 3]}
    assert completed_again["lineage"] == {"steps": [{"name": "run-latest"}]}


def test_latest_jsonl_cache_invalidates_after_append_and_skips_newer_decoys(tmp_path, monkeypatch):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    repo.append(
        module.CACHE_MANIFEST_STREAM,
        {"cache_key": "demo:key", "report_date": "2026-01-31", "source_version": "sv_old"},
    )
    assert repo.read_latest_manifest("demo:key", report_date="2026-01-31")["source_version"] == "sv_old"

    repo.append(
        module.CACHE_MANIFEST_STREAM,
        {"cache_key": "demo:key", "report_date": "2026-01-31", "source_version": "sv_new"},
    )
    repo.append(
        module.CACHE_MANIFEST_STREAM,
        {"cache_key": "demo:key", "report_date": "2026-02-28", "source_version": "sv_decoy"},
    )

    def fail_read_all(*_args, **_kwargs):
        raise AssertionError("latest helpers must refresh their private tuple cache directly")

    monkeypatch.setattr(repo, "read_all", fail_read_all)

    latest = repo.read_latest_manifest("demo:key", report_date="2026-01-31")
    assert latest is not None
    assert latest["source_version"] == "sv_new"


def test_latest_jsonl_lookup_uses_cache_key_index_instead_of_full_scan(tmp_path, monkeypatch):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)

    for index in range(200):
        repo.append(
            module.CACHE_MANIFEST_STREAM,
            {
                "cache_key": f"noise:{index}",
                "report_date": "2026-01-31",
                "source_version": f"sv_noise_{index}",
            },
        )
    repo.append(
        module.CACHE_MANIFEST_STREAM,
        {
            "cache_key": "demo:key",
            "report_date": "2026-01-31",
            "source_version": "sv_target",
        },
    )

    inspected_keys: list[str] = []
    original_read_latest_row = module.GovernanceRepository._read_latest_row

    def wrapping_read_latest_row(self, stream, matches, cache_key=None):
        def tracked(row: dict[str, object]) -> bool:
            inspected_keys.append(str(row.get("cache_key") or ""))
            return matches(row)

        return original_read_latest_row(self, stream, tracked, cache_key=cache_key)

    monkeypatch.setattr(
        module.GovernanceRepository,
        "_read_latest_row",
        wrapping_read_latest_row,
    )

    latest = repo.read_latest_manifest("demo:key", report_date="2026-01-31")

    assert latest is not None
    assert latest["source_version"] == "sv_target"
    assert inspected_keys == ["demo:key"]
