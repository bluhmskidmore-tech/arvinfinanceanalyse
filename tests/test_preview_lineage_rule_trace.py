from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.source_preview_repo import RULE_VERSION
from tests.helpers import ROOT, load_module


def _completed_manifest_records(governance_dir: Path) -> list[dict[str, object]]:
    manifest_path = governance_dir / "source_manifest.jsonl"
    return [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_source_manifest_repository_keeps_distinct_source_versions_as_separate_completed_rows(tmp_path):
    governance_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )
    manifest_module = load_module(
        "backend.app.repositories.source_manifest_repo",
        "backend/app/repositories/source_manifest_repo.py",
    )

    governance_repo = governance_module.GovernanceRepository(base_dir=tmp_path)
    repo = manifest_module.SourceManifestRepository(governance_repo=governance_repo)

    repo.add_many(
        [
            {
                "ingest_batch_id": "ib_first",
                "source_family": "zqtz",
                "report_date": "2025-12-31",
                "source_file": "ZQTZSHOW-20251231.xls",
                "archived_path": "archive/zqtz-first.xls",
                "source_version": "sv_same",
                "archive_mode": "local",
                "status": "completed",
            }
        ]
    )
    repo.add_many(
        [
            {
                "ingest_batch_id": "ib_second",
                "source_family": "zqtz",
                "report_date": "2025-12-31",
                "source_file": "ZQTZSHOW-20251231.xls",
                "archived_path": "archive/zqtz-second.xls",
                "source_version": "sv_second",
                "archive_mode": "local",
                "status": "completed",
            }
        ]
    )

    records = repo.load_all()

    assert len(records) == 2
    assert records[0]["schema_version"] == "phase1.manifest.v1"
    assert records[0]["status"] == "completed"
    assert records[1]["status"] == "completed"
    assert "rerun_of_batch_id" not in records[1]


def test_source_manifest_repository_marks_exact_same_artifact_as_rerun(tmp_path):
    governance_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )
    manifest_module = load_module(
        "backend.app.repositories.source_manifest_repo",
        "backend/app/repositories/source_manifest_repo.py",
    )

    governance_repo = governance_module.GovernanceRepository(base_dir=tmp_path)
    repo = manifest_module.SourceManifestRepository(governance_repo=governance_repo)

    base_record = {
        "source_family": "zqtz",
        "report_date": "2025-12-31",
        "source_file": "ZQTZSHOW-20251231.xls",
        "archived_path": "archive/zqtz-first.xls",
        "source_version": "sv_same",
        "archive_mode": "local",
        "status": "completed",
    }
    repo.add_many([{**base_record, "ingest_batch_id": "ib_first"}])
    repo.add_many([{**base_record, "ingest_batch_id": "ib_second"}])

    records = repo.load_all()

    assert len(records) == 2
    assert records[0]["status"] == "completed"
    assert records[1]["status"] == "rerun"
    assert records[1]["rerun_of_batch_id"] == "ib_first"


def test_materialize_uses_lineage_not_raw_directory_when_building_preview(tmp_path, monkeypatch):
    ingest_task_module = sys.modules.get("backend.app.tasks.ingest")
    if ingest_task_module is None:
        ingest_task_module = load_module("backend.app.tasks.ingest", "backend/app/tasks/ingest.py")

    materialize_module = sys.modules.get("backend.app.tasks.materialize")
    if materialize_module is None:
        materialize_module = load_module(
            "backend.app.tasks.materialize",
            "backend/app/tasks/materialize.py",
        )

    data_root = tmp_path / "data_input"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    duckdb_path = tmp_path / "moss.duckdb"

    data_root.mkdir()
    zqtz_source = data_root / "ZQTZSHOW-20251231.xls"
    zqtz_source.write_bytes((ROOT / "data_input" / "ZQTZSHOW-20251231.xls").read_bytes())

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    ingest_payload = ingest_task_module.ingest_demo_manifest.fn()
    manifest_rows = _completed_manifest_records(governance_dir)
    assert {row["status"] for row in manifest_rows} == {"completed"}
    assert {row["ingest_batch_id"] for row in manifest_rows} == {ingest_payload["ingest_batch_id"]}
    zqtz_source.unlink()

    payload = materialize_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_root),
    )

    assert payload["status"] == "completed"
    assert payload["preview_sources"] == ["zqtz"]


