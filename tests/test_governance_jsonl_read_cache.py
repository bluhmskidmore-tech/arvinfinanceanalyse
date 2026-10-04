from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from tests.helpers import load_module


def _load_governance_repo_module():
    return load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )


@pytest.mark.parametrize("read_method", ["read_all", "read_by_cache_keys", "read_by_run_id"])
def test_slow_snapshot_copy_does_not_block_atomic_append(tmp_path, monkeypatch, read_method):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    stream = module.CACHE_BUILD_RUN_STREAM
    repo.append(stream, {"run_id": "before", "cache_key": "demo:key", "lineage": {"items": [1]}})
    copying, release_copy = Event(), Event()
    original_deepcopy = module.deepcopy

    def paused_copy(row):
        if row.get("run_id") == "before" and not release_copy.is_set():
            copying.set()
            if not release_copy.wait(timeout=5):
                raise AssertionError("test did not release snapshot copy")
        return original_deepcopy(row)

    monkeypatch.setattr(module, "deepcopy", paused_copy)
    def read():
        if read_method == "read_by_run_id":
            return repo.read_by_run_id(stream, "before")
        if read_method == "read_by_cache_keys":
            return repo.read_by_cache_keys(stream, ["demo:key"])
        return repo.read_all(stream)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reader = pool.submit(read)
        try:
            assert copying.wait(timeout=2)
            writer = pool.submit(repo.append_many_atomic, [
                (stream, {"run_id": "after", "cache_key": "demo:key"}),
                (module.CACHE_MANIFEST_STREAM, {"cache_key": "demo:key", "source_version": "after"}),
            ])
            # The writer must complete while the reader is deliberately stuck
            # copying, without exposing a partial atomic batch to the reader.
            writer.result(timeout=2)
        finally:
            release_copy.set()
        snapshot = reader.result(timeout=2)

    assert [row["run_id"] for row in snapshot] == ["before"]
    snapshot[0]["lineage"]["items"].append(2)
    latest = read()
    assert [row["run_id"] for row in latest] == (
        ["before"] if read_method == "read_by_run_id" else ["before", "after"]
    )
    assert latest[0]["lineage"] == {"items": [1]}
    assert repo.read_latest_manifest("demo:key")["source_version"] == "after"


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


def test_run_queries_refresh_after_append_and_cross_process_atomic_replacement(tmp_path):
    import subprocess
    import sys

    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    stream = "agent_run"
    repo.append(stream, {"run_id": "selected", "result": {"items": ["first"]}})
    selected = repo.read_by_run_id(stream, "selected", latest_only=True)
    selected[0]["result"]["items"].append("poison")
    assert repo.read_by_run_id(stream, "selected")[0]["result"] == {"items": ["first"]}

    # Another repository/process shares disk authority, not the service cache.
    module.GovernanceRepository(base_dir=tmp_path).append(
        stream, {"run_id": "selected", "result": {"items": ["after"]}},
    )
    assert repo.read_by_run_id(stream, "selected", latest_only=True)[0]["result"] == {"items": ["after"]}
    target = tmp_path / f"{stream}.jsonl"
    original_version = target.stat()
    script = """
import os
import sys
from pathlib import Path
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.governance.locks import acquire_lock
repo = GovernanceRepository(base_dir=sys.argv[1])
with acquire_lock(repo._batch_lock(), base_dir=repo.base_dir):
    target = Path(repo.base_dir) / "agent_run.jsonl"
    stat = target.stat()
    replacement = target.with_suffix(".replacement")
    replacement.write_bytes(target.read_bytes().replace(b'after', b'final'))
    os.utime(replacement, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    os.replace(replacement, target)
"""
    subprocess.run([sys.executable, "-c", script, str(tmp_path)], check=True, timeout=15)
    assert target.stat().st_size == original_version.st_size
    assert target.stat().st_mtime_ns == original_version.st_mtime_ns
    assert repo.read_by_run_id(stream, "selected", latest_only=True)[0]["result"] == {"items": ["final"]}
    assert repo.read_all(stream)[-1]["result"] == {"items": ["final"]}
    versions = [key for key in module._JSONL_RUN_ID_INDEX if key[0] == str(target.resolve())]
    assert len(versions) == 1


