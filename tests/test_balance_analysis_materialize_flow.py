from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal

import duckdb
import pytest

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def _load_modules():
    repo_mod = sys.modules.get("backend.app.repositories.balance_analysis_repo")
    if repo_mod is None:
        repo_mod = load_module(
            "backend.app.repositories.balance_analysis_repo",
            "backend/app/repositories/balance_analysis_repo.py",
        )
    task_mod = sys.modules.get("backend.app.tasks.balance_analysis_materialize")
    if task_mod is None:
        task_mod = load_module(
            "backend.app.tasks.balance_analysis_materialize",
            "backend/app/tasks/balance_analysis_materialize.py",
        )
    return repo_mod, task_mod


def _load_fx_module():
    fx_mod = sys.modules.get("backend.app.tasks.fx_mid_materialize")
    if fx_mod is None:
        fx_mod = load_module(
            "backend.app.tasks.fx_mid_materialize",
            "backend/app/tasks/fx_mid_materialize.py",
        )
    return fx_mod


def _patch_usd_only_formal_fx_candidates(fx_mod, monkeypatch):
    monkeypatch.setattr(
        fx_mod,
        "_load_formal_fx_candidates",
        lambda: [
            fx_mod.FormalFxCandidate(
                series_id="EMM00058124",
                series_name="中间价:美元兑人民币",
                vendor_series_code="EMM00058124",
                base_currency="USD",
                quote_currency="CNY",
                invert_result=False,
            )
        ],
    )


def _patch_skip_fx_refresh(task_mod, monkeypatch):
    monkeypatch.setattr(
        task_mod.materialize_fx_mid_for_report_date,
        "fn",
        lambda **_kwargs: {
            "status": "completed",
            "row_count": 0,
            "source_kind": "stub",
        },
    )


