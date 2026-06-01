from __future__ import annotations

import sys
from pathlib import Path

import duckdb
from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.app.governance.settings import get_settings
from tests.helpers import ROOT, load_module


NONSTD_HEADERS = [
    "账务流水号",
    "序号",
    "所属账套",
    "账务日期",
    "交易流水号",
    "内部账户号",
    "产品类型",
    "客户名称",
    "会计分类",
    "成本中心",
    "投资组合",
    "资产代码",
    "交易机构",
    "会计事件",
    "币种",
    "借贷标识",
    "科目号",
    "科目名称",
    "金额",
    "备注",
]


def test_source_preview_service_summarizes_real_fi_pnl_file():
    preview_module = load_module(
        "backend.app.services.source_preview_service",
        "backend/app/services/source_preview_service.py",
    )

    fi_file = ROOT / "data_input" / "pnl" / "FI损益202512.xls"
    summary = preview_module.summarize_source_file(fi_file)

    assert summary["source_family"] == "pnl"
    assert summary["report_date"] == "2025-12-31"
    assert summary["total_rows"] > 0
    assert summary["preview_mode"] == "tabular"
    assert sum(summary["group_counts"].values()) == summary["total_rows"]
    assert "H" in summary["group_counts"]


def test_materialize_preview_supports_pnl_and_nonstd_rows_and_traces(tmp_path, monkeypatch):
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
    (data_root / "pnl").mkdir(parents=True)
    (data_root / "pnl_516").mkdir(parents=True)

    fi_target = data_root / "pnl" / "FI损益202512.xls"
    fi_target.write_bytes((ROOT / "data_input" / "pnl" / "FI损益202512.xls").read_bytes())
    _write_nonstd_preview_workbook(data_root / "pnl_516" / "非标516-20260101-0228.xlsx")

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    ingest_payload = ingest_module.ingest_demo_manifest.fn()
    materialize_payload = materialize_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_root),
    )

    assert ingest_payload["row_count"] == 2
    assert set(materialize_payload["preview_sources"]) == {"pnl", "pnl_516"}
    assert len(materialize_payload["preview_sources"]) == 2

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        summary_rows = conn.execute(
            """
            select source_family, total_rows
            from phase1_source_preview_summary
            """
        ).fetchall()
    finally:
        conn.close()

    by_family = {family: total for family, total in summary_rows}
    assert by_family.keys() == {"pnl", "pnl_516"}
    assert by_family["pnl"] > 0
    assert by_family["pnl_516"] == 2

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)
    ingest_batch_id = ingest_payload["ingest_batch_id"]

    fi_rows = client.get(
        f"/ui/preview/source-foundation/pnl/rows?ingest_batch_id={ingest_batch_id}&limit=2&offset=0"
    )
    fi_traces = client.get(
        f"/ui/preview/source-foundation/pnl/traces?ingest_batch_id={ingest_batch_id}&limit=3&offset=0"
    )
    nonstd_rows = client.get(
        f"/ui/preview/source-foundation/pnl_516/rows?ingest_batch_id={ingest_batch_id}&limit=2&offset=0"
    )
    nonstd_traces = client.get(
        f"/ui/preview/source-foundation/pnl_516/traces?ingest_batch_id={ingest_batch_id}&limit=3&offset=0"
    )

    for response in (fi_rows, fi_traces, nonstd_rows, nonstd_traces):
        assert response.status_code == 503
        body = response.json()
        assert "result_meta" not in body
        assert "reserved" in str(body.get("detail", "")).lower()
    get_settings.cache_clear()


def test_mixed_family_materialize_does_not_pollute_tyw_trace_contract(tmp_path, monkeypatch):
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
    (data_root / "pnl").mkdir(parents=True)
    (data_root / "pnl_516").mkdir(parents=True)
    (data_root / "pnl" / "FI损益202512.xls").write_bytes((ROOT / "data_input" / "pnl" / "FI损益202512.xls").read_bytes())
    _write_nonstd_preview_workbook(data_root / "pnl_516" / "非标516-20260101-0228.xlsx")

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    ingest_payload = ingest_module.ingest_demo_manifest.fn()
    materialize_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_root),
    )

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)
    tyw_traces = client.get(
        f"/ui/preview/source-foundation/tyw/traces?ingest_batch_id={ingest_payload['ingest_batch_id']}&limit=20&offset=0"
    )

    assert tyw_traces.status_code == 503
    body = tyw_traces.json()
    assert "result_meta" not in body
    assert "reserved" in str(body.get("detail", "")).lower()
    get_settings.cache_clear()


def _write_nonstd_preview_workbook(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sheet1"
    worksheet.append(["会计分录详情表"])
    worksheet.append(NONSTD_HEADERS)
    worksheet.append(
        [
            "1411968",
            "1",
            "默认账套",
            "2026-02-27",
            "TRD001",
            "",
            "证券投资基金",
            "测试产品A",
            "FVTPL",
            "5010",
            "FIOA",
            "SA001",
            "80002",
            "冲销前一日估值",
            "人民币",
            "贷",
            "51601010004",
            "公允价值变动损益",
            "-2090626.5",
            "revmtm_val|",
        ]
    )
    worksheet.append(
        [
            "1411969",
            "2",
            "默认账套",
            "2026-02-28",
            "TRD002",
            "",
            "证券投资基金",
            "测试产品B",
            "FVTPL",
            "5010",
            "FIOA",
            "SA002",
            "80002",
            "估值入账",
            "人民币",
            "借",
            "51601010004",
            "公允价值变动损益",
            "1450.25",
            "mtm_val|",
        ]
    )
    workbook.save(path)
