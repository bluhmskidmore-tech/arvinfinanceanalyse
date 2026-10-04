"""End-to-end: ingest + archive manifests, then materialize standardized snapshots from archives."""

from __future__ import annotations

import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def _biff_record(record_id: int, payload: bytes) -> bytes:
    return struct.pack("<HH", record_id, len(payload)) + payload


def _write_snapshot_xls(path: Path, rows: list[dict[str, object]]) -> None:
    """Write the smallest BIFF2 workbook the snapshot parser accepts.

    Source exports put headers on the second row. Numeric zero is written as a
    NUMBER cell, while None leaves a genuinely missing cell for fail-closed tests.
    """
    headers = list(rows[0])
    parts = [
        _biff_record(0x0009, struct.pack("<HH", 0x0004, 0x0010)),
        _biff_record(0x0042, struct.pack("<H", 936)),
    ]
    xf = b"\x00\x00\x00"
    for row_index, row in enumerate(
        [[], headers, *[[item.get(header) for header in headers] for item in rows]]
    ):
        for column_index, value in enumerate(row):
            if value is None or value == "":
                continue
            prefix = struct.pack("<HH", row_index, column_index) + xf
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                parts.append(
                    _biff_record(0x0003, prefix + struct.pack("<d", float(value)))
                )
            else:
                encoded = str(value).encode("gbk")
                parts.append(
                    _biff_record(0x0004, prefix + bytes([len(encoded)]) + encoded)
                )
    path.write_bytes(b"".join([*parts, _biff_record(0x000A, b"")]))


def _write_synthetic_snapshot_inputs(
    data_root: Path,
    report_date: str,
    *,
    zqtz: bool = True,
    tyw: bool = True,
    missing_zqtz_amount: str | None = None,
    missing_tyw_amount: str | None = None,
    zqtz_market_value: int = 101,
) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    date_suffix = report_date.replace("-", "")
    if zqtz:
        zqtz_rows: list[dict[str, object]] = [
            {
                "日期": report_date,
                "债券代号": "B-CNY",
                "债券名称": "人民币债券",
                "业务种类": "国债",
                "业务种类1": "国债",
                "投资组合": "组合甲",
                "成本中心": "中心甲",
                "资产分类": "债券",
                "币种": "人民币",
                "到期日": "2030-12-31",
                "面值": 100,
                "公允价值": zqtz_market_value,
                "摊余成本": 99,
                "应计利息": 1.25,
                "应收/应付利息": 0.5,
            },
            {
                "日期": report_date,
                "债券代号": "B-USD",
                "债券名称": "美元债券",
                "业务种类": "金融债",
                "业务种类1": "金融债",
                "投资组合": "组合乙",
                "成本中心": "中心乙",
                "资产分类": "债券",
                "币种": "美元",
                "到期日": "2030-12-31",
                "面值": 25,
                "公允价值": 25,
                "摊余成本": 25,
                "应计利息": 0,
                "应收/应付利息": 0,
            },
        ]
        if missing_zqtz_amount is not None:
            zqtz_rows[0][missing_zqtz_amount] = None
        _write_snapshot_xls(data_root / f"ZQTZSHOW-{date_suffix}.xls", zqtz_rows)
    if tyw:
        tyw_rows: list[dict[str, object]] = [
            {
                "流水号": "T-CNY",
                "产品类型": "存放同业",
                "对手方名称": "对手甲",
                "投资组合": "组合甲",
                "币种": "人民币",
                "金额": 100,
                "应计利息": 1,
            },
            {
                "流水号": "T-USD",
                "产品类型": "拆放同业",
                "对手方名称": "对手乙",
                "投资组合": "组合乙",
                "币种": "美元",
                "金额": 40,
                "应计利息": 0,
            },
        ]
        if missing_tyw_amount is not None:
            tyw_rows[0][missing_tyw_amount] = None
        _write_snapshot_xls(data_root / f"TYWLSHOW-{date_suffix}.xls", tyw_rows)


def _load_tasks():
    ingest_mod = sys.modules.get("backend.app.tasks.ingest")
    if ingest_mod is None:
        ingest_mod = load_module(
            "backend.app.tasks.ingest", "backend/app/tasks/ingest.py"
        )
    snap_mod = sys.modules.get("backend.app.tasks.snapshot_materialize")
    if snap_mod is None:
        snap_mod = load_module(
            "backend.app.tasks.snapshot_materialize",
            "backend/app/tasks/snapshot_materialize.py",
        )
    return ingest_mod, snap_mod