def _seed_snapshot_and_fx_tables(duckdb_path: str) -> None:
    snapshot_mod = sys.modules.get("backend.app.repositories.snapshot_repo")
    if snapshot_mod is None:
        snapshot_mod = load_module(
            "backend.app.repositories.snapshot_repo",
            "backend/app/repositories/snapshot_repo.py",
        )

    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        snapshot_mod.ensure_snapshot_tables(conn)
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, issuer_name, industry_name, rating,
              currency_code, face_value_native, market_value_native, amortized_cost_native,
              accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
              overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "240001.IB",
                "债券A",
                "组合A",
                "CC100",
                "可供出售债券",
                "债券类",
                "国债",
                "发行人A",
                "主权",
                "AAA",
                "USD",
                Decimal("100"),
                Decimal("100"),
                Decimal("90"),
                Decimal("5"),
                Decimal("0.025"),
                Decimal("0.03"),
                "2027-12-31",
                None,
                0,
                False,
                "固定",
                "sv-z-1",
                "rv-snap-1",
                "ib-z-1",
                "trace-z-1",
            ],
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot (
              report_date, position_id, product_type, position_side, counterparty_name,
              account_type, special_account_type, core_customer_type, currency_code,
              principal_native, accrued_interest_native, funding_cost_rate, maturity_date,
              pledged_bond_code, source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "pos-1",
                "持有至到期同业存单",
                "liability",
                "银行A",
                "负债账户",
                "一般",
                "股份制银行",
                "USD",
                Decimal("10"),
                Decimal("2"),
                Decimal("0.015"),
                "2026-06-30",
                None,
                "sv-t-1",
                "rv-snap-1",
                "ib-t-1",
                "trace-t-1",
            ],
        )
        conn.execute(
            """
            insert into fx_daily_mid (
              trade_date, base_currency, quote_currency, mid_rate,
              source_name, is_business_day, is_carry_forward, source_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-31",
                "USD",
                "CNY",
                Decimal("7.2"),
                "CFETS",
                True,
                False,
                "sv-fx-1",
            ],
        )
    finally:
        conn.close()


def test_choice_fx_fetch_accepts_legacy_choice_client_signature(monkeypatch):
    fx_mod = _load_fx_module()

    class _ChoiceResult:
        Codes = ["EMM00058124"]
        Dates = ["2025-12-31"]
        Data = {"EMM00058124": [[Decimal("7.20")]]}

    class _LegacyChoiceClient:
        def __init__(self):
            self.calls: list[tuple[list[str], str]] = []

        def edb(self, codes, options=""):
            self.calls.append((list(codes), options))
            return _ChoiceResult()

    legacy_client = _LegacyChoiceClient()
    monkeypatch.setattr(fx_mod, "ChoiceClient", lambda: legacy_client)

    rows = fx_mod._fetch_choice_fx_mid_rows_for_report_date(
        "2025-12-31",
        candidates=[
            fx_mod.FormalFxCandidate(
                series_id="EMM00058124",
                series_name="中间价:美元兑人民币",
                vendor_series_code="EMM00058124",
                base_currency="USD",
                quote_currency="CNY",
                invert_result=False,
            )
        ],
    )

    assert rows == [
        (
            "2025-12-31",
            "USD",
            "CNY",
            Decimal("7.20"),
            fx_mod.CHOICE_SOURCE_NAME,
            True,
            False,
            rows[0][7],
            "choice",
            rows[0][9],
            "EMM00058124",
            "2025-12-31",
        )
    ]
    assert legacy_client.calls == [
        (
            ["EMM00058124"],
            "IsLatest=0,StartDate=2025-12-31,EndDate=2025-12-31,RECVtimeout=5",
        )
    ]


def test_balance_analysis_materialize_writes_formal_fact_tables_and_governance_records(tmp_path, monkeypatch):
    repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))
    _patch_skip_fx_refresh(task_mod, monkeypatch)

    payload = task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["report_date"] == "2025-12-31"
    assert payload["zqtz_rows"] == 2
    assert payload["tyw_rows"] == 2

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        zqtz_rows = conn.execute(
            """
            select report_date, instrument_code, invest_type_std, accounting_basis,
                   position_scope, currency_basis, market_value_amount, source_version
            from fact_formal_zqtz_balance_daily
            order by currency_basis
            """
        ).fetchall()
        tyw_rows = conn.execute(
            """
            select report_date, position_id, invest_type_std, accounting_basis,
                   position_scope, currency_basis, principal_amount, source_version
            from fact_formal_tyw_balance_daily
            order by currency_basis
            """
        ).fetchall()
    finally:
        conn.close()

    assert zqtz_rows == [
        ("2025-12-31", "240001.IB", "A", "FVOCI", "asset", "CNY", Decimal("720.00000000"), "sv-z-1"),
        ("2025-12-31", "240001.IB", "A", "FVOCI", "asset", "native", Decimal("100.00000000"), "sv-z-1"),
    ]
    assert tyw_rows == [
        ("2025-12-31", "pos-1", "H", "AC", "liability", "CNY", Decimal("72.00000000"), "sv-t-1"),
        ("2025-12-31", "pos-1", "H", "AC", "liability", "native", Decimal("10.00000000"), "sv-t-1"),
    ]

    repo = repo_mod.BalanceAnalysisRepository(str(duckdb_path))
    assert repo.list_report_dates() == ["2025-12-31"]

    build_runs = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifests = [
        json.loads(line)
        for line in (governance_dir / "cache_manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert build_runs[0]["status"] == "queued"
    assert build_runs[0]["queued_at"]
    assert build_runs[1]["status"] == "running"
    assert build_runs[1]["started_at"]
    assert build_runs[-1]["status"] == "completed"
    assert build_runs[-1]["finished_at"]
    assert build_runs[-1]["cache_key"] == task_mod.CACHE_KEY
    assert manifests[-1]["cache_key"] == task_mod.CACHE_KEY
    assert manifests[-1]["rule_version"] == task_mod.RULE_VERSION
    assert manifests[-1]["module_name"] == "balance_analysis"


def test_balance_analysis_materialize_fails_when_required_fx_rate_is_missing(tmp_path):
    _repo_mod, task_mod = _load_modules()
    fx_mod = _load_fx_module()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("delete from fx_daily_mid")
    finally:
        conn.close()

    # Use controlled vendor failures instead of live Choice calls.
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MOSS_FX_MID_CSV_PATH", "")
        monkeypatch.setenv("MOSS_FX_OFFICIAL_SOURCE_PATH", "")
        _patch_usd_only_formal_fx_candidates(fx_mod, monkeypatch)
        monkeypatch.setattr(
            fx_mod,
            "ChoiceClient",
            lambda: type(
                "FailingChoiceClient",
                (),
                {"edb": lambda self, codes, options="", **_kwargs: (_ for _ in ()).throw(RuntimeError("choice unavailable"))},
            )(),
        )
        monkeypatch.setattr(
            fx_mod,
            "AkShareVendorAdapter",
            lambda: type("FailingAkShareVendor", (), {"fetch_fx_mid_snapshot": lambda self, **_kwargs: (_ for _ in ()).throw(RuntimeError("akshare unavailable"))})(),
        )
        with pytest.raises(ValueError, match="Choice failed: choice unavailable"):
            task_mod.materialize_balance_analysis_facts.fn(
                report_date="2025-12-31",
                duckdb_path=str(duckdb_path),
                governance_dir=str(governance_dir),
            )
    finally:
        monkeypatch.undo()


def test_balance_analysis_materialize_preserves_computed_lineage_when_write_fails(tmp_path, monkeypatch):
    repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))
    _patch_skip_fx_refresh(task_mod, monkeypatch)

    def _fail_replace(self, **_kwargs):
        raise RuntimeError("synthetic write failure")

    monkeypatch.setattr(
        repo_mod.BalanceAnalysisRepository,
        "replace_formal_balance_rows",
        _fail_replace,
    )

    with pytest.raises(RuntimeError, match="synthetic write failure"):
        task_mod.materialize_balance_analysis_facts.fn(
            report_date="2025-12-31",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )


def test_balance_analysis_materialize_allows_missing_family_when_no_manifest_exists_for_that_date(tmp_path):
    repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    fx_csv_path = tmp_path / "fx_mid.csv"
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("delete from tyw_interbank_daily_snapshot")
        conn.execute("drop table fx_daily_mid")
    finally:
        conn.close()

    fx_csv_path.write_text(
        "\n".join(
            [
                "trade_date,base_currency,quote_currency,mid_rate,source_name,is_business_day,is_carry_forward",
                "2025-12-31,USD,CNY,7.20,CFETS,true,false",
            ]
        ),
        encoding="utf-8",
    )

    payload = task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        ingest_batch_id="ib-z-only",
        fx_source_path=str(fx_csv_path),
    )

    assert payload["status"] == "completed"
    assert payload["zqtz_rows"] == 2
    assert payload["tyw_rows"] == 0

    repo = repo_mod.BalanceAnalysisRepository(str(duckdb_path))
    zqtz_rows = repo.fetch_formal_zqtz_rows(
        report_date="2025-12-31",
        position_scope="asset",
        currency_basis="native",
    )
    tyw_rows = repo.fetch_formal_tyw_rows(
        report_date="2025-12-31",
        position_scope="liability",
        currency_basis="native",
    )

    assert len(zqtz_rows) == 1
    assert tyw_rows == []


def test_balance_analysis_materialize_migrates_old_formal_zqtz_schema(tmp_path, monkeypatch):
    repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))
    _patch_skip_fx_refresh(task_mod, monkeypatch)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("drop table if exists fact_formal_zqtz_balance_daily")
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              instrument_code varchar,
              instrument_name varchar,
              portfolio_name varchar,
              cost_center varchar,
              asset_class varchar,
              bond_type varchar,
              issuer_name varchar,
              industry_name varchar,
              rating varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              currency_code varchar,
              face_value_amount decimal(24, 8),
              market_value_amount decimal(24, 8),
              amortized_cost_amount decimal(24, 8),
              accrued_interest_amount decimal(24, 8),
              coupon_rate decimal(18, 8),
              ytm_value decimal(18, 8),
              maturity_date varchar,
              interest_mode varchar,
              is_issuance_like boolean,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
    finally:
        conn.close()

    payload = task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"

    repo = repo_mod.BalanceAnalysisRepository(str(duckdb_path))
    rows = repo.fetch_formal_zqtz_rows(
        report_date="2025-12-31",
        position_scope="asset",
        currency_basis="native",
    )
    assert rows
    assert rows[0]["account_category"] == "可供出售债券"

    build_runs = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert build_runs[-1]["status"] == "completed"
    assert build_runs[-1]["source_version"] == "sv-fx-1__sv-t-1__sv-z-1"


def test_balance_analysis_materialize_fails_when_only_prior_business_day_fx_exists(tmp_path):
    _repo_mod, task_mod = _load_modules()
    fx_mod = _load_fx_module()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("delete from fx_daily_mid where trade_date = '2025-12-31'")
        conn.execute(
            """
            insert into fx_daily_mid (
              trade_date, base_currency, quote_currency, mid_rate,
              source_name, is_business_day, is_carry_forward, source_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-30",
                "USD",
                "CNY",
                Decimal("7.1"),
                "CFETS",
                True,
                False,
                "sv-fx-prev",
            ],
        )
    finally:
        conn.close()

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MOSS_FX_MID_CSV_PATH", "")
        monkeypatch.setenv("MOSS_FX_OFFICIAL_SOURCE_PATH", "")
        _patch_usd_only_formal_fx_candidates(fx_mod, monkeypatch)
        monkeypatch.setattr(
            fx_mod,
            "ChoiceClient",
            lambda: type(
                "FailingChoiceClient",
                (),
                {"edb": lambda self, codes, options="", **_kwargs: (_ for _ in ()).throw(RuntimeError("choice unavailable"))},
            )(),
        )
        monkeypatch.setattr(
            fx_mod,
            "AkShareVendorAdapter",
            lambda: type("FailingAkShareVendor", (), {"fetch_fx_mid_snapshot": lambda self, **_kwargs: (_ for _ in ()).throw(RuntimeError("akshare unavailable"))})(),
        )
        with pytest.raises(ValueError, match="Choice failed: choice unavailable"):
            task_mod.materialize_balance_analysis_facts.fn(
                report_date="2025-12-31",
                duckdb_path=str(duckdb_path),
                governance_dir=str(governance_dir),
            )
    finally:
        monkeypatch.undo()


