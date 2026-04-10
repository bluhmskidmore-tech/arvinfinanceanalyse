from pathlib import Path
import sys

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from tests.helpers import ROOT, load_module


def test_source_preview_service_summarizes_real_zqtz_and_tyw_files():
    preview_module = load_module(
        "backend.app.services.source_preview_service",
        "backend/app/services/source_preview_service.py",
    )

    zqtz_summary = preview_module.summarize_source_file(
        ROOT / "data_input" / "ZQTZSHOW-20251231.xls",
    )
    tyw_summary = preview_module.summarize_source_file(
        ROOT / "data_input" / "TYWLSHOW-20251231.xls",
    )

    assert zqtz_summary["source_family"] == "zqtz"
    assert zqtz_summary["report_date"] == "2025-12-31"
    assert zqtz_summary["total_rows"] > 0
    assert len(zqtz_summary["group_counts"]) >= 3
    assert all(count > 0 for count in zqtz_summary["group_counts"].values())
    assert sum(zqtz_summary["group_counts"].values()) == zqtz_summary["total_rows"]

    assert tyw_summary["source_family"] == "tyw"
    assert tyw_summary["report_date"] == "2025-12-31"
    assert tyw_summary["total_rows"] > 0
    assert len(tyw_summary["group_counts"]) >= 3
    assert all(count > 0 for count in tyw_summary["group_counts"].values())
    assert sum(tyw_summary["group_counts"].values()) == tyw_summary["total_rows"]


def test_source_preview_service_reexports_supported_source_families_from_repo():
    preview_module = load_module(
        "backend.app.services.source_preview_service",
        "backend/app/services/source_preview_service.py",
    )
    repo_module = load_module(
        "backend.app.repositories.source_preview_repo",
        "backend/app/repositories/source_preview_repo.py",
    )

    assert (
        preview_module.SUPPORTED_PREVIEW_SOURCE_FAMILIES
        == repo_module.SUPPORTED_PREVIEW_SOURCE_FAMILIES
    )


def test_source_preview_api_registers_manual_refresh_routes():
    from backend.app.main import app

    paths = {route.path for route in app.routes}

    assert "/ui/preview/source-foundation/refresh" in paths
    assert "/ui/preview/source-foundation/refresh-status" in paths


def test_materialize_task_persists_source_preview_summary_rows(tmp_path, monkeypatch):
    ingest_module = sys.modules.get("backend.app.tasks.ingest")
    if ingest_module is None:
        ingest_module = load_module(
            "backend.app.tasks.ingest",
            "backend/app/tasks/ingest.py",
        )
    materialize_module = sys.modules.get("backend.app.tasks.materialize")
    if materialize_module is None:
        materialize_module = load_module(
            "backend.app.tasks.materialize",
            "backend/app/tasks/materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    data_root.mkdir()
    for file_name in ("ZQTZSHOW-20251231.xls", "TYWLSHOW-20251231.xls"):
        (data_root / file_name).write_bytes((ROOT / "data_input" / file_name).read_bytes())

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    ingest_module.ingest_demo_manifest.fn()

    payload = materialize_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_root),
    )

    assert payload["status"] == "completed"
    assert set(payload["preview_sources"]) == {"tyw", "zqtz"}
    assert len(payload["preview_sources"]) == 2

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        rows = conn.execute(
            """
            select source_family, total_rows
            from phase1_source_preview_summary
            """
        ).fetchall()
    finally:
        conn.close()

    by_family = {family: total for family, total in rows}
    assert by_family.keys() == {"tyw", "zqtz"}
    assert by_family["tyw"] > 0
    assert by_family["zqtz"] > 0
    get_settings.cache_clear()


