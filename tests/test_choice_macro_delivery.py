from __future__ import annotations

import json
import sys

import duckdb
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def _choice_series_json() -> str:
    return json.dumps(
        [
            {
                "series_id": "cn_cpi_yoy",
                "series_name": "CN CPI YoY",
                "vendor_series_code": "EDB_CPI_YOY",
                "frequency": "daily",
                "unit": "pct",
            },
            {
                "series_id": "cn_repo_7d",
                "series_name": "CN Repo 7D",
                "vendor_series_code": "EDB_REPO_7D",
                "frequency": "daily",
                "unit": "pct",
            },
        ],
        ensure_ascii=False,
    )


def _write_choice_macro_catalog(path) -> None:
    path.write_text(
        json.dumps(
            {
                "catalog_version": "2026-04-10.choice-macro.v1",
                "vendor_name": "choice",
                "generated_at": "2026-04-10T09:00:00Z",
                "generated_from": "tests.fixture.choice_macro_catalog",
                "batches": [
                    {
                        "batch_id": "catalog_cmd1",
                        "request_options": {
                            "IsPublishDate": 1,
                            "RowIndex": 1,
                            "Ispandas": 1,
                        },
                        "series": [
                            {
                                "series_id": "cn_cpi_yoy",
                                "series_name": "CN CPI YoY",
                                "vendor_series_code": "EDB_CPI_YOY",
                                "frequency": "monthly",
                                "unit": "pct",
                                "theme": "inflation",
                                "is_core": True,
                                "tags": ["china", "macro", "inflation"],
                            },
                            {
                                "series_id": "cn_repo_7d",
                                "series_name": "CN Repo 7D",
                                "vendor_series_code": "EDB_REPO_7D",
                                "frequency": "daily",
                                "unit": "pct",
                                "theme": "liquidity",
                                "is_core": True,
                                "tags": ["china", "rates", "liquidity"],
                            },
                        ],
                    },
                    {
                        "batch_id": "catalog_cmd2",
                        "request_options": {
                            "IsLatest": 0,
                            "StartDate": "2026-04-09",
                            "EndDate": "2026-04-09",
                        },
                        "series": [
                            {
                                "series_id": "cn_m2_yoy",
                                "series_name": "CN M2 YoY",
                                "vendor_series_code": "EDB_M2_YOY",
                                "frequency": "monthly",
                                "unit": "pct",
                                "theme": "money_supply",
                                "is_core": False,
                                "tags": ["china", "macro", "money_supply"],
                            }
                        ],
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _choice_gateway_payload() -> dict[str, object]:
    return {
        "vendor_version": "vv_choice_20260409T140000Z",
        "captured_at": "2026-04-09T14:00:00Z",
        "series": [
            {
                "series_id": "cn_cpi_yoy",
                "series_name": "CN CPI YoY",
                "vendor_series_code": "EDB_CPI_YOY",
                "trade_date": "2026-04-09",
                "value_numeric": 0.7,
                "frequency": "daily",
                "unit": "pct",
            },
            {
                "series_id": "cn_repo_7d",
                "series_name": "CN Repo 7D",
                "vendor_series_code": "EDB_REPO_7D",
                "trade_date": "2026-04-09",
                "value_numeric": 1.82,
                "frequency": "daily",
                "unit": "pct",
            },
        ],
    }


def test_choice_adapter_fetch_macro_snapshot_uses_choice_client_contract(monkeypatch):
    schema_module = load_module(
        "backend.app.schemas.macro_vendor",
        "backend/app/schemas/macro_vendor.py",
    )
    adapter_module = load_module(
        "backend.app.repositories.choice_adapter",
        "backend/app/repositories/choice_adapter.py",
    )

    captured: dict[str, object] = {}

    class FakeChoiceClient:
        def start(self):
            captured["started"] = True
            return 0

        def edb(self, codes: list[str], options: str = ""):
            captured["codes"] = codes
            captured["options"] = options
            return type(
                "FakeEmData",
                (),
                {
                    "ErrorCode": 0,
                    "ErrorMsg": "success",
                    "Codes": ["EDB_CPI_YOY", "EDB_REPO_7D"],
                    "Indicators": ["VALUE"],
                    "Dates": ["2026-04-09"],
                    "Data": {
                        "EDB_CPI_YOY": [[0.7]],
                        "EDB_REPO_7D": [[1.82]],
                    },
                },
            )()

    monkeypatch.setattr(adapter_module, "ChoiceClient", lambda: FakeChoiceClient())

    configs = [
        schema_module.ChoiceMacroSeriesConfig(
            series_id="cn_cpi_yoy",
            series_name="CN CPI YoY",
            vendor_series_code="EDB_CPI_YOY",
            frequency="daily",
            unit="pct",
        ),
        schema_module.ChoiceMacroSeriesConfig(
            series_id="cn_repo_7d",
            series_name="CN Repo 7D",
            vendor_series_code="EDB_REPO_7D",
            frequency="daily",
            unit="pct",
        ),
    ]

    snapshot = adapter_module.VendorAdapter().fetch_macro_snapshot(configs)

    assert captured["started"] is True
    assert captured["codes"] == ["EDB_CPI_YOY", "EDB_REPO_7D"]
    assert "IsPublishDate=1" in captured["options"]
    assert "RowIndex=1" in captured["options"]
    assert snapshot.vendor_version == "vv_choice_edb_20260409"
    assert [item.series_id for item in snapshot.series] == ["cn_cpi_yoy", "cn_repo_7d"]


def test_choice_macro_refresh_archives_raw_payload_and_materializes_duckdb(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", "")
    monkeypatch.setenv("MOSS_CHOICE_MACRO_URL", "https://choice.example/macro")
    monkeypatch.setenv("MOSS_CHOICE_USERNAME", "demo-user")
    monkeypatch.setenv("MOSS_CHOICE_PASSWORD", "demo-pass")
    monkeypatch.setenv("MOSS_CHOICE_MACRO_SERIES_JSON", _choice_series_json())
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.choice_macro")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_macro",
            "backend/app/tasks/choice_macro.py",
        )
    macro_schema_module = load_module(
        "backend.app.schemas.macro_vendor",
        "backend/app/schemas/macro_vendor.py",
    )
    governance_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    monkeypatch.setattr(
        task_module.VendorAdapter,
        "fetch_macro_snapshot",
        lambda self, series, timeout_seconds=10.0, request_options="": macro_schema_module.ChoiceMacroSnapshot(
            vendor_name="choice",
            vendor_version="vv_choice_20260409T140000Z",
            captured_at="2026-04-09T14:00:00Z",
            series=[
                macro_schema_module.ChoiceMacroPoint(
                    series_id="cn_cpi_yoy",
                    series_name="CN CPI YoY",
                    vendor_series_code="EDB_CPI_YOY",
                    vendor_name="choice",
                    trade_date="2026-04-09",
                    value_numeric=0.7,
                    frequency="daily",
                    unit="pct",
                    vendor_version="vv_choice_20260409T140000Z",
                ),
                macro_schema_module.ChoiceMacroPoint(
                    series_id="cn_repo_7d",
                    series_name="CN Repo 7D",
                    vendor_series_code="EDB_REPO_7D",
                    vendor_name="choice",
                    trade_date="2026-04-09",
                    value_numeric=1.82,
                    frequency="daily",
                    unit="pct",
                    vendor_version="vv_choice_20260409T140000Z",
                ),
            ],
            raw_payload=_choice_gateway_payload(),
        ),
    )

    payload = task_module.refresh_choice_macro_snapshot.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
    )

    assert payload["status"] == "completed"
    assert payload["vendor_version"] == "vv_choice_20260409T140000Z"
    assert payload["series_count"] == 2

    repo = governance_module.GovernanceRepository(base_dir=tmp_path / "governance")
    manifests = repo.read_all(governance_module.VENDOR_SNAPSHOT_MANIFEST_STREAM)
    versions = repo.read_all(governance_module.VENDOR_VERSION_REGISTRY_STREAM)
    assert manifests[-1]["vendor_version"] == "vv_choice_20260409T140000Z"
    assert manifests[-1]["capture_mode"] == "live"
    assert versions[-1]["vendor_version"] == "vv_choice_20260409T140000Z"

    conn = duckdb.connect(str(tmp_path / "moss.duckdb"), read_only=False)
    try:
        normalized_rows = conn.execute("select count(*) from choice_market_snapshot").fetchone()[0]
        fact_rows = conn.execute("select count(*) from fact_choice_macro_daily").fetchone()[0]
        catalog_rows = conn.execute("select count(*) from phase1_macro_vendor_catalog").fetchone()[0]
    finally:
        conn.close()

    assert normalized_rows == 2
    assert fact_rows == 2
    assert catalog_rows == 2
    get_settings.cache_clear()


def test_choice_macro_refresh_does_not_expose_partial_vendor_lineage_when_success_append_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", "")
    monkeypatch.setenv("MOSS_CHOICE_MACRO_URL", "https://choice.example/macro")
    monkeypatch.setenv("MOSS_CHOICE_USERNAME", "demo-user")
    monkeypatch.setenv("MOSS_CHOICE_PASSWORD", "demo-pass")
    monkeypatch.setenv("MOSS_CHOICE_MACRO_SERIES_JSON", _choice_series_json())
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.choice_macro")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_macro",
            "backend/app/tasks/choice_macro.py",
        )
    macro_schema_module = load_module(
        "backend.app.schemas.macro_vendor",
        "backend/app/schemas/macro_vendor.py",
    )
    governance_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    monkeypatch.setattr(
        task_module.VendorAdapter,
        "fetch_macro_snapshot",
        lambda self, series, timeout_seconds=10.0, request_options="": macro_schema_module.ChoiceMacroSnapshot(
            vendor_name="choice",
            vendor_version="vv_choice_20260409T140000Z",
            captured_at="2026-04-09T14:00:00Z",
            series=[
                macro_schema_module.ChoiceMacroPoint(
                    series_id="cn_cpi_yoy",
                    series_name="CN CPI YoY",
                    vendor_series_code="EDB_CPI_YOY",
                    vendor_name="choice",
                    trade_date="2026-04-09",
                    value_numeric=0.7,
                    frequency="daily",
                    unit="pct",
                    vendor_version="vv_choice_20260409T140000Z",
                ),
            ],
            raw_payload=_choice_gateway_payload(),
        ),
    )

    def failing_append_many_atomic(self, records):
        raise RuntimeError("choice lineage append failed")

    monkeypatch.setattr(task_module.GovernanceRepository, "append_many_atomic", failing_append_many_atomic)

    with pytest.raises(RuntimeError, match="choice lineage append failed"):
        task_module.refresh_choice_macro_snapshot.fn(
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(tmp_path / "governance"),
        )

    repo = governance_module.GovernanceRepository(base_dir=tmp_path / "governance")
    manifests = repo.read_all(governance_module.VENDOR_SNAPSHOT_MANIFEST_STREAM)
    versions = repo.read_all(governance_module.VENDOR_VERSION_REGISTRY_STREAM)
    build_runs = repo.read_all(governance_module.CACHE_BUILD_RUN_STREAM)

    assert manifests == []
    assert versions == []
    assert build_runs[-1]["status"] == "failed"
    assert build_runs[-1]["vendor_version"] == "vv_choice_20260409T140000Z"
    assert repo.read_all(governance_module.CACHE_MANIFEST_STREAM) == []
    get_settings.cache_clear()


def test_choice_macro_surfaces_failed_run_append_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", "")
    monkeypatch.setenv("MOSS_CHOICE_MACRO_URL", "https://choice.example/macro")
    monkeypatch.setenv("MOSS_CHOICE_USERNAME", "demo-user")
    monkeypatch.setenv("MOSS_CHOICE_PASSWORD", "demo-pass")
    monkeypatch.setenv("MOSS_CHOICE_MACRO_SERIES_JSON", _choice_series_json())
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.choice_macro")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_macro",
            "backend/app/tasks/choice_macro.py",
        )

    monkeypatch.setattr(
        task_module,
        "load_choice_macro_batches",
        lambda settings: (_ for _ in ()).throw(RuntimeError("fetch failed before lineage")),
    )

    original_append = task_module.GovernanceRepository.append

    def failing_append(self, stream: str, payload: dict[str, object]):
        if stream == task_module.CACHE_BUILD_RUN_STREAM and payload["status"] == "failed":
            raise RuntimeError("failed build-run append failed")
        return original_append(self, stream, payload)

    monkeypatch.setattr(task_module.GovernanceRepository, "append", failing_append)

    with pytest.raises(RuntimeError, match="Failed to append failed choice_macro lineage"):
        task_module.refresh_choice_macro_snapshot.fn(
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(tmp_path / "governance"),
        )

    get_settings.cache_clear()


def test_choice_macro_latest_api_returns_real_fact_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", "")
    monkeypatch.setenv("MOSS_CHOICE_MACRO_URL", "https://choice.example/macro")
    monkeypatch.setenv("MOSS_CHOICE_USERNAME", "demo-user")
    monkeypatch.setenv("MOSS_CHOICE_PASSWORD", "demo-pass")
    monkeypatch.setenv("MOSS_CHOICE_MACRO_SERIES_JSON", _choice_series_json())
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.choice_macro")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_macro",
            "backend/app/tasks/choice_macro.py",
        )
    macro_schema_module = load_module(
        "backend.app.schemas.macro_vendor",
        "backend/app/schemas/macro_vendor.py",
    )
    monkeypatch.setattr(
        task_module.VendorAdapter,
        "fetch_macro_snapshot",
        lambda self, series, timeout_seconds=10.0, request_options="": macro_schema_module.ChoiceMacroSnapshot(
            vendor_name="choice",
            vendor_version="vv_choice_20260409T140000Z",
            captured_at="2026-04-09T14:00:00Z",
            series=[
                macro_schema_module.ChoiceMacroPoint(
                    series_id="cn_cpi_yoy",
                    series_name="CN CPI YoY",
                    vendor_series_code="EDB_CPI_YOY",
                    vendor_name="choice",
                    trade_date="2026-04-09",
                    value_numeric=0.7,
                    frequency="daily",
                    unit="pct",
                    vendor_version="vv_choice_20260409T140000Z",
                ),
                macro_schema_module.ChoiceMacroPoint(
                    series_id="cn_repo_7d",
                    series_name="CN Repo 7D",
                    vendor_series_code="EDB_REPO_7D",
                    vendor_name="choice",
                    trade_date="2026-04-09",
                    value_numeric=1.82,
                    frequency="daily",
                    unit="pct",
                    vendor_version="vv_choice_20260409T140000Z",
                ),
            ],
            raw_payload=_choice_gateway_payload(),
        ),
    )

    task_module.refresh_choice_macro_snapshot.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
    )

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)
    response = client.get("/ui/macro/choice-series/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "macro.choice.latest"
    assert payload["result_meta"]["vendor_version"] == "vv_choice_20260409T140000Z"
    assert [item["series_id"] for item in payload["result"]["series"]] == ["cn_cpi_yoy", "cn_repo_7d"]
    assert payload["result"]["series"][0]["trade_date"] == "2026-04-09"
    get_settings.cache_clear()


def test_choice_macro_latest_api_aggregates_vendor_lineage_across_distinct_batch_versions(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              (
                'cn_cpi_yoy',
                'CN CPI YoY',
                '2026-04-09',
                0.7,
                'monthly',
                'pct',
                'sv_choice_macro_20260409',
                'vv_choice_batch_b',
                'rv_choice_macro_thin_slice_v1',
                'ok',
                'choice_macro_refresh:2026-04-09T14:00:00Z'
              ),
              (
                'cn_repo_7d',
                'CN Repo 7D',
                '2026-04-09',
                1.82,
                'daily',
                'pct',
                'sv_choice_macro_20260409',
                'vv_choice_batch_a',
                'rv_choice_macro_thin_slice_v1',
                'ok',
                'choice_macro_refresh:2026-04-09T14:00:00Z'
              )
            """
        )
    finally:
        conn.close()

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)
    response = client.get("/ui/macro/choice-series/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "sv_choice_macro_20260409"
    assert payload["result_meta"]["vendor_version"] == "vv_choice_batch_a__vv_choice_batch_b"
    assert [item["vendor_version"] for item in payload["result"]["series"]] == [
        "vv_choice_batch_b",
        "vv_choice_batch_a",
    ]
    get_settings.cache_clear()


def test_choice_macro_latest_api_returns_warning_quality_flag_when_duckdb_has_no_fact_rows(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)
    response = client.get("/ui/macro/choice-series/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "macro.choice.latest"
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result_meta"]["vendor_version"] == "vv_none"
    assert payload["result"]["series"] == []
    get_settings.cache_clear()


def test_choice_adapter_parses_pandas_edb_result(monkeypatch):
    schema_module = load_module(
        "backend.app.schemas.macro_vendor",
        "backend/app/schemas/macro_vendor.py",
    )
    adapter_module = load_module(
        "backend.app.repositories.choice_adapter",
        "backend/app/repositories/choice_adapter.py",
    )

    frame = pd.DataFrame(
        {
            "DATES": ["2025/12/01", "2026/01/01"],
            "RESULT": [8.5, 8.8],
            "PUBLISHDATE": ["20260228", "20260331"],
        },
        index=["EMM00087117", "EMM00087117"],
    )
    frame.index.name = "CODES"

    class FakeChoiceClient:
        def start(self):
            return 0

        def edb(self, codes: list[str], options: str = ""):
            return frame

    monkeypatch.setattr(adapter_module, "ChoiceClient", lambda: FakeChoiceClient())

    configs = [
        schema_module.ChoiceMacroSeriesConfig(
            series_id="emm00087117",
            series_name="Demo EDB",
            vendor_series_code="EMM00087117",
            frequency="daily",
            unit="unknown",
        ),
    ]

    snapshot = adapter_module.VendorAdapter().fetch_macro_snapshot(configs)

    assert snapshot.vendor_version == "vv_choice_edb_20260101"
    assert len(snapshot.series) == 1
    assert snapshot.series[0].trade_date == "2026-01-01"
    assert snapshot.series[0].value_numeric == 8.8


def test_choice_macro_refresh_initializes_runtime_before_fetch(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", "")
    monkeypatch.setenv("MOSS_CHOICE_MACRO_SERIES_JSON", _choice_series_json())
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.choice_macro")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_macro",
            "backend/app/tasks/choice_macro.py",
        )
    macro_schema_module = load_module(
        "backend.app.schemas.macro_vendor",
        "backend/app/schemas/macro_vendor.py",
    )

    observed: dict[str, object] = {}
    monkeypatch.setattr(task_module, "_init_runtime", lambda: observed.setdefault("init_runtime", True))
    monkeypatch.setattr(
        task_module.VendorAdapter,
        "fetch_macro_snapshot",
        lambda self, series, timeout_seconds=10.0, request_options="": macro_schema_module.ChoiceMacroSnapshot(
            vendor_name="choice",
            vendor_version="vv_choice_20260409T140000Z",
            captured_at="2026-04-09T14:00:00Z",
            series=[],
            raw_payload={"vendor_version": "vv_choice_20260409T140000Z", "captured_at": "2026-04-09T14:00:00Z", "series": []},
        ),
    )

    payload = task_module.refresh_choice_macro_snapshot.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
    )

    assert observed["init_runtime"] is True
    assert payload["status"] == "completed"


def test_choice_macro_command_file_parser_preserves_batch_options_and_names(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.choice_macro")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_macro",
            "backend/app/tasks/choice_macro.py",
        )

    command_file = tmp_path / "choice_macro_commands.txt"
    command_file.write_text(
        "\n".join(
            [
                "# cmd1 EMM00000015 中国:GDP:现价, EMM00008445 工业增加值:当月同比",
                'data=c.edb("EMM00000015,EMM00008445", "IsLatest=0,StartDate=2026-04-09,EndDate=2026-04-09")',
                "# cmd2 EMM00087083 M1",
                'data=c.edb("EMM00087083", "IsLatest=0,StartDate=2026-04-09,EndDate=2026-04-09")',
            ]
        ),
        encoding="utf-8",
    )

    batches = task_module.load_choice_macro_batches_from_file(command_file)

    assert [batch.batch_id for batch in batches] == ["cmd1", "cmd2"]
    assert batches[0].request_options == "IsLatest=0,StartDate=2026-04-09,EndDate=2026-04-09"
    assert [item.vendor_series_code for item in batches[0].series] == ["EMM00000015", "EMM00008445"]
    assert batches[0].series[0].series_name == "中国:GDP:现价"
    assert batches[1].series[0].series_id == "EMM00087083"


def test_choice_macro_load_batches_prefers_structured_catalog(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_CHOICE_MACRO_SERIES_JSON", _choice_series_json())
    command_file = tmp_path / "choice_macro_commands.txt"
    command_file.write_text(
        "\n".join(
            [
                "# cmd1 RAW001 raw series",
                'data=c.edb("RAW001", "IsLatest=0,StartDate=2026-04-09,EndDate=2026-04-09")',
            ]
        ),
        encoding="utf-8",
    )
    catalog_file = tmp_path / "choice_macro_catalog.json"
    _write_choice_macro_catalog(catalog_file)
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", str(catalog_file))
    monkeypatch.setenv("MOSS_CHOICE_MACRO_COMMANDS_FILE", str(command_file))
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.choice_macro")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_macro",
            "backend/app/tasks/choice_macro.py",
        )

    batches = task_module.load_choice_macro_batches(get_settings())

    assert [batch.batch_id for batch in batches] == ["catalog_cmd1", "catalog_cmd2"]
    assert batches[0].catalog_version == "2026-04-10.choice-macro.v1"
    assert batches[0].request_options == "IsPublishDate=1,RowIndex=1,Ispandas=1"
    assert [item.vendor_series_code for item in batches[0].series] == ["EDB_CPI_YOY", "EDB_REPO_7D"]
    assert batches[0].series[0].theme == "inflation"
    assert batches[0].series[0].is_core is True
    assert batches[1].series[0].tags == ["china", "macro", "money_supply"]
    get_settings.cache_clear()


def test_choice_macro_load_batches_falls_back_to_command_file_when_catalog_missing(tmp_path, monkeypatch):
    command_file = tmp_path / "choice_macro_commands.txt"
    command_file.write_text(
        "\n".join(
            [
                "# cmd1 EMM00000015 GDP",
                'data=c.edb("EMM00000015", "IsLatest=0,StartDate=2026-04-09,EndDate=2026-04-09")',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", str(tmp_path / "missing_catalog.json"))
    monkeypatch.setenv("MOSS_CHOICE_MACRO_COMMANDS_FILE", str(command_file))
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.choice_macro")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_macro",
            "backend/app/tasks/choice_macro.py",
        )

    batches = task_module.load_choice_macro_batches(get_settings())

    assert [batch.batch_id for batch in batches] == ["cmd1"]
    assert batches[0].catalog_version is None
    assert batches[0].series[0].vendor_series_code == "EMM00000015"
    assert batches[0].series[0].theme == "unknown"
    get_settings.cache_clear()


def test_choice_macro_refresh_materializes_structured_catalog_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    catalog_file = tmp_path / "choice_macro_catalog.json"
    _write_choice_macro_catalog(catalog_file)
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", str(catalog_file))
    monkeypatch.setenv("MOSS_CHOICE_MACRO_COMMANDS_FILE", "")
    monkeypatch.setenv("MOSS_CHOICE_MACRO_SERIES_JSON", "[]")
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.choice_macro")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_macro",
            "backend/app/tasks/choice_macro.py",
        )
    macro_schema_module = load_module(
        "backend.app.schemas.macro_vendor",
        "backend/app/schemas/macro_vendor.py",
    )

    def fake_fetch(self, series, timeout_seconds=10.0, request_options: str = ""):
        return macro_schema_module.ChoiceMacroSnapshot(
            vendor_name="choice",
            vendor_version="vv_choice_20260409T140000Z",
            captured_at="2026-04-09T14:00:00Z",
            series=[
                macro_schema_module.ChoiceMacroPoint(
                    series_id=item.series_id,
                    series_name=item.series_name,
                    vendor_series_code=item.vendor_series_code,
                    vendor_name="choice",
                    trade_date="2026-04-09",
                    value_numeric=float(index + 1),
                    frequency=item.frequency,
                    unit=item.unit,
                    vendor_version="vv_choice_20260409T140000Z",
                )
                for index, item in enumerate(series)
            ],
            raw_payload=_choice_gateway_payload(),
        )

    monkeypatch.setattr(task_module.VendorAdapter, "fetch_macro_snapshot", fake_fetch)

    payload = task_module.refresh_choice_macro_snapshot.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
    )

    assert payload["status"] == "completed"
    assert payload["series_count"] == 3

    conn = duckdb.connect(str(tmp_path / "moss.duckdb"), read_only=False)
    try:
        rows = conn.execute(
            """
            select
              series_id,
              vendor_series_code,
              batch_id,
              catalog_version,
              theme,
              is_core,
              tags_json,
              request_options
            from phase1_macro_vendor_catalog
            order by series_id
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        (
            "cn_cpi_yoy",
            "EDB_CPI_YOY",
            "catalog_cmd1",
            "2026-04-10.choice-macro.v1",
            "inflation",
            True,
            '["china","macro","inflation"]',
            "IsPublishDate=1,RowIndex=1,Ispandas=1",
        ),
        (
            "cn_m2_yoy",
            "EDB_M2_YOY",
            "catalog_cmd2",
            "2026-04-10.choice-macro.v1",
            "money_supply",
            False,
            '["china","macro","money_supply"]',
            "IsLatest=0,StartDate=2026-04-09,EndDate=2026-04-09",
        ),
        (
            "cn_repo_7d",
            "EDB_REPO_7D",
            "catalog_cmd1",
            "2026-04-10.choice-macro.v1",
            "liquidity",
            True,
            '["china","rates","liquidity"]',
            "IsPublishDate=1,RowIndex=1,Ispandas=1",
        ),
    ]
    get_settings.cache_clear()


def test_choice_macro_refresh_supports_multi_batch_command_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", str(tmp_path / "missing_catalog.json"))
    get_settings.cache_clear()

    command_file = tmp_path / "choice_macro_commands.txt"
    command_file.write_text(
        "\n".join(
            [
                "# cmd1 EMM00000015 中国:GDP:现价, EMM00008445 工业增加值:当月同比",
                'data=c.edb("EMM00000015,EMM00008445", "IsLatest=0,StartDate=2026-04-09,EndDate=2026-04-09")',
                "# cmd2 EMM00087083 M1",
                'data=c.edb("EMM00087083", "IsLatest=0,StartDate=2026-04-09,EndDate=2026-04-09")',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_CHOICE_MACRO_COMMANDS_FILE", str(command_file))

    task_module = sys.modules.get("backend.app.tasks.choice_macro")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_macro",
            "backend/app/tasks/choice_macro.py",
        )
    macro_schema_module = load_module(
        "backend.app.schemas.macro_vendor",
        "backend/app/schemas/macro_vendor.py",
    )

    observed: list[tuple[list[str], str]] = []

    def fake_fetch(self, series, timeout_seconds=10.0, request_options: str = ""):
        observed.append(([item.vendor_series_code for item in series], request_options))
        return macro_schema_module.ChoiceMacroSnapshot(
            vendor_name="choice",
            vendor_version="vv_choice_20260409T140000Z",
            captured_at="2026-04-09T14:00:00Z",
            series=[
                macro_schema_module.ChoiceMacroPoint(
                    series_id=item.series_id,
                    series_name=item.series_name,
                    vendor_series_code=item.vendor_series_code,
                    vendor_name="choice",
                    trade_date="2026-04-09",
                    value_numeric=float(index + 1),
                    frequency=item.frequency,
                    unit=item.unit,
                    vendor_version="vv_choice_20260409T140000Z",
                )
                for index, item in enumerate(series)
            ],
            raw_payload={
                "vendor_version": "vv_choice_20260409T140000Z",
                "captured_at": "2026-04-09T14:00:00Z",
                "series": [],
            },
        )

    monkeypatch.setattr(task_module.VendorAdapter, "fetch_macro_snapshot", fake_fetch)

    payload = task_module.refresh_choice_macro_snapshot.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
    )

    assert payload["status"] == "completed"
    assert payload["series_count"] == 3
    assert len(observed) == 2
    assert observed[0][0] == ["EMM00000015", "EMM00008445"]
    assert observed[1][0] == ["EMM00087083"]


def test_choice_macro_refresh_skips_no_data_batch_and_keeps_successful_batch(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", str(tmp_path / "missing_catalog.json"))
    get_settings.cache_clear()

    command_file = tmp_path / "choice_macro_commands.txt"
    command_file.write_text(
        "\n".join(
            [
                "# cmd1 EMM00000015 中国:GDP:现价",
                'data=c.edb("EMM00000015", "IsLatest=0,StartDate=2026-04-09,EndDate=2026-04-09")',
                "# cmd2 EMM00087083 M1",
                'data=c.edb("EMM00087083", "IsLatest=0,StartDate=2026-04-09,EndDate=2026-04-09")',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_CHOICE_MACRO_COMMANDS_FILE", str(command_file))

    task_module = sys.modules.get("backend.app.tasks.choice_macro")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_macro",
            "backend/app/tasks/choice_macro.py",
        )
    macro_schema_module = load_module(
        "backend.app.schemas.macro_vendor",
        "backend/app/schemas/macro_vendor.py",
    )

    def fake_fetch(self, series, timeout_seconds=10.0, request_options: str = ""):
        if series[0].vendor_series_code == "EMM00087083":
            raise RuntimeError("no data")
        return macro_schema_module.ChoiceMacroSnapshot(
            vendor_name="choice",
            vendor_version="vv_choice_20260409T140000Z",
            captured_at="2026-04-09T14:00:00Z",
            series=[
                macro_schema_module.ChoiceMacroPoint(
                    series_id=series[0].series_id,
                    series_name=series[0].series_name,
                    vendor_series_code=series[0].vendor_series_code,
                    vendor_name="choice",
                    trade_date="2026-04-09",
                    value_numeric=1.0,
                    frequency=series[0].frequency,
                    unit=series[0].unit,
                    vendor_version="vv_choice_20260409T140000Z",
                )
            ],
            raw_payload={"vendor_version": "vv_choice_20260409T140000Z", "captured_at": "2026-04-09T14:00:00Z", "series": []},
        )

    monkeypatch.setattr(task_module.VendorAdapter, "fetch_macro_snapshot", fake_fetch)

    payload = task_module.refresh_choice_macro_snapshot.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
    )

    assert payload["status"] == "completed"
    assert payload["series_count"] == 1
