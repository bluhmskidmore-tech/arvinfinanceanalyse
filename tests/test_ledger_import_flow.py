from __future__ import annotations

import csv
import hashlib
import io
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def test_fastapi_application_registers_ledger_import_routes(tmp_path, monkeypatch):
    _configure_ledger_import_env(tmp_path, monkeypatch)

    app = load_module("backend.app.main", "backend/app/main.py").app
    paths = {route.path for route in app.routes}

    assert "/api/ledger/import" in paths
    assert "/api/ledger/imports" in paths
    get_settings.cache_clear()


def test_ledger_import_api_imports_csv_lists_batch_and_preserves_unknown_raw_json(
    tmp_path,
    monkeypatch,
):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    csv_bytes = _ledger_csv_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="240001.IB",
                account_category="银行账户",
                asset_class="持有至到期类资产",
                face_amount="100.25",
                as_of_date="2026-03-17",
            )
        ],
        unknown_value="kept-in-raw-json",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post(
        "/api/ledger/import",
        files={"file": ("ZQTZSHOW-20260317.csv", csv_bytes, "text/csv")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["batch_id"] == 1
    assert payload["data"]["file_name"] == "ZQTZSHOW-20260317.csv"
    assert payload["data"]["file_hash"].startswith("sha256:")
    assert payload["data"]["as_of_date"] == "2026-03-17"
    assert payload["data"]["status"] == "success"
    assert payload["data"]["row_count"] == 1
    assert payload["data"]["error_count"] == 0
    assert payload["data"]["source_version"].startswith("sv_ledger_")
    assert payload["data"]["rule_version"] == "position_key_contract_v1"
    assert payload["metadata"]["no_data"] is False
    assert payload["trace"]["source_file_hash"] == payload["data"]["file_hash"]

    list_response = client.get("/api/ledger/imports")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["data"]["items"][0]["batch_id"] == 1
    assert listed["data"]["items"][0]["filename"] == "ZQTZSHOW-20260317.csv"
    assert listed["data"]["total"] == 1
    assert listed["metadata"]["no_data"] is False

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        raw_json = conn.execute("select raw_json from ledger_raw_row where batch_id = 1 and row_no = 1").fetchone()[0]
        snapshot = conn.execute(
            """
            select direction, face_amount, account_category_std, asset_class_std
            from position_snapshot
            where batch_id = 1 and row_no = 1
            """
        ).fetchone()
    finally:
        conn.close()

    assert "kept-in-raw-json" in raw_json
    assert snapshot == ("ASSET", pytest.approx(100.25), "银行账户", "持有至到期类资产")
    get_settings.cache_clear()


def test_ledger_import_position_key_matches_frozen_contract(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    csv_bytes = _ledger_csv_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="abc001.ib",
                account_category="银行账户",
                asset_class="持有至到期类资产",
                face_amount="10",
                as_of_date="2026-03-17",
            )
        ],
    )

    result = service_mod.LedgerImportService(str(duckdb_path)).import_file(
        file_name="ZQTZSHOW-20260317.csv",
        content=csv_bytes,
    )

    expected_canonical = "|".join(
        [
            "ABC001.IB",
            "ABC001.IB-NAME",
            "FIOA",
            "银行账户",
            "5010",
            "持有至到期类资产",
            "CNY",
            "3000000001",
            "ID-001",
            "LEGAL-001",
            "2024-01-01",
            "2029-01-01",
            "BANK",
        ]
    )
    expected_key = hashlib.sha256(expected_canonical.encode("utf-8")).hexdigest()

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        position_key = conn.execute(
            "select position_key from position_snapshot where batch_id = ?",
            [result["data"]["batch_id"]],
        ).fetchone()[0]
    finally:
        conn.close()

    assert position_key == expected_key
    assert len(position_key) == 64
    get_settings.cache_clear()


def test_ledger_import_parser_supports_xlsx_blank_amounts_and_liability_alias(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    xlsx_bytes = _ledger_xlsx_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="BOND-LIABILITY",
                account_category="发行类债劵",
                asset_class="发行类债券",
                face_amount="",
                as_of_date="2026-03-17",
            )
        ],
        unknown_value="xlsx-unknown",
    )

    result = service_mod.LedgerImportService(str(duckdb_path)).import_file(
        file_name="ZQTZSHOW-20260317.xlsx",
        content=xlsx_bytes,
    )

    assert result["data"]["status"] == "success"
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row = conn.execute(
            """
            select direction, face_amount, account_category_std, asset_class_std, raw_json
            from position_snapshot s
            join ledger_raw_row r using (batch_id, row_no)
            where s.batch_id = ?
            """,
            [result["data"]["batch_id"]],
        ).fetchone()
    finally:
        conn.close()

    assert row[0] == "LIABILITY"
    assert row[1] is None
    assert row[2] == "发行类债券"
    assert row[3] == "发行类债券"
    assert "xlsx-unknown" in row[4]
    get_settings.cache_clear()