def test_snapshot_materialize_explicit_local_archive_path_overrides_object_store_settings(
    tmp_path,
    monkeypatch,
):
    _ingest_mod, snap_mod = _load_tasks()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    explicit_archive_root = tmp_path / "explicit-archive"
    archive_file = (
        explicit_archive_root / "ZQTZSHOW" / "files" / "ZQTZSHOW-20251231.xls"
    )
    archive_file.parent.mkdir(parents=True)
    explicit_payload = b"payload-from-explicit-local-archive"
    archive_file.write_bytes(explicit_payload)

    snap_mod.SourceManifestRepository(
        governance_repo=snap_mod.GovernanceRepository(base_dir=governance_dir),
    ).add_many(
        [
            {
                "source_family": "zqtz",
                "report_date": "2025-12-31",
                "source_file": archive_file.name,
                "source_version": "sv-explicit-archive",
                "ingest_batch_id": "ib-explicit-archive",
                "archived_path": str(archive_file),
            }
        ]
    )

    settings_archive_root = tmp_path / "settings-archive"
    monkeypatch.setattr(
        snap_mod,
        "get_settings",
        lambda: SimpleNamespace(
            duckdb_path=tmp_path / "settings.duckdb",
            governance_path=tmp_path / "settings-governance",
            object_store_mode="minio",
            local_archive_path=settings_archive_root,
            minio_endpoint="network-object-store.invalid:9000",
            minio_access_key="unused",
            minio_secret_key="unused",
            minio_bucket="unused",
        ),
    )

    store_args: list[dict[str, object]] = []
    real_store_type = snap_mod.ObjectStoreRepository

    def _build_store(**kwargs):
        store_args.append(dict(kwargs))
        return real_store_type(**kwargs)

    parsed_payloads: list[bytes] = []

    def _parse_explicit_payload(**kwargs):
        parsed_payloads.append(kwargs["file_bytes"])
        return [{"sentinel": "parsed-explicit-archive"}]

    monkeypatch.setattr(snap_mod, "ObjectStoreRepository", _build_store)
    monkeypatch.setattr(
        snap_mod, "parse_zqtz_snapshot_rows_from_bytes", _parse_explicit_payload
    )
    monkeypatch.setattr(snap_mod, "merge_zqtz_rows_by_grain", lambda rows: rows)
    monkeypatch.setattr(
        snap_mod,
        "replace_zqtz_snapshot_rows",
        lambda _conn, rows, **_kwargs: len(rows),
    )

    payload = snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        source_families=["zqtz"],
        report_date="2025-12-31",
        local_archive_path=str(explicit_archive_root),
    )

    assert payload["status"] == "completed"
    assert payload["zqtz_rows"] == 1
    assert payload["tyw_rows"] == 0
    assert parsed_payloads == [explicit_payload]
    assert len(store_args) == 1
    assert store_args[0]["mode"] == "local"
    assert (
        Path(str(store_args[0]["local_archive_path"])).resolve()
        == explicit_archive_root.resolve()
    )