def test_preview_row_and_trace_apis_return_deterministic_payloads(tmp_path, monkeypatch):
    ingest_task_module = sys.modules.get("backend.app.tasks.ingest")
    if ingest_task_module is None:
        ingest_task_module = load_module("backend.app.tasks.ingest", "backend/app/tasks/ingest.py")

    materialize_module = sys.modules.get("backend.app.tasks.materialize")
    if materialize_module is None:
        materialize_module = load_module(
            "backend.app.tasks.materialize",
            "backend/app/tasks/materialize.py",
        )

    data_root = tmp_path / "data_input"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    duckdb_path = tmp_path / "moss.duckdb"

    data_root.mkdir()
    for file_name in ("ZQTZSHOW-20251231.xls", "TYWLSHOW-20251231.xls"):
        (data_root / file_name).write_bytes((ROOT / "data_input" / file_name).read_bytes())

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    ingest_payload = ingest_task_module.ingest_demo_manifest.fn()
    ingest_batch_id = ingest_payload["ingest_batch_id"]

    materialize_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_root),
    )

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    zqtz_rows = client.get(
        f"/ui/preview/source-foundation/zqtz/rows?ingest_batch_id={ingest_batch_id}&limit=2&offset=0"
    )
    zqtz_traces = client.get(
        f"/ui/preview/source-foundation/zqtz/traces?ingest_batch_id={ingest_batch_id}&limit=3&offset=0"
    )

    assert zqtz_rows.status_code == 200
    assert zqtz_traces.status_code == 200

    row_payload = zqtz_rows.json()
    trace_payload = zqtz_traces.json()

    assert row_payload["result_meta"]["formal_use_allowed"] is False
    assert trace_payload["result_meta"]["formal_use_allowed"] is False

    first_row = row_payload["result"]["rows"][0]
    assert set(first_row) >= {
        "ingest_batch_id",
        "row_locator",
        "report_date",
        "business_type_primary",
        "business_type_final",
        "asset_group",
        "instrument_code",
        "instrument_name",
        "account_category",
        "manual_review_needed",
    }

    first_trace = trace_payload["result"]["rows"][0]
    assert set(first_trace) >= {
        "ingest_batch_id",
        "row_locator",
        "trace_step",
        "field_name",
        "field_value",
        "derived_label",
        "manual_review_needed",
    }
    assert row_payload["result_meta"]["source_version"] == first_row["source_version"]
    assert trace_payload["result_meta"]["source_version"] == first_row["source_version"]

    second_page = client.get(
        f"/ui/preview/source-foundation/zqtz/rows?ingest_batch_id={ingest_batch_id}&limit=2&offset=2"
    ).json()

    assert row_payload["result"]["rows"][0]["row_locator"] < row_payload["result"]["rows"][1]["row_locator"]
    assert row_payload["result"]["rows"][1]["row_locator"] < second_page["result"]["rows"][0]["row_locator"]


def _walk_preview_pages(
    client: TestClient,
    source_family: str,
    endpoint: str,
    ingest_batch_id: str,
    page_limit: int,
) -> tuple[int, list[dict[str, object]]]:
    offset = 0
    total_rows: int | None = None
    accumulated: list[dict[str, object]] = []
    while True:
        response = client.get(
            f"/ui/preview/source-foundation/{source_family}/{endpoint}"
            f"?ingest_batch_id={ingest_batch_id}&limit={page_limit}&offset={offset}"
        )
        assert response.status_code == 200
        block = response.json()["result"]
        if total_rows is None:
            total_rows = int(block["total_rows"])
        chunk = block["rows"]
        assert block["limit"] == page_limit
        assert block["offset"] == offset
        accumulated.extend(chunk)
        if not chunk:
            break
        offset += len(chunk)
    assert total_rows is not None
    return total_rows, accumulated