def test_ledger_import_returns_contract_error_envelope_for_invalid_request(tmp_path, monkeypatch):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.post("/api/ledger/import", content=b"not multipart")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "LEDGER_IMPORT_INVALID_REQUEST"
    assert payload["error"]["retryable"] is False
    assert "Content-Type must be multipart/form-data" in payload["error"]["message"]
    assert payload["trace"]["request_id"].startswith("req_ledger_")
    assert "detail" not in payload
    get_settings.cache_clear()


def test_ledger_import_duplicate_file_returns_409_and_does_not_duplicate_snapshots(
    tmp_path,
    monkeypatch,
):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    csv_bytes = _ledger_csv_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="DUP-001",
                account_category="银行账户",
                asset_class="持有至到期类资产",
                face_amount="10",
                as_of_date="2026-03-17",
            )
        ],
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    first = client.post(
        "/api/ledger/import",
        files={"file": ("ZQTZSHOW-20260317.csv", csv_bytes, "text/csv")},
    )
    duplicate = client.post(
        "/api/ledger/import",
        files={"file": ("ZQTZSHOW-20260317-copy.csv", csv_bytes, "text/csv")},
    )

    assert first.status_code == 200
    assert duplicate.status_code == 409
    duplicate_payload = duplicate.json()
    assert duplicate_payload["error"]["code"] == "LEDGER_IMPORT_DUPLICATE"
    assert duplicate_payload["data"]["status"] == "duplicate"
    assert duplicate_payload["trace"]["duplicate_of_batch_id"] == first.json()["data"]["batch_id"]

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        batch_count = conn.execute("select count(*) from ledger_import_batch").fetchone()[0]
        snapshot_count = conn.execute("select count(*) from position_snapshot").fetchone()[0]
    finally:
        conn.close()

    assert batch_count == 1
    assert snapshot_count == 1
    get_settings.cache_clear()


def test_ledger_import_concurrent_duplicate_file_creates_one_successful_snapshot(
    tmp_path,
    monkeypatch,
):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    csv_bytes = _ledger_csv_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="DUP-CONCURRENT",
                account_category="银行账户",
                asset_class="持有至到期类资产",
                face_amount="10",
                as_of_date="2026-03-17",
            )
        ],
    )

    def import_copy(file_name: str) -> str:
        payload = service_mod.LedgerImportService(str(duckdb_path)).import_file(
            file_name=file_name,
            content=csv_bytes,
        )
        return str(payload["data"]["status"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(
            executor.map(
                import_copy,
                ["ZQTZSHOW-20260317-a.csv", "ZQTZSHOW-20260317-b.csv"],
            )
        )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        batch_count = conn.execute("select count(*) from ledger_import_batch").fetchone()[0]
        snapshot_count = conn.execute("select count(*) from position_snapshot").fetchone()[0]
    finally:
        conn.close()

    assert statuses == ["duplicate", "success"]
    assert batch_count == 1
    assert snapshot_count == 1
    get_settings.cache_clear()


def test_ledger_import_real_pack_seven_xls_samples_import_without_errors(tmp_path, monkeypatch):
    pack_dir = _pack_dir()
    if pack_dir is None:
        pytest.skip("bank ledger pack sample_ledgers directory is not available")
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    service = service_mod.LedgerImportService(str(duckdb_path))
    sample_names = [
        "ZQTZSHOW-20260301(3).xls",
        "ZQTZSHOW-20260303.xls",
        "ZQTZSHOW-20260310.xls",
        "ZQTZSHOW-20260311.xls",
        "ZQTZSHOW-20260312.xls",
        "ZQTZSHOW-20260314.xls",
        "ZQTZSHOW-20260317.xls",
    ]

    payloads = [
        service.import_file(
            file_name=sample_name,
            content=(pack_dir / "sample_ledgers" / sample_name).read_bytes(),
        )
        for sample_name in sample_names
    ]

    assert [payload["data"]["status"] for payload in payloads] == ["success"] * 7
    assert all(payload["data"]["row_count"] > 0 for payload in payloads)
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        batch_count = conn.execute("select count(*) from ledger_import_batch").fetchone()[0]
        raw_count = conn.execute("select count(*) from ledger_raw_row").fetchone()[0]
        snapshot_count = conn.execute("select count(*) from position_snapshot").fetchone()[0]
    finally:
        conn.close()

    assert batch_count == 7
    assert raw_count == snapshot_count
    get_settings.cache_clear()


def test_ledger_import_real_pack_20260317_golden_counts(tmp_path, monkeypatch):
    sample = _pack_sample("ZQTZSHOW-20260317.xls")
    if sample is None:
        pytest.skip("bank ledger pack sample ZQTZSHOW-20260317.xls is not available")
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )

    result = service_mod.LedgerImportService(str(duckdb_path)).import_file(
        file_name=sample.name,
        content=sample.read_bytes(),
    )

    assert result["data"]["row_count"] == 1838
    assert result["data"]["as_of_date"] == "2026-03-17"
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        counts = conn.execute(
            """
            select
              count(*) as total_rows,
              sum(case when direction = 'ASSET' then 1 else 0 end) as asset_rows,
              sum(case when direction = 'LIABILITY' then 1 else 0 end) as liability_rows,
              round(sum(case when direction = 'ASSET' then face_amount else 0 end) / 100000000, 2) as asset_face_100m,
              round(sum(case when direction = 'LIABILITY' then face_amount else 0 end) / 100000000, 2) as liability_face_100m
            from position_snapshot
            where batch_id = ?
            """,
            [result["data"]["batch_id"]],
        ).fetchone()
        traced = conn.execute(
            """
            select count(*)
            from position_snapshot s
            join ledger_raw_row r using (batch_id, row_no)
            where s.batch_id = ?
            """,
            [result["data"]["batch_id"]],
        ).fetchone()[0]
    finally:
        conn.close()

    assert counts == (1838, 1706, 132, pytest.approx(3289.07), pytest.approx(1231.77))
    assert traced == 1838
    get_settings.cache_clear()


def test_ledger_import_schema_registry_adds_batch_raw_and_snapshot_tables():
    loader = load_module(
        "backend.app.schema_registry.duckdb_loader",
        "backend/app/schema_registry/duckdb_loader.py",
    )
    conn = duckdb.connect(":memory:")
    try:
        loader.apply_registry_sql(conn)
        tables = {
            row[0]
            for row in conn.execute(
                """
                select table_name
                from information_schema.tables
                where table_schema = 'main'
                """
            ).fetchall()
        }
    finally:
        conn.close()

    assert {"ledger_import_batch", "ledger_raw_row", "position_snapshot"} <= tables


def _configure_ledger_import_env(tmp_path, monkeypatch) -> Path:
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    return duckdb_path


def _ledger_csv_bytes(service_mod, rows: list[list[object]], *, unknown_value: str = "") -> bytes:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["ZQTZSHOW"])
    writer.writerow([spec.source_field for spec in service_mod.FIELD_SPECS] + ["未知列"])
    for row in rows:
        writer.writerow([*row, unknown_value])
    return output.getvalue().encode("utf-8-sig")