def test_preview_api_returns_real_source_preview_envelope(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()


def test_source_preview_refresh_queues_async_run_and_reports_latest_status(tmp_path, monkeypatch):
    _configure_source_preview_refresh_env(tmp_path, monkeypatch, include_pnl_preview_source=True)
    queued_messages: list[dict[str, object]] = []
    refresh_module = load_module(
        "backend.app.services.source_preview_refresh_service",
        "backend/app/services/source_preview_refresh_service.py",
    )

    def fake_send(**kwargs):
        queued_messages.append(kwargs)
        return None

    monkeypatch.setattr(refresh_module.refresh_source_preview_cache, "send", fake_send)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    refresh_response = client.post("/ui/preview/source-foundation/refresh")

    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["status"] == "queued"
    assert refresh_payload["job_name"] == "source_preview_refresh"
    assert refresh_payload["trigger_mode"] == "async"
    assert refresh_payload["cache_key"] == "source_preview.foundation"
    assert refresh_payload["preview_sources"] == ["zqtz", "tyw"]
    assert queued_messages[0]["run_id"] == refresh_payload["run_id"]
    assert queued_messages[0]["duckdb_path"] == str(tmp_path / "moss.duckdb")
    assert queued_messages[0]["governance_dir"] == str(tmp_path / "governance")

    status_response = client.get("/ui/preview/source-foundation/refresh-status")

    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "queued"
    assert status_payload["run_id"] == refresh_payload["run_id"]
    assert status_payload["job_name"] == "source_preview_refresh"
    assert status_payload["trigger_mode"] == "async"
    assert status_payload["cache_key"] == "source_preview.foundation"
    get_settings.cache_clear()


def test_source_preview_refresh_sync_fallback_ingests_and_materializes_only_zqtz_and_tyw(
    tmp_path,
    monkeypatch,
):
    _configure_source_preview_refresh_env(tmp_path, monkeypatch, include_pnl_preview_source=True)
    refresh_module = load_module(
        "backend.app.services.source_preview_refresh_service",
        "backend/app/services/source_preview_refresh_service.py",
    )

    monkeypatch.setattr(
        refresh_module.refresh_source_preview_cache,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("queue disabled")),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    refresh_response = client.post("/ui/preview/source-foundation/refresh")

    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["status"] == "completed"
    assert refresh_payload["job_name"] == "source_preview_refresh"
    assert refresh_payload["trigger_mode"] == "sync-fallback"
    assert refresh_payload["cache_key"] == "source_preview.foundation"
    assert set(refresh_payload["preview_sources"]) == {"zqtz", "tyw"}
    assert refresh_payload["source_version"].startswith("sv_")
    assert refresh_payload["ingest_batch_id"].startswith("ib_")

    status_response = client.get(
        "/ui/preview/source-foundation/refresh-status",
        params={"run_id": refresh_payload["run_id"]},
    )
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "completed"
    assert status_payload["run_id"] == refresh_payload["run_id"]
    assert status_payload["trigger_mode"] == "terminal"
    assert set(status_payload["preview_sources"]) == {"zqtz", "tyw"}

    foundation_response = client.get("/ui/preview/source-foundation")
    assert foundation_response.status_code == 200
    foundation_sources = foundation_response.json()["result"]["sources"]
    assert {source["source_family"] for source in foundation_sources} == {"zqtz", "tyw"}
    get_settings.cache_clear()


def test_source_preview_refresh_rejects_duplicate_inflight_run(tmp_path, monkeypatch):
    governance_dir = _configure_source_preview_status_env(tmp_path, monkeypatch)
    refresh_module = load_module(
        "backend.app.services.source_preview_refresh_service",
        "backend/app/services/source_preview_refresh_service.py",
    )
    send_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        refresh_module.refresh_source_preview_cache,
        "send",
        lambda **kwargs: send_calls.append(kwargs),
    )

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "source-preview-running",
            "job_name": "source_preview_refresh",
            "status": "running",
            "cache_key": "source_preview.foundation",
            "lock": "lock:duckdb:source-preview",
            "source_version": "sv_preview_running",
            "vendor_version": "vv_none",
            "preview_sources": ["zqtz", "tyw"],
        },
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post("/ui/preview/source-foundation/refresh")

    assert response.status_code == 409
    assert response.json()["detail"] == "Source preview refresh already in progress."
    assert send_calls == []
    get_settings.cache_clear()