def test_preview_row_and_trace_apis_pagination_matrix_unknown_batch_and_oob_offset(
    tmp_path, monkeypatch
):
    ingest_task_module = sys.modules.get("backend.app.tasks.ingest")
    if ingest_task_module is None:
        ingest_task_module = load_module("backend.app.tasks.ingest", "backend/app/tasks/ingest.py")

    materialize_module = sys.modules.get("backend.app.tasks.materialize")
    if materialize_module is None:
        materialize_module = load_module(
            "backend.app.tasks.materialize",
            "backend/app/tasks/materialize.py",
        )

    data_root = tmp_path / "data_input"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    duckdb_path = tmp_path / "moss.duckdb"

    data_root.mkdir()
    for file_name in ("ZQTZSHOW-20251231.xls", "TYWLSHOW-20251231.xls"):
        (data_root / file_name).write_bytes((ROOT / "data_input" / file_name).read_bytes())

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    ingest_payload = ingest_task_module.ingest_demo_manifest.fn()
    ingest_batch_id = ingest_payload["ingest_batch_id"]

    materialize_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_root),
    )

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    for family in ("zqtz", "tyw"):
        row_totals: set[int] = set()
        for page_limit in (41, 318):
            total, rows = _walk_preview_pages(
                client, family, "rows", ingest_batch_id, page_limit
            )
            row_totals.add(total)
            assert total > 0
            assert len(rows) == total
            locators = [int(r["row_locator"]) for r in rows]
            assert locators == sorted(locators)
            assert len(locators) == len(set(locators))
        assert len(row_totals) == 1

        p1 = client.get(
            f"/ui/preview/source-foundation/{family}/rows"
            f"?ingest_batch_id={ingest_batch_id}&limit=3&offset=0"
        ).json()["result"]
        p2 = client.get(
            f"/ui/preview/source-foundation/{family}/rows"
            f"?ingest_batch_id={ingest_batch_id}&limit=3&offset=3"
        ).json()["result"]
        assert len(p1["rows"]) == 3
        assert len(p2["rows"]) == 3
        assert int(p1["rows"][-1]["row_locator"]) < int(p2["rows"][0]["row_locator"])

        trace_totals: set[int] = set()
        for page_limit in (180, 420):
            total_t, traces = _walk_preview_pages(
                client, family, "traces", ingest_batch_id, page_limit
            )
            trace_totals.add(total_t)
            assert total_t > 0
            assert len(traces) == total_t
            for idx in range(len(traces) - 1):
                cur = (int(traces[idx]["row_locator"]), int(traces[idx]["trace_step"]))
                nxt = (int(traces[idx + 1]["row_locator"]), int(traces[idx + 1]["trace_step"]))
                assert cur <= nxt
        assert len(trace_totals) == 1

        t1 = client.get(
            f"/ui/preview/source-foundation/{family}/traces"
            f"?ingest_batch_id={ingest_batch_id}&limit=4&offset=0"
        ).json()["result"]
        t2 = client.get(
            f"/ui/preview/source-foundation/{family}/traces"
            f"?ingest_batch_id={ingest_batch_id}&limit=4&offset=4"
        ).json()["result"]
        assert len(t1["rows"]) == 4
        assert len(t2["rows"]) == 4
        assert (int(t1["rows"][-1]["row_locator"]), int(t1["rows"][-1]["trace_step"])) <= (
            int(t2["rows"][0]["row_locator"]),
            int(t2["rows"][0]["trace_step"]),
        )

    unknown = "ingest_batch_id=ib_absolutely_unknown_xyz"
    for family, endpoint in (("zqtz", "rows"), ("zqtz", "traces"), ("tyw", "rows"), ("tyw", "traces")):
        r = client.get(
            f"/ui/preview/source-foundation/{family}/{endpoint}?{unknown}&limit=50&offset=0"
        )
        assert r.status_code == 200
        body = r.json()["result"]
        assert body["total_rows"] == 0
        assert body["rows"] == []
        assert body["ingest_batch_id"] == "ib_absolutely_unknown_xyz"

    zqtz_total = client.get(
        f"/ui/preview/source-foundation/zqtz/rows?ingest_batch_id={ingest_batch_id}&limit=1&offset=0"
    ).json()["result"]["total_rows"]
    zqtz_tr_total = int(
        client.get(
            f"/ui/preview/source-foundation/zqtz/traces?ingest_batch_id={ingest_batch_id}&limit=1&offset=0"
        ).json()["result"]["total_rows"]
    )

    oob_rows = client.get(
        f"/ui/preview/source-foundation/zqtz/rows"
        f"?ingest_batch_id={ingest_batch_id}&limit=20&offset={zqtz_total + 10_000}"
    ).json()["result"]
    assert oob_rows["total_rows"] == zqtz_total
    assert oob_rows["rows"] == []
    assert oob_rows["offset"] == zqtz_total + 10_000

    oob_tr_offset = zqtz_tr_total + 10_000
    oob_tr = client.get(
        f"/ui/preview/source-foundation/zqtz/traces"
        f"?ingest_batch_id={ingest_batch_id}&limit=20&offset={oob_tr_offset}"
    ).json()["result"]
    assert oob_tr["total_rows"] == zqtz_tr_total
    assert oob_tr["rows"] == []
    assert oob_tr["offset"] == oob_tr_offset

    tyw_total = client.get(
        f"/ui/preview/source-foundation/tyw/rows?ingest_batch_id={ingest_batch_id}&limit=1&offset=0"
    ).json()["result"]["total_rows"]
    assert tyw_total >= 3
    penultimate = tyw_total - 2
    window = client.get(
        f"/ui/preview/source-foundation/tyw/rows"
        f"?ingest_batch_id={ingest_batch_id}&limit=10&offset={penultimate}"
    ).json()["result"]
    assert len(window["rows"]) == 2
    assert window["offset"] == penultimate

    get_settings.cache_clear()