def test_balance_analysis_materialize_normalizes_snapshot_currency_labels_for_fx_lookup(tmp_path):
    repo_mod, task_mod = _load_modules()
    fx_mod = _load_fx_module()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("update zqtz_bond_daily_snapshot set currency_code = '美元'")
        conn.execute("update tyw_interbank_daily_snapshot set currency_code = '人民币'")
    finally:
        conn.close()

    class _ChoiceResult:
        Codes = ["EMM00058124"]
        Dates = ["2025-12-31"]
        Data = {"EMM00058124": [[Decimal("7.20")]]}

    class _FakeChoiceClient:
        def edb(self, codes, options="", **_kwargs):
            return _ChoiceResult()

    monkeypatch = pytest.MonkeyPatch()
    try:
        _patch_usd_only_formal_fx_candidates(fx_mod, monkeypatch)
        monkeypatch.setattr(fx_mod, "ChoiceClient", lambda: _FakeChoiceClient())

        payload = task_mod.materialize_balance_analysis_facts.fn(
            report_date="2025-12-31",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )
    finally:
        monkeypatch.undo()

    assert payload["status"] == "completed"

    repo = repo_mod.BalanceAnalysisRepository(str(duckdb_path))
    zqtz_rows = repo.fetch_formal_zqtz_rows(report_date="2025-12-31", position_scope="asset", currency_basis="CNY")
    tyw_rows = repo.fetch_formal_tyw_rows(report_date="2025-12-31", position_scope="liability", currency_basis="CNY")

    assert {row["currency_code"] for row in zqtz_rows} == {"USD"}
    assert {row["currency_code"] for row in tyw_rows} == {"CNY"}