def test_snapshot_tables_materialize_from_manifest_archives(tmp_path, monkeypatch):
    ingest_mod, snap_mod = _load_tasks()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    _write_synthetic_snapshot_inputs(data_root, "2025-12-31")

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    ingest_mod.ingest_demo_manifest.fn()
    result = snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert result["status"] == "completed"
    assert result["zqtz_rows"] > 0
    assert result["tyw_rows"] > 0
    expected_rule_version = "rv_snapshot_zqtz_tyw_v3"

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        zcols = [
            r[1]
            for r in conn.execute(
                "pragma table_info('zqtz_bond_daily_snapshot')"
            ).fetchall()
        ]
        assert "source_version" in zcols
        assert "rule_version" in zcols
        assert "ingest_batch_id" in zcols
        assert "trace_id" in zcols
        assert "interest_receivable_payable" in zcols

        populated_interest = conn.execute(
            """
            select count(*)
            from zqtz_bond_daily_snapshot
            where interest_receivable_payable is not null
              and interest_receivable_payable <> 0
            """
        ).fetchone()[0]
        assert populated_interest > 0
        assert (
            conn.execute(
                "select accrued_interest_native from zqtz_bond_daily_snapshot where instrument_code = 'B-USD'"
            ).fetchone()[0]
            == 0
        )

        tcols = [
            r[1]
            for r in conn.execute(
                "pragma table_info('tyw_interbank_daily_snapshot')"
            ).fetchall()
        ]
        assert "source_version" in tcols
        assert "rule_version" in tcols
        assert "ingest_batch_id" in tcols
        assert "trace_id" in tcols

        zrow = conn.execute(
            """
            select report_date, instrument_code, portfolio_name, cost_center, currency_code,
                   source_version, rule_version, ingest_batch_id, trace_id
            from zqtz_bond_daily_snapshot
            limit 1
            """
        ).fetchone()
        assert zrow is not None
        assert all(zrow)
        assert zrow[6] == expected_rule_version

        trow = conn.execute(
            """
            select report_date, position_id, source_version, rule_version, ingest_batch_id, trace_id
            from tyw_interbank_daily_snapshot
            limit 1
            """
        ).fetchone()
        assert trow is not None
        assert all(trow)
        assert trow[3] == expected_rule_version
        assert (
            conn.execute(
                "select accrued_interest_native from tyw_interbank_daily_snapshot where position_id = 'T-USD'"
            ).fetchone()[0]
            == 0
        )
    finally:
        conn.close()

    manifests = snap_mod.GovernanceRepository(base_dir=governance_dir).read_all(
        snap_mod.SNAPSHOT_MANIFEST_STREAM
    )
    assert {
        (record["target_table"], record["rule_version"])
        for record in manifests
        if record["snapshot_run_id"] == result["snapshot_run_id"]
    } == {
        ("zqtz_bond_daily_snapshot", expected_rule_version),
        ("tyw_interbank_daily_snapshot", expected_rule_version),
    }

    get_settings.cache_clear()


def test_snapshot_materialize_respects_report_date_filter(tmp_path, monkeypatch):
    ingest_mod, snap_mod = _load_tasks()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    _write_synthetic_snapshot_inputs(data_root, "2025-12-31")

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    ingest_mod.ingest_demo_manifest.fn()
    full = snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    assert full["zqtz_rows"] > 0

    filtered = snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
    )
    assert filtered["zqtz_rows"] == full["zqtz_rows"]

    empty_scope = snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2099-01-01",
    )
    assert empty_scope["zqtz_rows"] == 0
    assert empty_scope["tyw_rows"] == 0

    get_settings.cache_clear()


def test_snapshot_materialize_locfs_tyw_missing_report_date(tmp_path, monkeypatch):
    ingest_mod, snap_mod = _load_tasks()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    _write_synthetic_snapshot_inputs(data_root, "2026-03-25", zqtz=False)
    _write_synthetic_snapshot_inputs(data_root, "2026-03-26", tyw=False)
    _write_synthetic_snapshot_inputs(data_root, "2026-03-27", tyw=False)

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    ingest_mod.ingest_demo_manifest.fn()
    prior = snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        source_families=["tyw"],
        report_date="2026-03-25",
    )
    assert prior["tyw_rows"] > 0

    locf = snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        source_families=["zqtz", "tyw"],
        report_date="2026-03-26",
    )

    assert locf["zqtz_rows"] > 0
    assert locf["tyw_rows"] == prior["tyw_rows"]

    chained = snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        source_families=["zqtz", "tyw"],
        report_date="2026-03-27",
    )
    assert chained["tyw_rows"] == prior["tyw_rows"]

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        prior_sum, locf_sum = conn.execute(
            """
            select
              sum(case when report_date = date '2026-03-25' then principal_native else 0 end),
              sum(case when report_date = date '2026-03-26' then principal_native else 0 end)
            from tyw_interbank_daily_snapshot
            where report_date in (date '2026-03-25', date '2026-03-26')
            """
        ).fetchone()
        rule_version, source_version, ingest_batch_id, trace_id = conn.execute(
            """
            select min(rule_version), min(source_version), min(ingest_batch_id), min(trace_id)
            from tyw_interbank_daily_snapshot
            where report_date = date '2026-03-26'
            """
        ).fetchone()
        chained_rule_versions = conn.execute(
            "select distinct rule_version from tyw_interbank_daily_snapshot "
            "where report_date = date '2026-03-27'"
        ).fetchall()
    finally:
        conn.close()

    assert locf_sum == prior_sum
    assert rule_version == "rv_snapshot_zqtz_tyw_v3__locf"
    assert chained_rule_versions == [("rv_snapshot_zqtz_tyw_v3__locf",)]
    assert str(source_version).startswith("sv_tyw_locf_")
    assert ingest_batch_id == "locf:2026-03-25"
    assert str(trace_id).startswith("locf:2026-03-26:from:2026-03-25")

    get_settings.cache_clear()