def test_history_endpoint_lists_multiple_materialized_batches_and_preserves_old_rows(
    tmp_path, monkeypatch
):
    ingest_task_module = sys.modules.get("backend.app.tasks.ingest")
    if ingest_task_module is None:
        ingest_task_module = load_module("backend.app.tasks.ingest", "backend/app/tasks/ingest.py")

    materialize_module = sys.modules.get("backend.app.tasks.materialize")
    if materialize_module is None:
        materialize_module = load_module(
            "backend.app.tasks.materialize",
            "backend/app/tasks/materialize.py",
        )

    data_root = tmp_path / "data_input"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    duckdb_path = tmp_path / "moss.duckdb"

    data_root.mkdir()
    for file_name in ("ZQTZSHOW-20251231.xls", "TYWLSHOW-20251231.xls"):
        (data_root / file_name).write_bytes((ROOT / "data_input" / file_name).read_bytes())

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    first_ingest = ingest_task_module.ingest_demo_manifest.fn()
    materialize_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_root),
        ingest_batch_id=first_ingest["ingest_batch_id"],
    )

    zqtz_path = data_root / "ZQTZSHOW-20251231.xls"
    zqtz_path.write_bytes(zqtz_path.read_bytes() + b"\n")
    second_ingest = ingest_task_module.ingest_demo_manifest.fn()
    materialize_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_root),
        ingest_batch_id=second_ingest["ingest_batch_id"],
    )

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    history_response = client.get("/ui/preview/source-foundation/history")
    assert history_response.status_code == 200
    history_payload = history_response.json()
    batch_ids = {row["ingest_batch_id"] for row in history_payload["result"]["rows"]}
    assert first_ingest["ingest_batch_id"] in batch_ids
    assert second_ingest["ingest_batch_id"] in batch_ids
    assert history_payload["result_meta"]["source_version"] != "sv_preview_history"
    for row in history_payload["result"]["rows"]:
        assert row["source_version"] in history_payload["result_meta"]["source_version"]

    filtered_history_response = client.get(
        "/ui/preview/source-foundation/history?source_family=zqtz&limit=100&offset=0"
    )
    assert filtered_history_response.status_code == 200
    filtered_history_payload = filtered_history_response.json()
    assert filtered_history_payload["result"]["total_rows"] == 2
    assert len(filtered_history_payload["result"]["rows"]) == 2
    assert {
        row["source_family"] for row in filtered_history_payload["result"]["rows"]
    } == {"zqtz"}
    assert filtered_history_payload["result_meta"]["source_version"] != "sv_preview_history"
    for row in filtered_history_payload["result"]["rows"]:
        assert row["source_version"] in filtered_history_payload["result_meta"]["source_version"]

    first_batch_rows = client.get(
        f"/ui/preview/source-foundation/zqtz/rows?ingest_batch_id={first_ingest['ingest_batch_id']}&limit=5&offset=0"
    ).json()["result"]
    second_batch_rows = client.get(
        f"/ui/preview/source-foundation/zqtz/rows?ingest_batch_id={second_ingest['ingest_batch_id']}&limit=5&offset=0"
    ).json()["result"]

    assert first_batch_rows["total_rows"] > 0
    assert second_batch_rows["total_rows"] > 0
    assert first_batch_rows["ingest_batch_id"] == first_ingest["ingest_batch_id"]
    assert second_batch_rows["ingest_batch_id"] == second_ingest["ingest_batch_id"]