def test_balance_analysis_materialize_auto_populates_fx_from_csv_when_table_is_missing(tmp_path, monkeypatch):
    _repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    csv_path = tmp_path / "fx_mid.csv"
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("drop table fx_daily_mid")
    finally:
        conn.close()

    csv_path.write_text(
        "\n".join(
            [
                "trade_date,base_currency,quote_currency,mid_rate,source_name,is_business_day,is_carry_forward",
                "2025-12-31,USD,CNY,7.20,CFETS,true,false",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_FX_MID_CSV_PATH", str(csv_path))
    get_settings.cache_clear()

    payload = task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["zqtz_rows"] == 2
    assert payload["tyw_rows"] == 2
    get_settings.cache_clear()


def test_balance_analysis_materialize_treats_cnx_as_identity_not_spot_fx(tmp_path):
    repo_mod, task_mod = _load_modules()
    fx_mod = _load_fx_module()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("update zqtz_bond_daily_snapshot set currency_code = '综本'")
    finally:
        conn.close()

    class _ChoiceResult:
        Codes = ["EMM00058124"]
        Dates = ["2025-12-31"]
        Data = {"EMM00058124": [[Decimal("7.20")]]}

    class _FakeChoiceClient:
        def edb(self, codes, options="", **_kwargs):
            return _ChoiceResult()

    monkeypatch = pytest.MonkeyPatch()
    try:
        _patch_usd_only_formal_fx_candidates(fx_mod, monkeypatch)
        monkeypatch.setattr(fx_mod, "ChoiceClient", lambda: _FakeChoiceClient())

        payload = task_mod.materialize_balance_analysis_facts.fn(
            report_date="2025-12-31",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )
    finally:
        monkeypatch.undo()

    assert payload["status"] == "completed"

    repo = repo_mod.BalanceAnalysisRepository(str(duckdb_path))
    rows = repo.fetch_formal_zqtz_rows(
        report_date="2025-12-31",
        position_scope="asset",
        currency_basis="CNY",
    )
    assert len(rows) == 1
    assert rows[0]["currency_code"] == "CNX"
    assert rows[0]["market_value_amount"] == Decimal("100.00000000")


def test_balance_analysis_materialize_does_not_autodiscover_fx_csv_from_data_input_root(tmp_path, monkeypatch):
    _repo_mod, task_mod = _load_modules()
    fx_mod = _load_fx_module()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    data_input_root = tmp_path / "data_input"
    fx_csv_path = data_input_root / "fx" / "fx_daily_mid.csv"
    fx_csv_path.parent.mkdir(parents=True, exist_ok=True)
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("drop table fx_daily_mid")
    finally:
        conn.close()

    fx_csv_path.write_text(
        "\n".join(
            [
                "trade_date,base_currency,quote_currency,mid_rate,source_name,is_business_day,is_carry_forward",
                "2025-12-31,USD,CNY,7.20,CFETS,true,false",
            ]
        ),
        encoding="utf-8",
    )

    class _FailingChoiceClient:
        def edb(self, codes, options="", **_kwargs):
            raise RuntimeError("choice unavailable")

    class _FailingAkShareVendor:
        def fetch_fx_mid_snapshot(self, **_kwargs):
            raise RuntimeError("akshare unavailable")

    monkeypatch.delenv("MOSS_FX_MID_CSV_PATH", raising=False)
    monkeypatch.delenv("MOSS_FX_OFFICIAL_SOURCE_PATH", raising=False)
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_input_root))
    _patch_usd_only_formal_fx_candidates(fx_mod, monkeypatch)
    monkeypatch.setattr(fx_mod, "ChoiceClient", lambda: _FailingChoiceClient())
    monkeypatch.setattr(fx_mod, "AkShareVendorAdapter", lambda: _FailingAkShareVendor())
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="Choice failed: choice unavailable"):
        task_mod.materialize_balance_analysis_facts.fn(
            report_date="2025-12-31",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )

    get_settings.cache_clear()