def _ledger_xlsx_bytes(service_mod, rows: list[list[object]], *, unknown_value: str = "") -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "ZQTZSHOW"
    worksheet.append(["ZQTZSHOW"])
    worksheet.append([spec.source_field for spec in service_mod.FIELD_SPECS] + ["未知列"])
    for row in rows:
        worksheet.append([*row, unknown_value])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def _ledger_row_values(
    service_mod,
    *,
    bond_code: str,
    account_category: str,
    asset_class: str,
    face_amount: str,
    as_of_date: str,
) -> list[object]:
    values = {
        "bond_code": bond_code,
        "bond_name": f"{bond_code}-name",
        "counterparty_cif_no": "3000000001",
        "portfolio": "FIOA",
        "as_of_date": as_of_date,
        "business_type": "资产支持证券",
        "business_type_1": "资产支持证券",
        "account_category_std": account_category,
        "cost_center": "5010      ",
        "asset_class_std": asset_class,
        "face_amount": face_amount,
        "fair_value": "99.50",
        "amortized_cost": "98.25",
        "accrued_interest": "1.25",
        "interest_method": "固定",
        "coupon_rate": "0.025",
        "interest_start_date": "2024-01-01",
        "maturity_date": "2029-01-01",
        "credit_customer_id": "ID-001",
        "credit_customer_rating": "AAA",
        "credit_customer_industry": "金融",
        "interest_receivable_payable": "1.25",
        "currency": "CNY",
        "channel": "BANK",
        "legal_customer_id": "LEGAL-001",
        "quantity": "100",
        "latest_face_value": "100",
        "yield_to_maturity": "0.026",
        "option_or_special_maturity_date": "2029-01-01",
    }
    return [values.get(spec.standard_field, "") for spec in service_mod.FIELD_SPECS]


def _pack_sample(file_name: str) -> Path | None:
    pack_dir = _pack_dir()
    if pack_dir is None:
        return None
    sample = pack_dir / "sample_ledgers" / file_name
    return sample if sample.exists() else None


def _pack_dir() -> Path | None:
    candidates: list[Path] = []
    env_dir = os.getenv("MOSS_BANK_LEDGER_PACK_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.append(
        Path(
            r"C:\Users\arvin\AppData\Local\Temp\bank_ledger_codex_pack_20260427_readonly\bank_ledger_codex_pack"
        )
    )
    for base in candidates:
        if (base / "sample_ledgers").is_dir():
            return base
    return None