def test_run_index_recovers_when_external_replace_follows_snapshot_read(tmp_path, monkeypatch):
    import json
    import os

    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    repo.append("agent_run", {"run_id": "old", "status": "completed"})
    original_read = module._read_jsonl_rows_cached
    replaced = False
    new_rows = [
        {"run_id": "noise", "status": "queued"},
        {"run_id": "target", "status": "completed"},
    ]

    def read_then_replace(path):
        nonlocal replaced
        rows = original_read(path)
        if not replaced:
            replaced = True
            replacement = path.with_suffix(".replacement")
            replacement.write_text(
                "".join(json.dumps(row) + "\n" for row in new_rows), encoding="utf-8",
            )
            # Emulate an external replacement that does not take our file lock,
            # after old rows were returned but before their version is sampled.
            os.replace(replacement, path)
        return rows

    monkeypatch.setattr(module, "_read_jsonl_rows_cached", read_then_replace)
    assert repo.read_by_run_id("agent_run", "old") == [{"run_id": "old", "status": "completed"}]
    assert repo.read_by_run_id("agent_run", "target", latest_only=True) == [new_rows[1]]
    assert repo.read_by_run_id("agent_run", "old") == []


def test_run_delta_query_filters_before_copy_and_refreshes_after_compaction(tmp_path, monkeypatch):
    import json
    import os
    from backend.app.agent.schemas.agent_run import AgentRunDeltaRecord

    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    rows = [
        {"run_id": "selected", "owner_user_id": "owner", "seq": 1, "text": "old"},
        {"run_id": "other", "owner_user_id": "owner", "seq": 3, "text": "noise"},
        {"run_id": "selected", "owner_user_id": "foreign", "seq": 3, "text": "private"},
        {"run_id": "selected", "owner_user_id": "owner", "seq": 2, "text": "new"},
    ]
    rows = [{**row, "channel": "answer", "created_at": "2026-07-25T10:00:00+00:00"} for row in rows]
    repo.append_many_atomic([("agent_run_delta", row) for row in rows])
    def read(after_seq):
        return repo.read_run_deltas(
            "selected", owner_user_id="owner", after_seq=after_seq,
            validate=AgentRunDeltaRecord.model_validate,
        )

    assert [delta.model_dump() for delta in read(1)] == [rows[-1]]
    original_copy = module.deepcopy
    copied = []

    def counting_copy(row):
        copied.append(row)
        return original_copy(row)

    monkeypatch.setattr(module, "deepcopy", counting_copy)
    assert read(2) == []
    assert copied == []
    with module.acquire_lock(repo._batch_lock(), base_dir=repo.base_dir):
        target = tmp_path / "agent_run_delta.jsonl"
        replacement = target.with_suffix(".replacement")
        replacement.write_text(json.dumps(rows[-1]) + "\n", encoding="utf-8")
        os.replace(replacement, target)
    assert [delta.model_dump() for delta in read(1)] == [rows[-1]]
    assert copied == []


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


def test_read_all_jsonl_cache_returns_nested_mutation_safe_copies(tmp_path):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    repo.append(
        "job_runs",
        {"job_name": "ingest", "lineage": {"steps": [{"name": "extract"}]}},
    )

    rows = repo.read_all("job_runs")
    rows[0]["lineage"]["steps"][0]["name"] = "mutated"
    rows[0]["lineage"]["steps"].append({"name": "injected"})

    # The second read hits the process-wide cache; nested objects must not
    # have been poisoned by the caller-side mutation above.
    rows_again = repo.read_all("job_runs")
    assert rows_again[0]["lineage"] == {"steps": [{"name": "extract"}]}


def test_read_by_cache_keys_copies_only_selected_rows_in_append_order(
    tmp_path,
    monkeypatch,
):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    stream = module.CACHE_BUILD_RUN_STREAM
    events = [
        {
            "run_id": "selected-first",
            "cache_key": "demo:key",
            "lineage": {"steps": [{"name": "first"}]},
        },
        {
            "run_id": "noise",
            "cache_key": "noise:key",
            "lineage": {"steps": [{"name": "noise"}]},
        },
        {
            "run_id": "whitespace-decoy",
            "cache_key": " demo:key ",
            "lineage": {"steps": [{"name": "whitespace"}]},
        },
        {
            "run_id": "selected-second-key",
            "cache_key": "page:key",
            "lineage": {"steps": [{"name": "second"}]},
        },
        {
            "run_id": "selected-last",
            "cache_key": "demo:key",
            "lineage": {"steps": [{"name": "last"}]},
        },
    ]
    for event in events:
        repo.append(stream, event)
    module._read_jsonl_rows_and_index_cached(tmp_path / f"{stream}.jsonl")

    copied_run_ids = []
    original_deepcopy = module.deepcopy

    def counting_deepcopy(value):
        copied_run_ids.append(value["run_id"])
        return original_deepcopy(value)

    monkeypatch.setattr(module, "deepcopy", counting_deepcopy)

    rows = repo.read_by_cache_keys(stream, ["page:key", "demo:key", "demo:key"])

    assert [row["run_id"] for row in rows] == [
        "selected-first",
        "selected-second-key",
        "selected-last",
    ]
    assert copied_run_ids == [
        "selected-first",
        "selected-second-key",
        "selected-last",
    ]
    rows[0]["lineage"]["steps"][0]["name"] = "mutated"
    assert repo.read_by_cache_keys(stream, ["demo:key"])[0]["lineage"] == {
        "steps": [{"name": "first"}]
    }