def test_balance_analysis_materialize_fails_closed_when_explicit_fx_path_is_missing_even_if_fallback_exists(
    tmp_path,
    monkeypatch,
):
    _repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    data_input_root = tmp_path / "data_input"
    fallback_csv = data_input_root / "fx" / "fx_daily_mid.csv"
    fallback_csv.parent.mkdir(parents=True, exist_ok=True)
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("drop table fx_daily_mid")
    finally:
        conn.close()

    fallback_csv.write_text(
        "\n".join(
            [
                "trade_date,base_currency,quote_currency,mid_rate,source_name,is_business_day,is_carry_forward",
                "2025-12-31,USD,CNY,7.20,CFETS,true,false",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MOSS_FX_MID_CSV_PATH", str(tmp_path / "missing.csv"))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_input_root))
    get_settings.cache_clear()

    with pytest.raises(FileNotFoundError):
        task_mod.materialize_balance_analysis_facts.fn(
            report_date="2025-12-31",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )

    get_settings.cache_clear()


def test_balance_analysis_materialize_prefers_official_fx_source_path_over_legacy_fx_csv_path(
    tmp_path,
    monkeypatch,
):
    _repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    official_csv = tmp_path / "official_fx_mid.csv"
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("drop table fx_daily_mid")
    finally:
        conn.close()

    official_csv.write_text(
        "\n".join(
            [
                "trade_date,base_currency,quote_currency,mid_rate,source_name,is_business_day,is_carry_forward",
                "2025-12-31,USD,CNY,7.20,CFETS,true,false",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MOSS_FX_OFFICIAL_SOURCE_PATH", str(official_csv))
    monkeypatch.setenv("MOSS_FX_MID_CSV_PATH", str(tmp_path / "missing.csv"))
    get_settings.cache_clear()

    payload = task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["zqtz_rows"] == 2
    assert payload["tyw_rows"] == 2
    get_settings.cache_clear()


def test_balance_analysis_materialize_accepts_explicit_data_root_and_fx_source_path_without_env(
    tmp_path,
    monkeypatch,
):
    _repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    data_input_root = tmp_path / "data_input"
    official_csv = data_input_root / "fx" / "fx_daily_mid.csv"
    official_csv.parent.mkdir(parents=True, exist_ok=True)
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("drop table fx_daily_mid")
    finally:
        conn.close()

    official_csv.write_text(
        "\n".join(
            [
                "trade_date,base_currency,quote_currency,mid_rate,source_name,is_business_day,is_carry_forward",
                "2025-12-31,USD,CNY,7.20,CFETS,true,false",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("MOSS_FX_OFFICIAL_SOURCE_PATH", raising=False)
    monkeypatch.delenv("MOSS_FX_MID_CSV_PATH", raising=False)
    monkeypatch.delenv("MOSS_DATA_INPUT_ROOT", raising=False)
    get_settings.cache_clear()

    payload = task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_input_root),
        fx_source_path=str(official_csv),
    )

    assert payload["status"] == "completed"
    assert payload["zqtz_rows"] == 2
    assert payload["tyw_rows"] == 2
    get_settings.cache_clear()


def test_balance_analysis_materialize_auto_populates_fx_from_choice_when_no_csv_exists(
    tmp_path,
    monkeypatch,
):
    _repo_mod, task_mod = _load_modules()
    fx_mod = _load_fx_module()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    data_input_root = tmp_path / "data_input"
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("drop table fx_daily_mid")
    finally:
        conn.close()

    class _ChoiceResult:
        Codes = ["EMM00058124"]
        Dates = ["2025-12-31"]
        Data = {"EMM00058124": [[Decimal("7.20")]]}

    class _FakeChoiceClient:
        def edb(self, codes, options="", **_kwargs):
            return _ChoiceResult()

    _patch_usd_only_formal_fx_candidates(fx_mod, monkeypatch)
    monkeypatch.delenv("MOSS_FX_OFFICIAL_SOURCE_PATH", raising=False)
    monkeypatch.delenv("MOSS_FX_MID_CSV_PATH", raising=False)
    monkeypatch.setattr(fx_mod, "ChoiceClient", lambda: _FakeChoiceClient())
    get_settings.cache_clear()

    payload = task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_input_root),
    )

    assert payload["status"] == "completed"
    assert payload["zqtz_rows"] == 2
    assert payload["tyw_rows"] == 2
    get_settings.cache_clear()


def test_balance_analysis_materialize_marks_choice_fx_carry_forward_when_prior_business_day_is_used(
    tmp_path,
    monkeypatch,
):
    _repo_mod, task_mod = _load_modules()
    fx_mod = _load_fx_module()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    data_input_root = tmp_path / "data_input"
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("drop table fx_daily_mid")
    finally:
        conn.close()

    class _ChoiceResult:
        Codes = ["EMM00058124"]
        Dates = ["2025-12-30"]
        Data = {"EMM00058124": [[Decimal("7.10")]]}

    class _FakeChoiceClient:
        def __init__(self):
            self.calls: list[str] = []

        def edb(self, codes, options="", **_kwargs):
            self.calls.append(options)
            if "StartDate=2025-12-31" in options:
                return type("EmptyChoiceResult", (), {"Codes": [], "Dates": [], "Data": {}})()
            return _ChoiceResult()

    fake_client = _FakeChoiceClient()

    _patch_usd_only_formal_fx_candidates(fx_mod, monkeypatch)
    monkeypatch.delenv("MOSS_FX_OFFICIAL_SOURCE_PATH", raising=False)
    monkeypatch.delenv("MOSS_FX_MID_CSV_PATH", raising=False)
    monkeypatch.setattr(fx_mod, "ChoiceClient", lambda: fake_client)
    get_settings.cache_clear()

    payload = task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_input_root),
    )

    assert payload["status"] == "completed"

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select trade_date, mid_rate, is_business_day, is_carry_forward
            from fx_daily_mid
            where trade_date = '2025-12-31'
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [(date(2025, 12, 31), Decimal("7.10000000"), False, True)]
    assert any("StartDate=2025-12-31" in call for call in fake_client.calls)
    assert any("StartDate=2025-12-30" in call for call in fake_client.calls)
    get_settings.cache_clear()


def test_balance_analysis_materialize_scopes_snapshot_rows_to_requested_ingest_batch_id(
    tmp_path,
    monkeypatch,
):
    repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))
    _patch_skip_fx_refresh(task_mod, monkeypatch)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("update zqtz_bond_daily_snapshot set ingest_batch_id = 'ib-current'")
        conn.execute("update tyw_interbank_daily_snapshot set ingest_batch_id = 'ib-current'")
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, issuer_name, industry_name, rating,
              currency_code, face_value_native, market_value_native, amortized_cost_native,
              accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
              overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "240099.IB",
                "债券旧批次",
                "组合旧",
                "CC999",
                "可供出售债券",
                "债券类",
                "国债",
                "发行人旧",
                "主权",
                "AAA",
                "USD",
                Decimal("50"),
                Decimal("50"),
                Decimal("45"),
                Decimal("2"),
                Decimal("0.020"),
                Decimal("0.025"),
                "2027-12-31",
                None,
                0,
                False,
                "固定",
                "sv-z-old",
                "rv-snap-1",
                "ib-old",
                "trace-z-old",
            ],
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot (
              report_date, position_id, product_type, position_side, counterparty_name,
              account_type, special_account_type, core_customer_type, currency_code,
              principal_native, accrued_interest_native, funding_cost_rate, maturity_date,
              pledged_bond_code, source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "pos-old",
                "持有至到期同业存单",
                "liability",
                "银行旧",
                "负债账户",
                "一般",
                "股份制银行",
                "USD",
                Decimal("8"),
                Decimal("1"),
                Decimal("0.010"),
                "2026-05-31",
                None,
                "sv-t-old",
                "rv-snap-1",
                "ib-old",
                "trace-t-old",
            ],
        )
    finally:
        conn.close()

    payload = task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        ingest_batch_id="ib-current",
    )

    assert payload["status"] == "completed"
    assert payload["zqtz_rows"] == 2
    assert payload["tyw_rows"] == 2

    repo = repo_mod.BalanceAnalysisRepository(str(duckdb_path))
    zqtz_rows = repo.fetch_formal_zqtz_rows(
        report_date="2025-12-31",
        position_scope="asset",
        currency_basis="CNY",
    )
    tyw_rows = repo.fetch_formal_tyw_rows(
        report_date="2025-12-31",
        position_scope="liability",
        currency_basis="CNY",
    )

    assert {row["ingest_batch_id"] for row in zqtz_rows} == {"ib-current"}
    assert {row["ingest_batch_id"] for row in tyw_rows} == {"ib-current"}
    assert {row["source_version"] for row in zqtz_rows} == {"sv-z-1"}
    assert {row["source_version"] for row in tyw_rows} == {"sv-t-1"}