@pytest.mark.parametrize(
    "old_rule_version",
    ("rv_snapshot_zqtz_tyw_v1", "rv_snapshot_zqtz_tyw_v2"),
)
def test_tyw_locf_rejects_old_source_rows_under_v3_rule(
    tmp_path, monkeypatch, old_rule_version,
):
    ingest_mod, snap_mod = _load_tasks()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    _write_synthetic_snapshot_inputs(data_root, "2026-03-25", zqtz=False)
    _write_synthetic_snapshot_inputs(data_root, "2026-03-26", tyw=False)

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    ingest_mod.ingest_demo_manifest.fn()
    with monkeypatch.context() as old_rule:
        old_rule.setattr(snap_mod, "SNAPSHOT_RULE_VERSION", old_rule_version)
        prior = snap_mod.materialize_standard_snapshots.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            source_families=["tyw"],
            report_date="2026-03-25",
        )
    assert prior["tyw_rows"] > 0

    with pytest.raises(ValueError, match=r"TYW LOCF source.*rule_version"):
        snap_mod.materialize_standard_snapshots.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            source_families=["zqtz", "tyw"],
            report_date="2026-03-26",
        )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        assert conn.execute(
            "select distinct rule_version from tyw_interbank_daily_snapshot "
            "where report_date = date '2026-03-25'"
        ).fetchall() == [(old_rule_version,)]
        assert conn.execute(
            "select count(*) from zqtz_bond_daily_snapshot "
            "where report_date = date '2026-03-26'"
        ).fetchone() == (0,)
        assert conn.execute(
            "select count(*) from tyw_interbank_daily_snapshot "
            "where report_date = date '2026-03-26'"
        ).fetchone() == (0,)
    finally:
        conn.close()

    manifests = snap_mod.GovernanceRepository(base_dir=governance_dir).read_all(
        snap_mod.SNAPSHOT_MANIFEST_STREAM
    )
    assert len(manifests) == 1
    assert manifests[0]["snapshot_run_id"] == prior["snapshot_run_id"]
    assert manifests[0]["rule_version"] == old_rule_version

    get_settings.cache_clear()


def test_snapshot_materialize_normalizes_currency_labels_to_iso_codes(
    tmp_path, monkeypatch
):
    ingest_mod, snap_mod = _load_tasks()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    _write_synthetic_snapshot_inputs(data_root, "2025-12-31")

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    ingest_mod.ingest_demo_manifest.fn()
    snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        zqtz_codes = {
            row[0]
            for row in conn.execute(
                "select distinct currency_code from zqtz_bond_daily_snapshot"
            ).fetchall()
        }
        tyw_codes = {
            row[0]
            for row in conn.execute(
                "select distinct currency_code from tyw_interbank_daily_snapshot"
            ).fetchall()
        }
    finally:
        conn.close()

    assert zqtz_codes == {"CNY", "USD"}
    assert tyw_codes == {"CNY", "USD"}

    get_settings.cache_clear()


def test_snapshot_materialize_keeps_prior_report_dates_within_same_ingest_batch(
    tmp_path, monkeypatch
):
    ingest_mod, snap_mod = _load_tasks()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    _write_synthetic_snapshot_inputs(data_root, "2025-12-31")
    _write_synthetic_snapshot_inputs(data_root, "2026-01-01")

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    ingest_payload = ingest_mod.ingest_demo_manifest.fn()
    ingest_batch_id = ingest_payload["ingest_batch_id"]

    snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        ingest_batch_id=ingest_batch_id,
        source_families=["zqtz", "tyw"],
        report_date="2025-12-31",
    )
    snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        ingest_batch_id=ingest_batch_id,
        source_families=["zqtz", "tyw"],
        report_date="2026-01-01",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        zqtz_dates = [
            row[0].isoformat()
            for row in conn.execute(
                "select distinct report_date from zqtz_bond_daily_snapshot order by report_date"
            ).fetchall()
        ]
        tyw_dates = [
            row[0].isoformat()
            for row in conn.execute(
                "select distinct report_date from tyw_interbank_daily_snapshot order by report_date"
            ).fetchall()
        ]
    finally:
        conn.close()

    assert zqtz_dates == ["2025-12-31", "2026-01-01"]
    assert tyw_dates == ["2025-12-31", "2026-01-01"]

    get_settings.cache_clear()