def test_source_preview_refresh_returns_503_when_send_error_is_not_safe_for_sync_fallback(
    tmp_path,
    monkeypatch,
):
    _, governance_dir, _ = _configure_source_preview_refresh_env(
        tmp_path,
        monkeypatch,
        include_pnl_preview_source=True,
    )
    refresh_module = load_module(
        "backend.app.services.source_preview_refresh_service",
        "backend/app/services/source_preview_refresh_service.py",
    )
    fallback_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        refresh_module.refresh_source_preview_cache,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("unexpected broker failure")),
    )
    monkeypatch.setattr(
        refresh_module.refresh_source_preview_cache,
        "fn",
        lambda **kwargs: fallback_calls.append(kwargs),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.post("/ui/preview/source-foundation/refresh")

    assert response.status_code == 503
    assert response.json()["detail"] == "Source preview refresh queue dispatch failed."
    assert fallback_calls == []

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    latest = [record for record in records if record.get("job_name") == "source_preview_refresh"][-1]
    assert latest["status"] == "failed"
    assert latest["error_message"] == "Source preview refresh queue dispatch failed."
    get_settings.cache_clear()


def test_source_preview_refresh_returns_stable_503_when_sync_fallback_worker_fails(
    tmp_path,
    monkeypatch,
):
    _, governance_dir, _ = _configure_source_preview_refresh_env(
        tmp_path,
        monkeypatch,
        include_pnl_preview_source=True,
    )
    refresh_module = load_module(
        "backend.app.services.source_preview_refresh_service",
        "backend/app/services/source_preview_refresh_service.py",
    )
    task_module = load_module(
        "backend.app.tasks.source_preview_refresh",
        "backend/app/tasks/source_preview_refresh.py",
    )

    monkeypatch.setattr(
        refresh_module.refresh_source_preview_cache,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("queue disabled")),
    )
    monkeypatch.setattr(
        task_module,
        "_run_source_preview_ingest",
        lambda **_: (_ for _ in ()).throw(RuntimeError("ingest boom")),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.post("/ui/preview/source-foundation/refresh")

    assert response.status_code == 503
    assert response.json()["detail"] == "Source preview refresh failed during sync fallback."

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    latest = [record for record in records if record.get("job_name") == "source_preview_refresh"][-1]
    assert latest["status"] == "failed"
    assert latest["error_message"] == "ingest boom"
    get_settings.cache_clear()


def test_source_preview_refresh_status_run_id_returns_exact_terminal_record(tmp_path, monkeypatch):
    governance_dir = _configure_source_preview_status_env(tmp_path, monkeypatch)

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "source-preview-target",
            "job_name": "source_preview_refresh",
            "status": "queued",
            "cache_key": "source_preview.foundation",
            "lock": "lock:duckdb:source-preview",
            "source_version": "sv_preview_pending",
            "vendor_version": "vv_none",
            "preview_sources": ["zqtz", "tyw"],
        },
    )
    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "source-preview-target",
            "job_name": "source_preview_refresh",
            "status": "completed",
            "cache_key": "source_preview.foundation",
            "lock": "lock:duckdb:source-preview",
            "source_version": "sv_preview_done",
            "vendor_version": "vv_none",
            "preview_sources": ["zqtz", "tyw"],
            "ingest_batch_id": "ib_target",
        },
    )
    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "source-preview-other",
            "job_name": "source_preview_refresh",
            "status": "queued",
            "cache_key": "source_preview.foundation",
            "lock": "lock:duckdb:source-preview",
            "source_version": "sv_preview_other",
            "vendor_version": "vv_none",
            "preview_sources": ["zqtz", "tyw"],
        },
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/ui/preview/source-foundation/refresh-status",
        params={"run_id": "source-preview-target"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "source-preview-target"
    assert payload["status"] == "completed"
    assert payload["source_version"] == "sv_preview_done"
    assert payload["ingest_batch_id"] == "ib_target"
    assert payload["trigger_mode"] == "terminal"
    get_settings.cache_clear()

    ingest_module = sys.modules.get("backend.app.tasks.ingest")
    if ingest_module is None:
        ingest_module = load_module(
            "backend.app.tasks.ingest",
            "backend/app/tasks/ingest.py",
        )
    materialize_module = sys.modules.get("backend.app.tasks.materialize")
    if materialize_module is None:
        materialize_module = load_module(
            "backend.app.tasks.materialize",
            "backend/app/tasks/materialize.py",
        )

    data_root = tmp_path / "data_input"
    data_root.mkdir()
    for file_name in ("ZQTZSHOW-20251231.xls", "TYWLSHOW-20251231.xls"):
        (data_root / file_name).write_bytes((ROOT / "data_input" / file_name).read_bytes())

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    ingest_module.ingest_demo_manifest.fn()
    materialize_module.materialize_cache_view.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
        data_root=str(data_root),
    )

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)
    response = client.get("/ui/preview/source-foundation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "preview.source-foundation"
    assert payload["result_meta"]["formal_use_allowed"] is False
    sources = payload["result"]["sources"]
    assert len(sources) == 2
    assert {item["source_family"] for item in sources} == {"tyw", "zqtz"}
    for item in sources:
        assert item["total_rows"] > 0
        assert isinstance(item.get("group_counts"), dict)
        assert sum(item["group_counts"].values()) == item["total_rows"]
    get_settings.cache_clear()


def test_preview_rows_api_empty_duckdb_returns_empty_page(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "no_preview_tables.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)
    response = client.get("/ui/preview/source-foundation/zqtz/rows?limit=10&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["result_meta"]["result_kind"] == "preview.zqtz.rows"
    assert body["result"]["total_rows"] == 0
    assert body["result"]["columns"] == []
    assert body["result"]["rows"] == []
    assert body["result"]["limit"] == 10
    assert body["result"]["offset"] == 0
    get_settings.cache_clear()


def test_preview_rows_api_returns_columns_for_dynamic_table(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    ingest_module = sys.modules.get("backend.app.tasks.ingest")
    if ingest_module is None:
        ingest_module = load_module(
            "backend.app.tasks.ingest",
            "backend/app/tasks/ingest.py",
        )
    materialize_module = sys.modules.get("backend.app.tasks.materialize")
    if materialize_module is None:
        materialize_module = load_module(
            "backend.app.tasks.materialize",
            "backend/app/tasks/materialize.py",
        )

    data_root = tmp_path / "data_input"
    data_root.mkdir()
    for file_name in ("ZQTZSHOW-20251231.xls",):
        (data_root / file_name).write_bytes((ROOT / "data_input" / file_name).read_bytes())

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    ingest_module.ingest_demo_manifest.fn()
    materialize_module.materialize_cache_view.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
        data_root=str(data_root),
    )

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)
    response = client.get("/ui/preview/source-foundation/zqtz/rows?limit=5&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["result_meta"]["result_kind"] == "preview.zqtz.rows"
    assert body["result"]["total_rows"] > 0
    assert body["result"]["columns"][:4] == [
        {"key": "ingest_batch_id", "label": "批次ID", "type": "string"},
        {"key": "row_locator", "label": "行号", "type": "number"},
        {"key": "report_date", "label": "报告日期", "type": "string"},
        {"key": "business_type_primary", "label": "业务种类1", "type": "string"},
    ]
    assert {"key": "instrument_name", "label": "债券名称", "type": "string"} in body["result"]["columns"]
    assert {"key": "manual_review_needed", "label": "需人工复核", "type": "boolean"} in body["result"]["columns"]
    assert set(body["result"]["rows"][0].keys()) == {column["key"] for column in body["result"]["columns"]}
    get_settings.cache_clear()


def test_preview_traces_api_returns_typed_columns_for_generic_table(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    ingest_module = sys.modules.get("backend.app.tasks.ingest")
    if ingest_module is None:
        ingest_module = load_module(
            "backend.app.tasks.ingest",
            "backend/app/tasks/ingest.py",
        )
    materialize_module = sys.modules.get("backend.app.tasks.materialize")
    if materialize_module is None:
        materialize_module = load_module(
            "backend.app.tasks.materialize",
            "backend/app/tasks/materialize.py",
        )

    data_root = tmp_path / "data_input"
    data_root.mkdir()
    for file_name in ("TYWLSHOW-20251231.xls",):
        (data_root / file_name).write_bytes((ROOT / "data_input" / file_name).read_bytes())

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    ingest_module.ingest_demo_manifest.fn()
    materialize_module.materialize_cache_view.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
        data_root=str(data_root),
    )

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)
    response = client.get("/ui/preview/source-foundation/tyw/traces?limit=5&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["result_meta"]["result_kind"] == "preview.tyw.traces"
    assert body["result"]["total_rows"] > 0
    assert body["result"]["columns"] == [
        {"key": "ingest_batch_id", "label": "批次ID", "type": "string"},
        {"key": "row_locator", "label": "行号", "type": "number"},
        {"key": "trace_step", "label": "轨迹步骤", "type": "number"},
        {"key": "field_name", "label": "字段名", "type": "string"},
        {"key": "field_value", "label": "字段值", "type": "string"},
        {"key": "derived_label", "label": "归类标签", "type": "string"},
        {"key": "manual_review_needed", "label": "需人工复核", "type": "boolean"},
    ]
    get_settings.cache_clear()


def test_preview_traces_api_empty_duckdb_returns_empty_page(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "no_preview_tables.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)
    response = client.get("/ui/preview/source-foundation/tyw/traces?limit=25&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["result_meta"]["result_kind"] == "preview.tyw.traces"
    assert body["result"]["total_rows"] == 0
    assert body["result"]["rows"] == []
    assert body["result"]["limit"] == 25
    assert body["result"]["offset"] == 0
    get_settings.cache_clear()


def test_preview_rows_and_traces_apis_reject_invalid_pagination_query():
    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    bad_queries = [
        "/ui/preview/source-foundation/zqtz/rows?limit=10&offset=-1",
        "/ui/preview/source-foundation/zqtz/rows?limit=0&offset=0",
        "/ui/preview/source-foundation/zqtz/rows?limit=501&offset=0",
        "/ui/preview/source-foundation/zqtz/traces?limit=10&offset=-3",
        "/ui/preview/source-foundation/tyw/traces?limit=0&offset=0",
        "/ui/preview/source-foundation/tyw/traces?limit=600&offset=0",
    ]
    for path in bad_queries:
        assert client.get(path).status_code == 422


def test_preview_rows_and_traces_reject_unsupported_source_family():
    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    for path in (
        "/ui/preview/source-foundation/history?source_family=not-a-family&limit=10&offset=0",
        "/ui/preview/source-foundation/not-a-family/rows?limit=10&offset=0",
        "/ui/preview/source-foundation/not-a-family/traces?limit=10&offset=0",
    ):
        response = client.get(path)
        assert response.status_code == 400
        assert "Unsupported source_family" in response.json()["detail"]


def test_rule_traces_stay_family_scoped_with_tyw_and_pnl514_inputs(tmp_path, monkeypatch):
    preview_module = load_module(
        "backend.app.services.source_preview_service",
        "backend/app/services/source_preview_service.py",
    )
    ingest_module = sys.modules.get("backend.app.tasks.ingest")
    if ingest_module is None:
        ingest_module = load_module(
            "backend.app.tasks.ingest",
            "backend/app/tasks/ingest.py",
        )
    materialize_module = sys.modules.get("backend.app.tasks.materialize")
    if materialize_module is None:
        materialize_module = load_module(
            "backend.app.tasks.materialize",
            "backend/app/tasks/materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    data_root.mkdir()
    (data_root / "TYWLSHOW-20251231.xls").write_bytes((ROOT / "data_input" / "TYWLSHOW-20251231.xls").read_bytes())
    (data_root / "非标514-20250101-1231.xlsx").write_bytes(
        (ROOT / "data_input" / "pnl_514" / "非标514-20250101-1231.xlsx").read_bytes()
    )

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    ingest_module.ingest_demo_manifest.fn()
    materialize_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_root),
    )

    tyw_traces = preview_module.load_rule_traces(
        duckdb_path=str(duckdb_path),
        source_family="tyw",
        limit=200,
        offset=0,
    )
    pnl_traces = preview_module.load_rule_traces(
        duckdb_path=str(duckdb_path),
        source_family="pnl_514",
        limit=200,
        offset=0,
    )

    tyw_fields = {str(row["field_name"]) for row in tyw_traces.rows}
    pnl_fields = {str(row["field_name"]) for row in pnl_traces.rows}

    assert tyw_traces.total_rows > 0
    assert pnl_traces.total_rows > 0
    assert not {"科目号", "资产代码", "借贷标识"} & tyw_fields
    assert {"科目号", "资产代码", "借贷标识"} <= pnl_fields
    get_settings.cache_clear()


def test_materialize_clears_preview_tables_when_requested_ingest_batch_is_missing(tmp_path, monkeypatch):
    ingest_module = sys.modules.get("backend.app.tasks.ingest")
    if ingest_module is None:
        ingest_module = load_module(
            "backend.app.tasks.ingest",
            "backend/app/tasks/ingest.py",
        )
    materialize_module = sys.modules.get("backend.app.tasks.materialize")
    if materialize_module is None:
        materialize_module = load_module(
            "backend.app.tasks.materialize",
            "backend/app/tasks/materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    data_root.mkdir()
    (data_root / "TYWLSHOW-20251231.xls").write_bytes((ROOT / "data_input" / "TYWLSHOW-20251231.xls").read_bytes())
    (data_root / "ZQTZSHOW-20251231.xls").write_bytes((ROOT / "data_input" / "ZQTZSHOW-20251231.xls").read_bytes())

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    ingest_payload = ingest_module.ingest_demo_manifest.fn()
    materialize_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_root),
    )

    payload = materialize_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_root),
        ingest_batch_id="missing-batch",
    )

    assert ingest_payload["row_count"] > 0
    assert payload["preview_sources"] == []

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        assert conn.execute("select count(*) from phase1_source_preview_summary").fetchone()[0] == 0
    finally:
        conn.close()
    get_settings.cache_clear()


def test_materialize_ignores_manifest_rows_whose_archived_paths_no_longer_exist(tmp_path):
    preview_module = load_module(
        "backend.app.repositories.source_preview_repo",
        "backend/app/repositories/source_preview_repo.py",
    )
    governance_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    valid_file = tmp_path / "TYWLSHOW-20251231.xls"
    valid_file.write_bytes((ROOT / "data_input" / "TYWLSHOW-20251231.xls").read_bytes())

    repo = governance_module.GovernanceRepository(base_dir=governance_dir)
    repo.append(
        governance_module.SOURCE_MANIFEST_STREAM,
        {
            "ingest_batch_id": "batch-stale",
            "created_at": "2026-04-10T00:00:02Z",
            "source_family": "tyw",
            "report_date": "2025-12-31",
            "source_file": "TYWLSHOW-20251231.xls",
            "source_version": "sv_stale",
            "archived_path": str(tmp_path / "missing.xls"),
            "status": "completed",
        },
    )
    repo.append(
        governance_module.SOURCE_MANIFEST_STREAM,
        {
            "ingest_batch_id": "batch-valid",
            "created_at": "2026-04-10T00:00:01Z",
            "source_family": "tyw",
            "report_date": "2025-12-31",
            "source_file": "TYWLSHOW-20251231.xls",
            "source_version": "sv_valid",
            "archived_path": str(valid_file),
            "status": "completed",
        },
    )

    summaries = preview_module.materialize_source_previews(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert len(summaries) == 1
    assert summaries[0]["source_version"] == "sv_valid"


def test_preview_rows_and_traces_default_to_latest_batch_for_family(tmp_path, monkeypatch):
    preview_module = load_module(
        "backend.app.services.source_preview_service",
        "backend/app/services/source_preview_service.py",
    )
    repo_module = load_module(
        "backend.app.repositories.source_preview_repo",
        "backend/app/repositories/source_preview_repo.py",
    )
    preview_write_module = load_module(
        "backend.app.repositories.source_preview_repo",
        "backend/app/repositories/source_preview_repo.py",
    )
    materialize_module = load_module(
        "backend.app.tasks.materialize",
        "backend/app/tasks/materialize.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"

    def write_batch(version: str, batch_id: str):
        def _inner(**_: object):
            summaries = [
                {
                    "ingest_batch_id": batch_id,
                    "batch_created_at": batch_id,
                    "source_family": "tyw",
                    "report_date": "2025-12-31",
                    "report_start_date": "2025-12-31",
                    "report_end_date": "2025-12-31",
                    "report_granularity": "day",
                    "source_file": "TYWLSHOW-20251231.xls",
                    "total_rows": 1,
                    "manual_review_count": 0,
                    "source_version": version,
                    "rule_version": preview_write_module.RULE_VERSION,
                    "preview_mode": "manifest",
                    "group_counts": {"存放类": 1},
                }
            ]
            row_records = [
                {
                    "ingest_batch_id": batch_id,
                    "row_locator": 1,
                    "report_date": "2025-12-31",
                    "business_type_primary": "存放同业",
                    "product_group": "存放类",
                    "institution_category": "bank",
                    "special_nature": "普通",
                    "counterparty_name": "A",
                    "investment_portfolio": "回购自营",
                    "manual_review_needed": False,
                    "source_version": version,
                    "rule_version": preview_write_module.RULE_VERSION,
                }
            ]
            trace_records = [
                {
                    "source_family": "tyw",
                    "ingest_batch_id": batch_id,
                    "row_locator": 1,
                    "trace_step": 1,
                    "field_name": "产品类型",
                    "field_value": "存放同业",
                    "derived_label": "存放类",
                    "manual_review_needed": False,
                }
            ]
            preview_write_module._write_preview_tables(str(duckdb_path), summaries, row_records, trace_records)
            return summaries
        return _inner

    monkeypatch.setattr(materialize_module, "materialize_source_previews", write_batch("sv_a", "batch-a"))
    materialize_module.materialize_cache_view.fn(duckdb_path=str(duckdb_path), governance_dir=str(tmp_path / "gov-a"), data_root=str(tmp_path / "input"))
    monkeypatch.setattr(materialize_module, "materialize_source_previews", write_batch("sv_b", "batch-b"))
    materialize_module.materialize_cache_view.fn(duckdb_path=str(duckdb_path), governance_dir=str(tmp_path / "gov-b"), data_root=str(tmp_path / "input"))

    rows_page = preview_module.load_preview_rows(str(duckdb_path), "tyw", limit=50, offset=0)
    traces_page = preview_module.load_rule_traces(str(duckdb_path), "tyw", limit=50, offset=0)
    summary_payload = repo_module.load_source_preview_payload(str(duckdb_path))

    assert summary_payload.sources[0].source_version == "sv_b"
    assert {row["ingest_batch_id"] for row in rows_page.rows} == {"batch-b"}
    assert {row["ingest_batch_id"] for row in traces_page.rows} == {"batch-b"}


def _configure_source_preview_refresh_env(
    tmp_path,
    monkeypatch,
    *,
    include_pnl_preview_source: bool = False,
):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    data_root.mkdir(parents=True, exist_ok=True)

    for file_name in ("ZQTZSHOW-20251231.xls", "TYWLSHOW-20251231.xls"):
        (data_root / file_name).write_bytes((ROOT / "data_input" / file_name).read_bytes())

    if include_pnl_preview_source:
        (data_root / "pnl").mkdir(parents=True, exist_ok=True)
        (data_root / "pnl" / "FI损益202512.xls").write_bytes(
            (ROOT / "data_input" / "pnl" / "FI损益202512.xls").read_bytes()
        )

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    get_settings.cache_clear()
    return duckdb_path, governance_dir, data_root


def _configure_source_preview_status_env(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    return governance_dir