def test_balance_analysis_materialize_uses_latest_manifest_batches_when_ingest_batch_id_is_omitted(
    tmp_path,
    monkeypatch,
):
    repo_mod, task_mod = _load_modules()
    governance_repo_mod = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )
    manifest_repo_mod = load_module(
        "backend.app.repositories.source_manifest_repo",
        "backend/app/repositories/source_manifest_repo.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))
    _patch_skip_fx_refresh(task_mod, monkeypatch)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("update zqtz_bond_daily_snapshot set ingest_batch_id = 'ib-current-z'")
        conn.execute("update tyw_interbank_daily_snapshot set ingest_batch_id = 'ib-current-t'")
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, issuer_name, industry_name, rating,
              currency_code, face_value_native, market_value_native, amortized_cost_native,
              accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
              overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "240099.IB",
                "债券旧批次",
                "组合旧",
                "CC999",
                "可供出售债券",
                "债券类",
                "国债",
                "发行人旧",
                "主权",
                "AAA",
                "USD",
                Decimal("50"),
                Decimal("50"),
                Decimal("45"),
                Decimal("2"),
                Decimal("0.020"),
                Decimal("0.025"),
                "2027-12-31",
                None,
                0,
                False,
                "固定",
                "sv-z-old",
                "rv-snap-1",
                "ib-old-z",
                "trace-z-old",
            ],
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot (
              report_date, position_id, product_type, position_side, counterparty_name,
              account_type, special_account_type, core_customer_type, currency_code,
              principal_native, accrued_interest_native, funding_cost_rate, maturity_date,
              pledged_bond_code, source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "pos-old",
                "持有至到期同业存单",
                "liability",
                "银行旧",
                "负债账户",
                "一般",
                "股份制银行",
                "USD",
                Decimal("8"),
                Decimal("1"),
                Decimal("0.010"),
                "2026-05-31",
                None,
                "sv-t-old",
                "rv-snap-1",
                "ib-old-t",
                "trace-t-old",
            ],
        )
    finally:
        conn.close()

    manifest_repo = manifest_repo_mod.SourceManifestRepository(
        governance_repo=governance_repo_mod.GovernanceRepository(base_dir=governance_dir),
    )
    manifest_repo.add_many(
        [
            {
                "source_family": "zqtz",
                "report_date": "2025-12-31",
                "source_file": "ZQTZSHOW-old.xls",
                "source_version": "sv-z-old",
                "ingest_batch_id": "ib-old-z",
                "archived_path": "/archive/zqtz/old.xls",
            },
            {
                "source_family": "tyw",
                "report_date": "2025-12-31",
                "source_file": "TYWLSHOW-old.xls",
                "source_version": "sv-t-old",
                "ingest_batch_id": "ib-old-t",
                "archived_path": "/archive/tyw/old.xls",
            },
        ]
    )
    manifest_repo.add_many(
        [
            {
                "source_family": "zqtz",
                "report_date": "2025-12-31",
                "source_file": "ZQTZSHOW-current.xls",
                "source_version": "sv-z-1",
                "ingest_batch_id": "ib-current-z",
                "archived_path": "/archive/zqtz/current.xls",
            },
            {
                "source_family": "tyw",
                "report_date": "2025-12-31",
                "source_file": "TYWLSHOW-current.xls",
                "source_version": "sv-t-1",
                "ingest_batch_id": "ib-current-t",
                "archived_path": "/archive/tyw/current.xls",
            },
        ]
    )

    payload = task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["zqtz_rows"] == 2
    assert payload["tyw_rows"] == 2

    repo = repo_mod.BalanceAnalysisRepository(str(duckdb_path))
    zqtz_rows = repo.fetch_formal_zqtz_rows(
        report_date="2025-12-31",
        position_scope="asset",
        currency_basis="CNY",
    )
    tyw_rows = repo.fetch_formal_tyw_rows(
        report_date="2025-12-31",
        position_scope="liability",
        currency_basis="CNY",
    )

    assert {row["ingest_batch_id"] for row in zqtz_rows} == {"ib-current-z"}
    assert {row["ingest_batch_id"] for row in tyw_rows} == {"ib-current-t"}
    assert {row["source_version"] for row in zqtz_rows} == {"sv-z-1"}
    assert {row["source_version"] for row in tyw_rows} == {"sv-t-1"}