def test_snapshot_materialize_explicit_ingest_batch_replaces_whole_report_date_slice(
    tmp_path, monkeypatch
):
    ingest_mod, snap_mod = _load_tasks()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    _write_synthetic_snapshot_inputs(data_root, "2025-12-31")

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    first = ingest_mod.ingest_demo_manifest.fn()
    first_batch_id = first["ingest_batch_id"]
    snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        ingest_batch_id=first_batch_id,
        source_families=["zqtz", "tyw"],
        report_date="2025-12-31",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            "update zqtz_bond_daily_snapshot set ingest_batch_id = 'ib-old' where report_date = date '2025-12-31'"
        )
        conn.execute(
            "update tyw_interbank_daily_snapshot set ingest_batch_id = 'ib-old' where report_date = date '2025-12-31'"
        )
    finally:
        conn.close()

    snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        ingest_batch_id=first_batch_id,
        source_families=["zqtz", "tyw"],
        report_date="2025-12-31",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        z_batches = {
            row[0]
            for row in conn.execute(
                "select distinct ingest_batch_id from zqtz_bond_daily_snapshot where report_date = date '2025-12-31'"
            ).fetchall()
        }
        t_batches = {
            row[0]
            for row in conn.execute(
                "select distinct ingest_batch_id from tyw_interbank_daily_snapshot where report_date = date '2025-12-31'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert z_batches == {first_batch_id}
    assert t_batches == {first_batch_id}

    get_settings.cache_clear()


def test_missing_required_amount_rolls_back_both_snapshot_families(
    tmp_path, monkeypatch
):
    ingest_mod, snap_mod = _load_tasks()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    _write_synthetic_snapshot_inputs(data_root, "2025-12-31")

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    first_batch = ingest_mod.ingest_demo_manifest.fn()["ingest_batch_id"]
    snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        ingest_batch_id=first_batch,
        source_families=["zqtz", "tyw"],
        report_date="2025-12-31",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        original_zqtz = conn.execute(
            "select instrument_code, market_value_native, ingest_batch_id "
            "from zqtz_bond_daily_snapshot order by instrument_code"
        ).fetchall()
        original_tyw = conn.execute(
            "select position_id, principal_native, ingest_batch_id "
            "from tyw_interbank_daily_snapshot order by position_id"
        ).fetchall()
    finally:
        conn.close()
    assert len(original_zqtz) == len(original_tyw) == 2
    assert original_zqtz[0][1] == 101

    # A new batch replaces the ZQTZ date slice first, then encounters a truly
    # absent TYW amount. Both writes must roll back to the prior batch.
    _write_synthetic_snapshot_inputs(
        data_root,
        "2025-12-31",
        zqtz_market_value=202,
        missing_tyw_amount="应计利息",
    )
    replacement = ingest_mod.ingest_demo_manifest.fn()
    assert replacement["row_count"] == 2
    assert replacement["ingest_batch_id"] != first_batch
    with pytest.raises(
        ValueError, match=r"TYW required amount invalid: header=应计利息, row=3"
    ):
        snap_mod.materialize_standard_snapshots.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            ingest_batch_id=replacement["ingest_batch_id"],
            source_families=["zqtz", "tyw"],
            report_date="2025-12-31",
        )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        assert (
            conn.execute(
                "select instrument_code, market_value_native, ingest_batch_id "
                "from zqtz_bond_daily_snapshot order by instrument_code"
            ).fetchall()
            == original_zqtz
        )
        assert (
            conn.execute(
                "select position_id, principal_native, ingest_batch_id "
                "from tyw_interbank_daily_snapshot order by position_id"
            ).fetchall()
            == original_tyw
        )
    finally:
        conn.close()

    get_settings.cache_clear()