def test_read_by_cache_keys_invalidates_after_append_and_empty_keys_read_nothing(
    tmp_path,
    monkeypatch,
):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    stream = module.CACHE_BUILD_RUN_STREAM
    repo.append(stream, {"run_id": "first", "cache_key": "demo:key"})

    assert [
        row["run_id"] for row in repo.read_by_cache_keys(stream, ["demo:key"])
    ] == ["first"]
    repo.append(stream, {"run_id": "noise", "cache_key": "noise:key"})
    repo.append(stream, {"run_id": "second", "cache_key": "demo:key"})
    assert [
        row["run_id"] for row in repo.read_by_cache_keys(stream, ["demo:key"])
    ] == ["first", "second"]

    def fail_if_read(*_args, **_kwargs):
        raise AssertionError("empty cache keys must not read or lock the stream")

    monkeypatch.setattr(module, "acquire_lock", fail_if_read)
    assert repo.read_by_cache_keys(stream, ["", "   "]) == []


@pytest.mark.parametrize("status", ["failed", "queued", "running", "completed"])
def test_latest_run_selects_only_newest_matching_row_without_status_fallback(
    tmp_path, monkeypatch, status,
):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    stream = module.CACHE_BUILD_RUN_STREAM
    matching = {"cache_key": "demo:key", "job_name": "job-a", "report_date": "2026-01-31"}
    repo.append(stream, {**matching, "run_id": "old", "status": "completed", "source_version": "sv_old"})
    repo.append(stream, {**matching, "run_id": "latest", "status": status, "source_version": " ",
                         "lineage": {"items": [1]}})
    repo.append(stream, {**matching, "run_id": "other-date", "report_date": "2026-02-28"})
    repo.append(stream, {**matching, "run_id": "other-job", "job_name": "job-b"})
    repo.append(stream, {**matching, "run_id": "other-key", "cache_key": "other:key"})
    module._read_jsonl_rows_and_index_cached(tmp_path / f"{stream}.jsonl")
    copied_run_ids = []
    original_deepcopy = module.deepcopy

    def counting_deepcopy(value):
        copied_run_ids.append(value["run_id"])
        return original_deepcopy(value)

    monkeypatch.setattr(module, "deepcopy", counting_deepcopy)
    latest = repo.read_latest_run(" demo:key ", job_name=" job-a ", report_date=" 2026-01-31 ")
    assert latest["run_id"] == "latest"
    assert latest["status"] == status
    assert latest["source_version"] == " "
    assert copied_run_ids == ["latest"]
    latest["lineage"]["items"].append(2)
    assert repo.read_latest_run("demo:key", job_name="job-a", report_date="2026-01-31")["lineage"] == {"items": [1]}
    repo.append(stream, {**matching, "run_id": "newest", "status": "queued"})
    assert repo.read_latest_run("demo:key", job_name="job-a", report_date="2026-01-31")["run_id"] == "newest"
    assert repo.read_latest_run("missing:key") is None
    assert repo.read_latest_run(" ") is None


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


def test_latest_jsonl_lookup_falls_back_to_full_scan_when_index_missing(tmp_path, monkeypatch):
    module = _load_governance_repo_module()
    repo = module.GovernanceRepository(base_dir=tmp_path)
    repo.append(
        module.CACHE_MANIFEST_STREAM,
        {"cache_key": "noise:0", "report_date": "2026-01-31", "source_version": "sv_noise"},
    )
    repo.append(
        module.CACHE_MANIFEST_STREAM,
        {"cache_key": "demo:key", "report_date": "2026-01-31", "source_version": "sv_target"},
    )

    original_reader = module._read_jsonl_rows_and_index_cached

    def reader_without_index(path):
        rows, _index = original_reader(path)
        return rows, None

    monkeypatch.setattr(
        module,
        "_read_jsonl_rows_and_index_cached",
        reader_without_index,
    )

    latest = repo.read_latest_manifest("demo:key", report_date="2026-01-31")

    assert latest is not None
    assert latest["source_version"] == "sv_target"