def test_source_preview_http_surfaces_share_analytical_result_meta_contract(tmp_path, monkeypatch):
    """foundation / history / rows / traces 均为 preview（analytical），不得冒充 formal；契约字段一致。"""
    ingest_task_module = sys.modules.get("backend.app.tasks.ingest")
    if ingest_task_module is None:
        ingest_task_module = load_module("backend.app.tasks.ingest", "backend/app/tasks/ingest.py")

    materialize_module = sys.modules.get("backend.app.tasks.materialize")
    if materialize_module is None:
        materialize_module = load_module(
            "backend.app.tasks.materialize",
            "backend/app/tasks/materialize.py",
        )

    data_root = tmp_path / "data_input"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    duckdb_path = tmp_path / "moss.duckdb"

    data_root.mkdir()
    for file_name in ("ZQTZSHOW-20251231.xls", "TYWLSHOW-20251231.xls"):
        (data_root / file_name).write_bytes((ROOT / "data_input" / file_name).read_bytes())

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    ingest_payload = ingest_task_module.ingest_demo_manifest.fn()
    ingest_batch_id = ingest_payload["ingest_batch_id"]

    materialize_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_root),
    )

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    foundation = client.get("/ui/preview/source-foundation").json()
    history = client.get("/ui/preview/source-foundation/history?limit=5&offset=0").json()
    zqtz_rows = client.get(
        f"/ui/preview/source-foundation/zqtz/rows?ingest_batch_id={ingest_batch_id}&limit=3&offset=0"
    ).json()
    zqtz_traces = client.get(
        f"/ui/preview/source-foundation/zqtz/traces?ingest_batch_id={ingest_batch_id}&limit=5&offset=0"
    ).json()
    tyw_rows = client.get(
        f"/ui/preview/source-foundation/tyw/rows?ingest_batch_id={ingest_batch_id}&limit=2&offset=0"
    ).json()

    expected_kinds = {
        "foundation": "preview.source-foundation",
        "history": "preview.source-foundation.history",
        "zqtz_rows": "preview.zqtz.rows",
        "zqtz_traces": "preview.zqtz.traces",
        "tyw_rows": "preview.tyw.rows",
    }
    bundles = {
        "foundation": foundation,
        "history": history,
        "zqtz_rows": zqtz_rows,
        "zqtz_traces": zqtz_traces,
        "tyw_rows": tyw_rows,
    }

    for key, body in bundles.items():
        meta = body["result_meta"]
        assert meta["basis"] == "analytical", key
        assert meta["formal_use_allowed"] is False, key
        assert meta["scenario_flag"] is False, key
        assert meta["rule_version"] == RULE_VERSION, key
        assert meta["cache_version"] == "cv_phase1_source_preview_v1", key
        assert meta["result_kind"] == expected_kinds[key], key
        assert meta["source_version"] != "sv_preview_empty", key

    z_res = zqtz_rows["result"]
    assert z_res["total_rows"] > 0
    assert z_res["limit"] == 3
    assert z_res["offset"] == 0
    assert len(z_res["rows"]) == 3
    assert z_res["source_family"] == "zqtz"

    tr_res = zqtz_traces["result"]
    assert tr_res["total_rows"] > 0
    assert len(tr_res["rows"]) == 5

    hist = history["result"]
    assert hist["total_rows"] >= 2
    assert len(hist["rows"]) <= 5
    assert hist["limit"] == 5
    assert hist["offset"] == 0

    get_settings.cache_clear()
