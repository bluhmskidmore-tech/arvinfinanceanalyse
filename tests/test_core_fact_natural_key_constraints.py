"""Migration v43 natural-key constraints and the pre-load gates that back them.

The constraints protect a grain that legitimately carries near-duplicates: one
bond is booked into two accounting classes at once, and a red-reversal row shares
every key column with its replacement except the maturity date. Deduplicating
either would destroy real money, so these tests pin both directions — the
violation is rejected, the legitimate near-duplicate is kept.
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal

import duckdb
import pytest
from backend.app.core_finance.bond_analytics.engine import compute_bond_analytics_rows
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.duckdb_migrations import (
    _v43_add_core_fact_natural_key_constraints,
    _v43_constraint_statements,
    register_all,
)
from backend.app.repositories.duckdb_schema_registry import DuckDBSchemaRegistry
from backend.app.repositories.fact_load_gates import (
    BOND_ANALYTICS_NATURAL_KEY,
    FactLoadGateError,
    check_multi_maturity_exposure,
    check_natural_key_uniqueness,
    check_sign_and_attribution,
    enforce_gate_outcome,
    evaluate_bond_analytics_load,
)
from backend.app.repositories.task_write_guard import repository_task_write_scope
from tests.helpers import load_module

_EXPECTED_UNIQUE_INDEXES = {
    "uq_fact_formal_bond_analytics_daily_natural_key",
    "uq_fact_formal_zqtz_balance_daily_natural_key",
    "uq_fact_formal_tyw_balance_daily_natural_key",
    "uq_fact_formal_risk_tensor_daily_natural_key",
    "uq_fact_nonstd_pnl_bridge_natural_key",
}

_BRIDGE_KEY_COLUMNS = ("report_date", "bond_code", "portfolio_name", "cost_center")

_BOND_KEY_COLUMNS = (
    "report_date",
    "instrument_code",
    "portfolio_name",
    "cost_center",
    "accounting_class",
    "maturity_date",
)


def _pnl_materialize_module():
    module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if module is None:
        module = load_module(
            "backend.app.tasks.pnl_materialize", "backend/app/tasks/pnl_materialize.py"
        )
    return module


def _migrated_db(tmp_path, name: str = "v43.duckdb") -> str:
    db_path = tmp_path / name
    registry = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry)
    registry.apply_pending()
    return str(db_path)


def _bridge_values(
    *,
    report_date: str = "2025-12-31",
    bond_code: str = "BOND-001",
    portfolio_name: str = "FI Desk",
    cost_center: str | None = "CC100",
    total_pnl: str = "100.00",
) -> tuple[object, ...]:
    return (
        report_date,
        bond_code,
        portfolio_name,
        cost_center,
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal(total_pnl),
        "sv",
        "rv",
        "ib",
        "tr",
    )


def _insert_bridge_rows(conn: duckdb.DuckDBPyConnection, rows: list[tuple[object, ...]]) -> None:
    placeholders = ", ".join(["(" + ", ".join(["?"] * 13) + ")"] * len(rows))
    conn.execute(
        f"insert into fact_nonstd_pnl_bridge values {placeholders}",
        [value for row in rows for value in row],
    )


def _insert_bond_row(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str = "2025-09-30",
    instrument_code: str = "240215",
    portfolio_name: str = "FIOA",
    cost_center: str = "50",
    accounting_class: str = "AC",
    maturity_date: str | None = "2032-01-12",
) -> None:
    conn.execute(
        """
        insert into fact_formal_bond_analytics_daily
            (report_date, instrument_code, portfolio_name, cost_center, accounting_class, maturity_date)
        values (?, ?, ?, ?, ?, ?)
        """,
        [report_date, instrument_code, portfolio_name, cost_center, accounting_class, maturity_date],
    )


class _BondRow:
    """Minimal stand-in for BondAnalyticsRow; the gates only read named fields."""

    def __init__(
        self,
        *,
        instrument_code: str = "240215",
        portfolio_name: str = "FIOA",
        cost_center: str = "50",
        accounting_class: str = "AC",
        maturity_date: date | None = date(2032, 1, 12),
        market_value: Decimal = Decimal("1000000"),
        report_date: date = date(2025, 9, 30),
    ) -> None:
        self.report_date = report_date
        self.instrument_code = instrument_code
        self.portfolio_name = portfolio_name
        self.cost_center = cost_center
        self.accounting_class = accounting_class
        self.maturity_date = maturity_date
        self.market_value = market_value


# --------------------------------------------------------------------------
# migration
# --------------------------------------------------------------------------


def test_v43_creates_every_governed_unique_index(tmp_path) -> None:
    conn = duckdb.connect(_migrated_db(tmp_path))
    try:
        names = {
            row[0]
            for row in conn.execute(
                "select index_name from duckdb_indexes() where is_unique"
            ).fetchall()
        }
    finally:
        conn.close()
    assert _EXPECTED_UNIQUE_INDEXES <= names


def test_v43_is_idempotent(tmp_path) -> None:
    conn = duckdb.connect(_migrated_db(tmp_path))
    try:
        _v43_add_core_fact_natural_key_constraints(conn)
        _v43_add_core_fact_natural_key_constraints(conn)
        count = conn.execute(
            "select count(*) from duckdb_indexes() where index_name in "
            "('uq_fact_formal_bond_analytics_daily_natural_key')"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_v43_slice_declares_the_verified_bond_grain() -> None:
    specs = {table_name: parts for _sql, _index, table_name, parts in _v43_constraint_statements()}
    bond_parts = specs["fact_formal_bond_analytics_daily"]
    assert tuple(column for column, _expression, _sentinel in bond_parts) == _BOND_KEY_COLUMNS
    # Every column must be sentinel-folded: a bare nullable column would let its
    # NULL rows slip past the unique index.
    assert all(sentinel for _column, _expression, sentinel in bond_parts)


def test_v43_refuses_to_index_a_bare_nullable_column(monkeypatch, tmp_path) -> None:
    """A future edit that drops a coalesce wrapper must not slip through review."""
    specs = _v43_constraint_statements()
    tampered = [
        (statement, index_name, table_name, tuple(
            (column, column, "") if table_name == "fact_formal_risk_tensor_daily"
            else (column, expression, sentinel)
            for column, expression, sentinel in parts
        ))
        for statement, index_name, table_name, parts in specs
    ]
    conn = duckdb.connect(_migrated_db(tmp_path))
    monkeypatch.setattr(
        "backend.app.repositories.duckdb_migrations._v43_constraint_statements",
        lambda: tampered,
    )
    try:
        with pytest.raises(RuntimeError, match="indexed bare"):
            _v43_add_core_fact_natural_key_constraints(conn)
    finally:
        conn.close()


def test_v43_rejects_a_duplicate_grain_instead_of_deduplicating(tmp_path) -> None:
    """Preflight must abort; silently dropping a row could destroy a real position."""
    db_path = _migrated_db(tmp_path)
    conn = duckdb.connect(db_path)
    try:
        conn.execute("drop index uq_fact_formal_bond_analytics_daily_natural_key")
        _insert_bond_row(conn)
        _insert_bond_row(conn)

        with pytest.raises(RuntimeError, match="duplicate natural-key groups"):
            _v43_add_core_fact_natural_key_constraints(conn)

        assert conn.execute("select count(*) from fact_formal_bond_analytics_daily").fetchone()[0] == 2
    finally:
        conn.close()


def test_v43_folds_nulls_rather_than_demanding_cleanup(tmp_path) -> None:
    """A legacy row with a NULL key column must still migrate — and stay constrained."""
    db_path = _migrated_db(tmp_path)
    conn = duckdb.connect(db_path)
    try:
        conn.execute("drop index uq_fact_formal_bond_analytics_daily_natural_key")
        _insert_bond_row(conn, cost_center=None)  # type: ignore[arg-type]
        _v43_add_core_fact_natural_key_constraints(conn)

        with pytest.raises(duckdb.ConstraintException):
            _insert_bond_row(conn, cost_center=None)  # type: ignore[arg-type]
        assert conn.execute("select count(*) from fact_formal_bond_analytics_daily").fetchone()[0] == 1
    finally:
        conn.close()


def test_v43_still_aborts_on_a_duplicate_that_only_null_folding_reveals(tmp_path) -> None:
    db_path = _migrated_db(tmp_path)
    conn = duckdb.connect(db_path)
    try:
        conn.execute("drop index uq_fact_formal_bond_analytics_daily_natural_key")
        _insert_bond_row(conn, cost_center=None, maturity_date=None)  # type: ignore[arg-type]
        _insert_bond_row(conn, cost_center=None, maturity_date=None)  # type: ignore[arg-type]
        with pytest.raises(RuntimeError, match="duplicate natural-key groups"):
            _v43_add_core_fact_natural_key_constraints(conn)
    finally:
        conn.close()


def test_v43_rejects_a_sentinel_value_present_in_real_data(tmp_path) -> None:
    """A real cost center spelled like the sentinel would merge with 'unknown'."""
    db_path = _migrated_db(tmp_path)
    conn = duckdb.connect(db_path)
    try:
        conn.execute("drop index uq_fact_formal_bond_analytics_daily_natural_key")
        _insert_bond_row(conn, cost_center="__moss_null__")
        with pytest.raises(RuntimeError, match="NULL sentinel"):
            _v43_add_core_fact_natural_key_constraints(conn)
    finally:
        conn.close()


def test_v43_index_rejects_duplicates_including_null_maturity(tmp_path) -> None:
    """DuckDB treats NULL as distinct in a unique index; the sentinel closes that hole."""
    conn = duckdb.connect(_migrated_db(tmp_path))
    try:
        _insert_bond_row(conn)
        with pytest.raises(duckdb.ConstraintException):
            _insert_bond_row(conn)

        _insert_bond_row(conn, instrument_code="FUND001", maturity_date=None)
        with pytest.raises(duckdb.ConstraintException):
            _insert_bond_row(conn, instrument_code="FUND001", maturity_date=None)

        assert conn.execute("select count(*) from fact_formal_bond_analytics_daily").fetchone()[0] == 2
    finally:
        conn.close()


def test_v43_keeps_the_legitimate_two_book_split(tmp_path) -> None:
    """240215 sits in AC and OCI at once — 931 such groups exist and must survive."""
    conn = duckdb.connect(_migrated_db(tmp_path))
    try:
        _insert_bond_row(conn, accounting_class="AC")
        _insert_bond_row(conn, accounting_class="OCI")
        # ...and a red-reversal pair differing only by maturity date.
        _insert_bond_row(conn, instrument_code="031800572.IB", maturity_date="2024-02-21")
        _insert_bond_row(conn, instrument_code="031800572.IB", maturity_date="2026-09-21")
        assert conn.execute("select count(*) from fact_formal_bond_analytics_daily").fetchone()[0] == 4
    finally:
        conn.close()


# --------------------------------------------------------------------------
# fact_nonstd_pnl_bridge — constraint and loader
# --------------------------------------------------------------------------


def test_v43_slice_declares_the_verified_bridge_grain() -> None:
    specs = {table_name: parts for _sql, _index, table_name, parts in _v43_constraint_statements()}
    bridge_parts = specs["fact_nonstd_pnl_bridge"]
    assert tuple(column for column, _expression, _sentinel in bridge_parts) == _BRIDGE_KEY_COLUMNS
    assert all(sentinel for _column, _expression, sentinel in bridge_parts)


def test_v43_bridge_index_rejects_a_duplicate_batch_without_landing_a_row(tmp_path) -> None:
    """The whole statement is refused, not partially applied."""
    conn = duckdb.connect(_migrated_db(tmp_path, "bridge_reject.duckdb"))
    try:
        with pytest.raises(duckdb.ConstraintException):
            _insert_bridge_rows(conn, [_bridge_values(), _bridge_values(total_pnl="7.00")])
        assert conn.execute("select count(*) from fact_nonstd_pnl_bridge").fetchone()[0] == 0
    finally:
        conn.close()


def test_v43_bridge_index_folds_nulls_like_the_other_governed_facts(tmp_path) -> None:
    conn = duckdb.connect(_migrated_db(tmp_path, "bridge_nulls.duckdb"))
    try:
        _insert_bridge_rows(conn, [_bridge_values(cost_center=None)])
        with pytest.raises(duckdb.ConstraintException):
            _insert_bridge_rows(conn, [_bridge_values(cost_center=None)])
        assert conn.execute("select count(*) from fact_nonstd_pnl_bridge").fetchone()[0] == 1
    finally:
        conn.close()


def test_v43_bridge_index_keeps_one_bond_split_across_desks_and_cost_centers(tmp_path) -> None:
    """The bridge grain is per desk and cost center; splitting one bond is legal."""
    conn = duckdb.connect(_migrated_db(tmp_path, "bridge_split.duckdb"))
    try:
        _insert_bridge_rows(
            conn,
            [
                _bridge_values(),
                _bridge_values(portfolio_name="FIOA"),
                _bridge_values(cost_center="CC200"),
                _bridge_values(report_date="2025-11-30"),
            ],
        )
        assert conn.execute("select count(*) from fact_nonstd_pnl_bridge").fetchone()[0] == 4
    finally:
        conn.close()


def _bridge_journal_row(*, voucher_date: str, raw_amount: str, trace_id: str) -> dict[str, object]:
    return {
        "voucher_date": voucher_date,
        "account_code": "51601010004",
        "asset_code": "BOND-001",
        "portfolio_name": "FI Desk",
        "cost_center": "CC100",
        "dc_flag": "credit",
        "event_type": "mtm",
        "raw_amount": raw_amount,
        "source_file": "nonstd-516.xlsx",
        "source_version": "src-v1",
        "rule_version": "rule-v1",
        "ingest_batch_id": "batch-bridge",
        "trace_id": trace_id,
    }


def _run_pnl_materialize(task_module, *, duckdb_path, governance_dir) -> dict[str, object]:
    return task_module.materialize_pnl_facts.fn(
        report_date="2025-12-31",
        is_month_end=True,
        fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "240001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "interest_income_514": "12.50",
                "fair_value_change_516": "-3.25",
                "capital_gain_517": "1.75",
                "manual_adjustment": "0.50",
                "currency_basis": "CNY",
                "source_version": "src-v1",
                "rule_version": "rule-v1",
                "ingest_batch_id": "batch-fi",
                "trace_id": "trace-fi",
                "approval_status": "approved",
                "event_semantics": "realized_incremental",
                "realized_flag": True,
            }
        ],
        nonstd_rows_by_type={
            "516": [
                _bridge_journal_row(
                    voucher_date="2025-12-30", raw_amount="40.00", trace_id="trace-001"
                ),
                _bridge_journal_row(
                    voucher_date="2025-12-31", raw_amount="60.00", trace_id="trace-002"
                ),
            ]
        },
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["*"]',
    )


def _bridge_state(duckdb_path) -> list[tuple[object, ...]]:
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        return conn.execute(
            "select report_date, bond_code, portfolio_name, cost_center, total_pnl "
            "from fact_nonstd_pnl_bridge order by 1, 2, 3, 4"
        ).fetchall()
    finally:
        conn.close()


def test_pnl_materialize_reruns_one_report_date_under_the_bridge_constraint(tmp_path) -> None:
    """Three reruns of one report date: the constraint must not break idempotency.

    Before the loader committed its purge separately this failed on the second
    run, because DuckDB 1.5.1 keeps the deleted keys in the unique index until
    the deleting transaction commits.
    """
    task_module = _pnl_materialize_module()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    states = []
    for _attempt in range(3):
        payload = _run_pnl_materialize(
            task_module, duckdb_path=duckdb_path, governance_dir=governance_dir
        )
        assert payload["status"] == "completed"
        assert payload["nonstd_bridge_rows"] == 1
        states.append(_bridge_state(duckdb_path))

    assert states[0] == [("2025-12-31", "BOND-001", "FI Desk", "CC100", Decimal("100.00"))]
    assert states[1] == states[0], "rerun 2 changed the bridge fact"
    assert states[2] == states[0], "rerun 3 changed the bridge fact"


def test_pnl_materialize_gate_rejects_a_duplicated_bridge_batch_and_keeps_the_good_load(
    tmp_path, monkeypatch
) -> None:
    """A defective batch must be named before the purge, so the stored date survives."""
    task_module = _pnl_materialize_module()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    _run_pnl_materialize(task_module, duckdb_path=duckdb_path, governance_dir=governance_dir)
    good_state = _bridge_state(duckdb_path)
    assert len(good_state) == 1

    original = task_module.build_nonstd_pnl_bridge_rows
    monkeypatch.setattr(
        task_module,
        "build_nonstd_pnl_bridge_rows",
        lambda *args, **kwargs: [row for row in original(*args, **kwargs) for _ in range(2)],
    )
    with pytest.raises(FactLoadGateError) as excinfo:
        _run_pnl_materialize(
            task_module, duckdb_path=duckdb_path, governance_dir=governance_dir
        )

    assert excinfo.value.table_name == "fact_nonstd_pnl_bridge"
    assert "Do not deduplicate" in str(excinfo.value)
    assert _bridge_state(duckdb_path) == good_state, "the purge ran before the gate"


# --------------------------------------------------------------------------
# gate A — uniqueness, blocking
# --------------------------------------------------------------------------


def test_gate_a_blocks_a_duplicate_natural_key() -> None:
    outcome = evaluate_bond_analytics_load([_BondRow(), _BondRow()])
    assert outcome.rejected
    assert outcome.blocking[0].code == "duplicate_natural_key"
    assert "Do not deduplicate" in outcome.blocking[0].message
    assert outcome.blocking[0].message.isascii(), "gate text must survive a cp936 console"


def test_gate_a_treats_two_null_maturities_as_the_same_key() -> None:
    outcome = evaluate_bond_analytics_load(
        [_BondRow(maturity_date=None), _BondRow(maturity_date=None)]
    )
    assert outcome.rejected


def test_gate_a_allows_the_two_book_split_and_the_reversal_pair() -> None:
    rows = [
        _BondRow(accounting_class="AC"),
        _BondRow(accounting_class="OCI"),
        _BondRow(instrument_code="031800572.IB", maturity_date=date(2024, 2, 21)),
        _BondRow(instrument_code="031800572.IB", maturity_date=date(2026, 9, 21)),
    ]
    assert check_natural_key_uniqueness(
        rows, table_name="t", key_fields=BOND_ANALYTICS_NATURAL_KEY
    ) == []


def test_enforce_raises_and_names_the_table() -> None:
    outcome = evaluate_bond_analytics_load([_BondRow(), _BondRow()])
    with pytest.raises(FactLoadGateError) as excinfo:
        enforce_gate_outcome(outcome, table_name="fact_formal_bond_analytics_daily")
    assert excinfo.value.table_name == "fact_formal_bond_analytics_daily"


# --------------------------------------------------------------------------
# gate B — one instrument, several maturity dates
# --------------------------------------------------------------------------


def test_gate_b_catches_the_amtd_maturity_roll_double_send() -> None:
    """2025-02-28: the pre-roll and post-roll rows both landed, +CNY 1.894bn."""
    amtd = Decimal("1893639290.80")
    rows = [
        _BondRow(
            instrument_code="J11603010202",
            cost_center="",
            maturity_date=date(2025, 2, 28),
            market_value=amtd,
        ),
        _BondRow(
            instrument_code="J11603010202",
            cost_center="53",
            maturity_date=date(2025, 3, 31),
            market_value=amtd,
        ),
    ]
    outcome = evaluate_bond_analytics_load(rows)
    assert not outcome.rejected, "gate B warns; it must not block a legal-looking batch"
    codes = {finding.code for finding in outcome.warnings}
    assert "multi_maturity_same_instrument" in codes


def test_gate_b_stays_quiet_below_the_amount_floor() -> None:
    rows = [
        _BondRow(maturity_date=date(2025, 2, 28), market_value=Decimal("1000")),
        _BondRow(maturity_date=date(2025, 3, 31), market_value=Decimal("1000")),
    ]
    assert check_multi_maturity_exposure(rows, table_name="t") == []


def test_gate_b_stays_quiet_for_one_maturity_per_instrument() -> None:
    rows = [
        _BondRow(accounting_class="AC", market_value=Decimal("5000000000")),
        _BondRow(accounting_class="OCI", market_value=Decimal("5000000000")),
    ]
    assert check_multi_maturity_exposure(rows, table_name="t") == []


# --------------------------------------------------------------------------
# gate C — sign and attribution
# --------------------------------------------------------------------------


def test_gate_c_reports_negative_market_value() -> None:
    findings = check_sign_and_attribution(
        [_BondRow(instrument_code="031800572.IB", market_value=Decimal("-14273208.63"))],
        table_name="t",
    )
    assert {finding.code for finding in findings} == {"negative_amount"}


def test_gate_c_reports_real_money_without_a_cost_center() -> None:
    findings = check_sign_and_attribution(
        [_BondRow(cost_center="", market_value=Decimal("1893639290.80"))],
        table_name="t",
    )
    assert {finding.code for finding in findings} == {"missing_cost_center"}


def test_gate_c_whitelists_zero_value_rows_without_a_cost_center() -> None:
    """585 counter-sold certificate treasuries have no cost center and no market value.

    Alerting on them would add ~31 findings every single day and the gate would
    be switched off, so the carve-out is what keeps gate C usable.
    """
    rows = [
        _BondRow(instrument_code=f"CERT{index}", cost_center="", market_value=Decimal("0"))
        for index in range(31)
    ]
    assert check_sign_and_attribution(rows, table_name="t") == []


def test_gate_c_never_blocks() -> None:
    rows = [
        _BondRow(instrument_code="A", cost_center="", market_value=Decimal("-999999999")),
        _BondRow(instrument_code="B", cost_center="", market_value=Decimal("999999999")),
    ]
    outcome = evaluate_bond_analytics_load(rows)
    assert not outcome.rejected
    assert len(outcome.warnings) >= 2


# --------------------------------------------------------------------------
# wiring — the gate runs inside the real write path
# --------------------------------------------------------------------------


def _real_analytics_row(report_date: str = "2026-03-31"):
    return compute_bond_analytics_rows(
        [
            {
                "report_date": date.fromisoformat(report_date),
                "instrument_code": "BOND-GATE",
                "currency_code": "CNY",
                "face_value_native": Decimal("100"),
                "market_value_native": Decimal("99"),
                "amortized_cost_native": Decimal("98"),
                "accrued_interest_native": Decimal("1"),
                "coupon_rate": Decimal("3"),
                "ytm_value": Decimal("3.5"),
                "value_date": date(2023, 4, 20),
                "maturity_date": date(2026, 4, 20),
                "interest_mode": "bullet",
                "is_issuance_like": False,
            }
        ],
        date.fromisoformat(report_date),
    )[0]


def test_repository_write_path_rejects_a_duplicated_batch(tmp_path) -> None:
    report_date = "2026-03-31"
    path = str(tmp_path / "gated.duckdb")
    repo = BondAnalyticsRepository(path)
    row = _real_analytics_row(report_date)

    with repository_task_write_scope("backend.app.tasks.core_fact_gate_test"):
        repo.replace_bond_analytics_rows(report_date=report_date, rows=[row])
    assert len(repo.fetch_bond_analytics_rows(report_date=report_date)) == 1

    with (
        repository_task_write_scope("backend.app.tasks.core_fact_gate_test"),
        pytest.raises(FactLoadGateError),
    ):
        repo.replace_bond_analytics_rows(report_date=report_date, rows=[row, row])

    # The gate runs before the delete/insert pair, so the good load survives.
    assert len(repo.fetch_bond_analytics_rows(report_date=report_date)) == 1