def test_balance_analysis_materialize_fails_closed_when_multiple_snapshot_batches_exist_without_manifest_or_explicit_batch(
    tmp_path,
    monkeypatch,
):
    _repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))
    _patch_skip_fx_refresh(task_mod, monkeypatch)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("update zqtz_bond_daily_snapshot set ingest_batch_id = 'ib-current-z'")
        conn.execute("update tyw_interbank_daily_snapshot set ingest_batch_id = 'ib-current-t'")
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, issuer_name, industry_name, rating,
              currency_code, face_value_native, market_value_native, amortized_cost_native,
              accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
              overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "240199.IB",
                "债券歧义批次",
                "组合歧义",
                "CC888",
                "可供出售债券",
                "债券类",
                "国债",
                "发行人歧义",
                "主权",
                "AAA",
                "USD",
                Decimal("40"),
                Decimal("40"),
                Decimal("36"),
                Decimal("1"),
                Decimal("0.018"),
                Decimal("0.022"),
                "2027-10-31",
                None,
                0,
                False,
                "固定",
                "sv-z-ambiguous",
                "rv-snap-1",
                "ib-old-z",
                "trace-z-ambiguous",
            ],
        )
    finally:
        conn.close()

    with pytest.raises(ValueError, match="explicit ingest_batch_id required"):
        task_mod.materialize_balance_analysis_facts.fn(
            report_date="2025-12-31",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )


def test_balance_analysis_materialize_fails_closed_when_latest_manifest_batch_has_no_snapshot_rows(
    tmp_path,
    monkeypatch,
):
    _repo_mod, task_mod = _load_modules()
    governance_repo_mod = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )
    manifest_repo_mod = load_module(
        "backend.app.repositories.source_manifest_repo",
        "backend/app/repositories/source_manifest_repo.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))
    _patch_skip_fx_refresh(task_mod, monkeypatch)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("update zqtz_bond_daily_snapshot set ingest_batch_id = 'ib-current-z'")
        conn.execute("update tyw_interbank_daily_snapshot set ingest_batch_id = 'ib-current-t'")
    finally:
        conn.close()

    manifest_repo = manifest_repo_mod.SourceManifestRepository(
        governance_repo=governance_repo_mod.GovernanceRepository(base_dir=governance_dir),
    )
    manifest_repo.add_many(
        [
            {
                "source_family": "zqtz",
                "report_date": "2025-12-31",
                "source_file": "ZQTZSHOW-current.xls",
                "source_version": "sv-z-1",
                "ingest_batch_id": "ib-current-z",
                "archived_path": "/archive/zqtz/current.xls",
            },
            {
                "source_family": "tyw",
                "report_date": "2025-12-31",
                "source_file": "TYWLSHOW-current.xls",
                "source_version": "sv-t-1",
                "ingest_batch_id": "ib-current-t",
                "archived_path": "/archive/tyw/current.xls",
            },
        ]
    )
    manifest_repo.add_many(
        [
            {
                "source_family": "zqtz",
                "report_date": "2025-12-31",
                "source_file": "ZQTZSHOW-latest.xls",
                "source_version": "sv-z-latest",
                "ingest_batch_id": "ib-latest-z",
                "archived_path": "/archive/zqtz/latest.xls",
            },
            {
                "source_family": "tyw",
                "report_date": "2025-12-31",
                "source_file": "TYWLSHOW-latest.xls",
                "source_version": "sv-t-latest",
                "ingest_batch_id": "ib-latest-t",
                "archived_path": "/archive/tyw/latest.xls",
            },
        ]
    )

    with pytest.raises(ValueError, match="has no materialized snapshot rows"):
        task_mod.materialize_balance_analysis_facts.fn(
            report_date="2025-12-31",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )


def test_balance_analysis_materialize_fails_closed_when_explicit_batch_lacks_one_required_family(
    tmp_path,
    monkeypatch,
):
    repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))
    _patch_skip_fx_refresh(task_mod, monkeypatch)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("update zqtz_bond_daily_snapshot set ingest_batch_id = 'ib-current'")
        conn.execute("update tyw_interbank_daily_snapshot set ingest_batch_id = 'ib-current'")
        conn.execute("delete from tyw_interbank_daily_snapshot where ingest_batch_id = 'ib-current'")
        repo_mod.ensure_balance_analysis_tables(conn)
        conn.execute(
            """
            insert into fact_formal_tyw_balance_daily (
              report_date, position_id, product_type, position_side, counterparty_name,
              account_type, special_account_type, core_customer_type, invest_type_std,
              accounting_basis, position_scope, currency_basis, currency_code, principal_amount,
              accrued_interest_amount, funding_cost_rate, maturity_date, source_version,
              rule_version, ingest_batch_id, trace_id
            ) values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-31",
                "pos-existing",
                "持有至到期同业存单",
                "liability",
                "银行存量",
                "负债账户",
                "一般",
                "股份制银行",
                "H",
                "AC",
                "liability",
                "CNY",
                "USD",
                Decimal("72"),
                Decimal("2"),
                Decimal("0.015"),
                "2026-06-30",
                "sv-existing",
                "rv-existing",
                "ib-existing",
                "trace-existing",
            ],
        )
    finally:
        conn.close()

    governance_dir.mkdir(parents=True, exist_ok=True)
    (governance_dir / "source_manifest.jsonl").write_text(
        json.dumps(
            {
                "source_name": "TYWLSHOW",
                "source_family": "tyw",
                "source_file": "TYWLSHOW-20251231.xls",
                "file_name": "TYWLSHOW-20251231.xls",
                "file_path": str(tmp_path / "TYWLSHOW-20251231.xls"),
                "file_size": 1,
                "report_date": "2025-12-31",
                "report_start_date": "2025-12-31",
                "report_end_date": "2025-12-31",
                "report_granularity": "day",
                "source_version": "sv-tyw-missing-snapshot",
                "ingest_batch_id": "ib-current",
                "archive_mode": "local",
                "archived_path": str(tmp_path / "archive" / "TYWLSHOW-20251231.xls"),
                "schema_version": "phase1.manifest.v1",
                "created_at": "2026-04-12T00:00:00+00:00",
                "status": "completed",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Explicit ingest_batch_id=ib-current"):
        task_mod.materialize_balance_analysis_facts.fn(
            report_date="2025-12-31",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            ingest_batch_id="ib-current",
        )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        remaining_tyw_fact_rows = conn.execute(
            """
            select count(*)
            from fact_formal_tyw_balance_daily
            where report_date = '2025-12-31'
            """
        ).fetchone()[0]
    finally:
        conn.close()

    assert remaining_tyw_fact_rows == 1
