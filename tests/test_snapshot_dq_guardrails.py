from __future__ import annotations

from decimal import Decimal

import duckdb
import pytest

from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.snapshot_repo import (
    ensure_snapshot_natural_key_constraints,
    ensure_snapshot_tables,
    merge_tyw_rows_by_grain,
    merge_zqtz_rows_by_grain,
    replace_tyw_snapshot_rows,
    replace_zqtz_snapshot_rows,
)
from backend.app.repositories.task_write_guard import repository_task_write_scope


def _tyw_row(*, position_id: str, principal: str, accrued: str = "0", rate: str = "0.015", counterparty: str = "银行A") -> dict[str, object]:
    return {
        "report_date": "2026-02-26",
        "position_id": position_id,
        "product_type": "卖出回购证券",
        "position_side": "liability",
        "counterparty_name": counterparty,
        "account_type": "acct",
        "special_account_type": None,
        "core_customer_type": "银行",
        "currency_code": "CNY",
        "principal_native": Decimal(principal),
        "accrued_interest_native": Decimal(accrued),
        "funding_cost_rate": Decimal(rate),
        "maturity_date": "2026-02-27",
        "pledged_bond_code": None,
        "source_version": "sv",
        "rule_version": "rv",
        "ingest_batch_id": "ib",
        "trace_id": f"trace-{position_id}-{principal}",
    }


def _zqtz_row(
    *,
    instrument_code: str = "240215",
    asset_class: str = "FVOCI",
    face_value: str = "100",
    market_value: str = "101",
    amortized_cost: str = "100",
    interest_receivable_payable: Decimal | None = None,
) -> dict[str, object]:
    return {
        "report_date": "2026-02-28",
        "instrument_code": instrument_code,
        "instrument_name": "bond",
        "portfolio_name": "FIOA",
        "cost_center": "5010",
        "account_category": "bank",
        "asset_class": asset_class,
        "bond_type": "policy",
        "business_type_primary": "policy",
        "issuer_name": "issuer",
        "industry_name": "industry",
        "rating": "AAA",
        "currency_code": "CNY",
        "face_value_native": Decimal(face_value),
        "market_value_native": Decimal(market_value),
        "amortized_cost_native": Decimal(amortized_cost),
        "accrued_interest_native": Decimal("1"),
        "interest_receivable_payable": interest_receivable_payable,
        "coupon_rate": Decimal("0.020"),
        "ytm_value": Decimal("0.025"),
        "maturity_date": "2034-01-01",
        "next_call_date": None,
        "overdue_days": 0,
        "is_issuance_like": False,
        "interest_mode": "fixed",
        "source_version": "sv",
        "rule_version": "rv",
        "ingest_batch_id": "ib",
        "trace_id": f"trace-{instrument_code}-{asset_class}-{face_value}",
        "value_date": None,
        "customer_attribute": "",
    }


def test_merge_zqtz_rows_by_grain_sums_duplicate_lots_with_same_accounting_bucket() -> None:
    rows = [
        _zqtz_row(face_value="100", market_value="101", amortized_cost="100"),
        _zqtz_row(face_value="200", market_value="203", amortized_cost="201"),
    ]

    merged = merge_zqtz_rows_by_grain(rows)

    assert len(merged) == 1
    assert merged[0]["face_value_native"] == Decimal("300")
    assert merged[0]["market_value_native"] == Decimal("304")
    assert merged[0]["amortized_cost_native"] == Decimal("301")
    assert merged[0]["accrued_interest_native"] == Decimal("2")


@pytest.mark.parametrize("field", ("coupon_rate", "ytm_value"))
@pytest.mark.parametrize("known_rate", (None, Decimal("0"), Decimal("3")))
def test_merge_zqtz_rates_require_complete_weighted_observations(field, known_rate) -> None:
    rows = [
        {**_zqtz_row(face_value="100"), field: known_rate},
        {**_zqtz_row(face_value="100"), field: None},
    ]
    for ordered in (rows, rows[::-1]):
        merged = merge_zqtz_rows_by_grain(ordered)[0]
        assert merged[field] is None
        other_field = "ytm_value" if field == "coupon_rate" else "coupon_rate"
        assert merged[other_field] == rows[0][other_field]


@pytest.mark.parametrize("field", ("coupon_rate", "ytm_value"))
def test_merge_zqtz_rates_preserve_full_coverage_and_explicit_zero(field) -> None:
    rows = [
        {**_zqtz_row(face_value="100"), field: Decimal("0")},
        {**_zqtz_row(face_value="300"), field: Decimal("4")},
    ]
    for ordered in (rows, rows[::-1]):
        assert merge_zqtz_rows_by_grain(ordered)[0][field] == Decimal("3")
    rows[1][field] = Decimal("0")
    assert merge_zqtz_rows_by_grain(rows)[0][field] == Decimal("0")


@pytest.mark.parametrize("field", ("coupon_rate", "ytm_value"))
def test_merge_zqtz_rates_ignore_missing_zero_weight_and_reject_undefined_weight(field) -> None:
    observed = {**_zqtz_row(face_value="100"), field: Decimal("3")}
    zero_weight = {**_zqtz_row(face_value="0"), field: None}
    assert merge_zqtz_rows_by_grain([observed, zero_weight])[0][field] == Decimal("3")
    opposing = {**_zqtz_row(face_value="-100"), field: Decimal("4")}
    for ordered in ([observed, opposing], [opposing, observed]):
        assert merge_zqtz_rows_by_grain(ordered)[0][field] is None
    assert merge_zqtz_rows_by_grain([zero_weight])[0][field] is None
    with pytest.raises(ValueError, match="face_value_native must be finite"):
        merge_zqtz_rows_by_grain([{**observed, "face_value_native": Decimal("NaN")}])


@pytest.mark.parametrize("field", ("coupon_rate", "ytm_value"))
@pytest.mark.parametrize("invalid", (Decimal("NaN"), Decimal("Infinity")))
def test_merge_zqtz_nonfinite_rate_is_unavailable(field, invalid) -> None:
    rows = [
        {**_zqtz_row(face_value="100"), field: invalid},
        {**_zqtz_row(face_value="100"), field: Decimal("3")},
    ]
    for ordered in (rows, rows[::-1]):
        assert merge_zqtz_rows_by_grain(ordered)[0][field] is None


def test_merge_zqtz_rows_by_grain_sums_interest_receivable_without_inventing_zero() -> None:
    both_present = merge_zqtz_rows_by_grain(
        [
            _zqtz_row(face_value="100", interest_receivable_payable=Decimal("120.5")),
            _zqtz_row(face_value="200", interest_receivable_payable=Decimal("40.25")),
        ]
    )
    partially_present = merge_zqtz_rows_by_grain(
        [
            _zqtz_row(face_value="100", interest_receivable_payable=None),
            _zqtz_row(face_value="200", interest_receivable_payable=Decimal("40.25")),
        ]
    )
    all_missing = merge_zqtz_rows_by_grain(
        [
            _zqtz_row(face_value="100", interest_receivable_payable=None),
            _zqtz_row(face_value="200", interest_receivable_payable=None),
        ]
    )

    assert both_present[0]["interest_receivable_payable"] == Decimal("160.75")
    assert partially_present[0]["interest_receivable_payable"] == Decimal("40.25")
    assert all_missing[0]["interest_receivable_payable"] is None


def test_merge_zqtz_rows_by_grain_keeps_distinct_accounting_buckets_separate() -> None:
    rows = [
        _zqtz_row(asset_class="HTM", face_value="100", market_value="101"),
        _zqtz_row(asset_class="FVOCI", face_value="200", market_value="203"),
    ]

    merged = merge_zqtz_rows_by_grain(rows)

    assert len(merged) == 2
    assert {row["asset_class"] for row in merged} == {"HTM", "FVOCI"}


def test_merge_tyw_rows_by_grain_sums_duplicate_position_rows() -> None:
    rows = [
        _tyw_row(position_id="3747070", principal="2565000000"),
        _tyw_row(position_id="3747070", principal="435000000"),
    ]

    merged = merge_tyw_rows_by_grain(rows)

    assert len(merged) == 1
    assert merged[0]["position_id"] == "3747070"
    assert merged[0]["principal_native"] == Decimal("3000000000")


def test_merge_tyw_funding_rate_requires_complete_weighted_observations() -> None:
    for known_rate in (None, Decimal("0"), Decimal("0.03")):
        rows = [
            {**_tyw_row(position_id="SYN", principal="100"), "funding_cost_rate": known_rate},
            {**_tyw_row(position_id="SYN", principal="100"), "funding_cost_rate": None},
        ]
        for ordered in (rows, rows[::-1]):
            assert merge_tyw_rows_by_grain(ordered)[0]["funding_cost_rate"] is None


def test_merge_tyw_funding_rate_preserves_full_coverage_zero_and_zero_weight() -> None:
    zero = {**_tyw_row(position_id="SYN", principal="100"), "funding_cost_rate": Decimal("0")}
    four = {**_tyw_row(position_id="SYN", principal="300"), "funding_cost_rate": Decimal("0.04")}
    for ordered in ([zero, four], [four, zero]):
        assert merge_tyw_rows_by_grain(ordered)[0]["funding_cost_rate"] == Decimal("0.03")
    assert merge_tyw_rows_by_grain([zero])[0]["funding_cost_rate"] == Decimal("0")
    zero_weight = {**_tyw_row(position_id="SYN", principal="0"), "funding_cost_rate": None}
    assert merge_tyw_rows_by_grain([four, zero_weight])[0]["funding_cost_rate"] == Decimal("0.04")
    assert merge_tyw_rows_by_grain([zero_weight])[0]["funding_cost_rate"] is None


def test_merge_tyw_funding_rate_rejects_undefined_weight_and_nonfinite_rate() -> None:
    good = _tyw_row(position_id="SYN", principal="100", rate="0.03")
    negative = _tyw_row(position_id="SYN", principal="-100", rate="0.04")
    for ordered in ([good, negative], [negative, good]):
        assert merge_tyw_rows_by_grain(ordered)[0]["funding_cost_rate"] is None
    for invalid in (Decimal("NaN"), Decimal("Infinity")):
        row = {**good, "funding_cost_rate": invalid}
        assert merge_tyw_rows_by_grain([row])[0]["funding_cost_rate"] is None
    with pytest.raises(ValueError, match="principal_native must be finite"):
        merge_tyw_rows_by_grain([{**good, "principal_native": Decimal("Infinity")}])


def test_merge_tyw_rows_by_grain_fails_closed_on_conflicting_metadata() -> None:
    rows = [
        _tyw_row(position_id="3747070", principal="2565000000", counterparty="国家开发银行"),
        _tyw_row(position_id="3747070", principal="435000000", counterparty="中国农业银行股份有限公司"),
    ]

    with pytest.raises(ValueError, match="conflicting TYW snapshot rows share the same canonical grain"):
        merge_tyw_rows_by_grain(rows)


def test_replace_tyw_snapshot_rows_can_replace_all_rows_for_report_date(tmp_path) -> None:
    db_path = tmp_path / "snapshot.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table tyw_interbank_daily_snapshot (
              report_date date,
              position_id varchar,
              product_type varchar,
              position_side varchar,
              counterparty_name varchar,
              account_type varchar,
              special_account_type varchar,
              core_customer_type varchar,
              currency_code varchar,
              principal_native decimal(24, 8),
              accrued_interest_native decimal(24, 8),
              funding_cost_rate decimal(18, 8),
              maturity_date date,
              pledged_bond_code varchar,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot values
            ('2026-02-26','old-1','同业拆入','liability','银行A','acct',null,'银行','CNY',100,0,0.015,'2026-03-01',null,'sv-old','rv','ib-old','trace-old')
            """
        )

        rows = [_tyw_row(position_id="new-1", principal="200", counterparty="银行B")]
        with repository_task_write_scope("backend.app.tasks.snapshot_dq_guardrails_test"):
            replace_tyw_snapshot_rows(
                conn,
                rows,
                ingest_batch_ids=["ib-new"],
                report_dates=["2026-02-26"],
                replace_all_for_report_dates=True,
            )

        result = conn.execute(
            "select position_id, ingest_batch_id, principal_native from tyw_interbank_daily_snapshot order by position_id"
        ).fetchall()
    finally:
        conn.close()

    assert result == [("new-1", "ib", 200)]


def test_snapshot_replace_preserves_decimal_precision_for_zqtz_and_tyw(tmp_path) -> None:
    db_path = tmp_path / "snapshot-precision.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        ensure_snapshot_tables(conn)
        zqtz_row = _zqtz_row(
            face_value="123456789012.12345678",
            market_value="9999999999.99999999",
            amortized_cost="1234567890.12345678",
        )
        zqtz_row["accrued_interest_native"] = Decimal("987654321.87654321")
        tyw_row = _tyw_row(
            position_id="precision-tyw",
            principal="123456789012.12345678",
            accrued="987654321.87654321",
            rate="0.12345678",
        )

        with repository_task_write_scope("backend.app.tasks.snapshot_precision_test"):
            replace_zqtz_snapshot_rows(conn, [zqtz_row], ingest_batch_ids=["ib"])
            replace_tyw_snapshot_rows(conn, [tyw_row], ingest_batch_ids=["ib"])

        zqtz_values = conn.execute(
            """
            select face_value_native, market_value_native,
                   amortized_cost_native, accrued_interest_native
            from zqtz_bond_daily_snapshot
            """
        ).fetchone()
        tyw_values = conn.execute(
            """
            select principal_native, accrued_interest_native, funding_cost_rate
            from tyw_interbank_daily_snapshot
            """
        ).fetchone()
    finally:
        conn.close()

    assert zqtz_values == (
        Decimal("123456789012.12345678"),
        Decimal("9999999999.99999999"),
        Decimal("1234567890.12345678"),
        Decimal("987654321.87654321"),
    )
    assert tyw_values == (
        Decimal("123456789012.12345678"),
        Decimal("987654321.87654321"),
        Decimal("0.12345678"),
    )


def _insert_raw_zqtz_row(conn: duckdb.DuckDBPyConnection, row: dict[str, object]) -> None:
    """Insert a zqtz snapshot row bypassing replace_zqtz_snapshot_rows's own dedup.

    Used only to simulate legacy double-counted data that accumulated *before*
    the natural-key fix existed (same instrument/grain written twice under
    different ingest_batch_id values with no cleanup in between).
    """
    conn.execute(
        """
        insert into zqtz_bond_daily_snapshot (
          report_date, instrument_code, instrument_name, portfolio_name, cost_center,
          account_category, asset_class, bond_type, business_type_primary, issuer_name,
          industry_name, rating, currency_code, face_value_native, market_value_native,
          amortized_cost_native, accrued_interest_native, coupon_rate, ytm_value,
          maturity_date, next_call_date, overdue_days, is_issuance_like, interest_mode,
          source_version, rule_version, ingest_batch_id, trace_id, value_date,
          customer_attribute, sub_type, interest_receivable_payable
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            row["report_date"],
            row["instrument_code"],
            row["instrument_name"],
            row["portfolio_name"],
            row["cost_center"],
            row["account_category"],
            row["asset_class"],
            row["bond_type"],
            row.get("business_type_primary") or "",
            row["issuer_name"],
            row["industry_name"],
            row["rating"],
            row["currency_code"],
            row["face_value_native"],
            row["market_value_native"],
            row["amortized_cost_native"],
            row["accrued_interest_native"],
            row["coupon_rate"],
            row["ytm_value"],
            row["maturity_date"],
            row["next_call_date"],
            row["overdue_days"],
            row["is_issuance_like"],
            row["interest_mode"],
            row["source_version"],
            row["rule_version"],
            row["ingest_batch_id"],
            row["trace_id"],
            row.get("value_date"),
            row.get("customer_attribute") or "",
            row.get("sub_type") or "",
            row.get("interest_receivable_payable"),
        ],
    )


def test_replace_zqtz_snapshot_rows_removes_prior_batch_row_for_same_natural_grain(tmp_path) -> None:
    """Defect 1: a same-day replay under a *different* ingest_batch_id must not double-count."""
    db_path = tmp_path / "snapshot-zqtz-cross-batch.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        ensure_snapshot_tables(conn)

        old_row = _zqtz_row(market_value="100")
        old_row["ingest_batch_id"] = "ib-old"
        with repository_task_write_scope("backend.app.tasks.snapshot_cross_batch_test"):
            replace_zqtz_snapshot_rows(
                conn, [old_row], ingest_batch_ids=["ib-old"], report_dates=["2026-02-28"]
            )

        new_row = _zqtz_row(market_value="205")
        new_row["ingest_batch_id"] = "ib-new"
        with repository_task_write_scope("backend.app.tasks.snapshot_cross_batch_test"):
            replace_zqtz_snapshot_rows(
                conn, [new_row], ingest_batch_ids=["ib-new"], report_dates=["2026-02-28"]
            )

        rows = conn.execute(
            "select ingest_batch_id, market_value_native from zqtz_bond_daily_snapshot"
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("ib-new", Decimal("205"))]


def test_replace_tyw_snapshot_rows_removes_prior_batch_row_for_same_position(tmp_path) -> None:
    """Defect 1, tyw side: same-day replay under a different ingest_batch_id must not double-count."""
    db_path = tmp_path / "snapshot-tyw-cross-batch.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        ensure_snapshot_tables(conn)

        old_row = _tyw_row(position_id="pos-1", principal="100")
        old_row["ingest_batch_id"] = "ib-old"
        with repository_task_write_scope("backend.app.tasks.snapshot_cross_batch_test"):
            replace_tyw_snapshot_rows(
                conn, [old_row], ingest_batch_ids=["ib-old"], report_dates=["2026-02-26"]
            )

        new_row = _tyw_row(position_id="pos-1", principal="250")
        new_row["ingest_batch_id"] = "ib-new"
        with repository_task_write_scope("backend.app.tasks.snapshot_cross_batch_test"):
            replace_tyw_snapshot_rows(
                conn, [new_row], ingest_batch_ids=["ib-new"], report_dates=["2026-02-26"]
            )

        rows = conn.execute(
            "select ingest_batch_id, principal_native from tyw_interbank_daily_snapshot"
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("ib-new", Decimal("250"))]


def test_replace_all_for_report_dates_still_replaces_whole_day_after_natural_key_fix(tmp_path) -> None:
    """The pre-existing whole-day replace branch must not regress."""
    db_path = tmp_path / "snapshot-replace-all.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        ensure_snapshot_tables(conn)

        first = _zqtz_row(instrument_code="A", market_value="100")
        first["ingest_batch_id"] = "ib-1"
        second = _zqtz_row(instrument_code="B", market_value="200")
        second["ingest_batch_id"] = "ib-1"
        with repository_task_write_scope("backend.app.tasks.snapshot_replace_all_test"):
            replace_zqtz_snapshot_rows(
                conn,
                [first, second],
                ingest_batch_ids=["ib-1"],
                report_dates=["2026-02-28"],
                replace_all_for_report_dates=True,
            )

        replacement = _zqtz_row(instrument_code="C", market_value="300")
        replacement["ingest_batch_id"] = "ib-2"
        with repository_task_write_scope("backend.app.tasks.snapshot_replace_all_test"):
            replace_zqtz_snapshot_rows(
                conn,
                [replacement],
                ingest_batch_ids=["ib-2"],
                report_dates=["2026-02-28"],
                replace_all_for_report_dates=True,
            )

        rows = conn.execute(
            "select instrument_code, ingest_batch_id from zqtz_bond_daily_snapshot"
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("C", "ib-2")]


def test_ensure_snapshot_natural_key_constraints_dedupes_preexisting_cross_batch_duplicates(
    tmp_path,
) -> None:
    """Migration-time cleanup: keep the last-written row per natural-key group."""
    db_path = tmp_path / "snapshot-dedupe.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        apply_pending_migrations_on_connection(conn)  # base tables only, no natural-key index yet

        old_row = _zqtz_row(market_value="100")
        old_row["ingest_batch_id"] = "ib-old"
        newer_row = _zqtz_row(market_value="205")
        newer_row["ingest_batch_id"] = "ib-new"
        _insert_raw_zqtz_row(conn, old_row)
        _insert_raw_zqtz_row(conn, newer_row)

        ensure_snapshot_natural_key_constraints(conn)

        rows = conn.execute(
            "select ingest_batch_id, market_value_native from zqtz_bond_daily_snapshot"
        ).fetchall()

        with pytest.raises(duckdb.ConstraintException):
            _insert_raw_zqtz_row(conn, {**_zqtz_row(market_value="999"), "ingest_batch_id": "ib-another"})
    finally:
        conn.close()

    assert rows == [("ib-new", Decimal("205"))]


def test_ensure_snapshot_natural_key_constraints_refuses_sentinel_collision(tmp_path) -> None:
    db_path = tmp_path / "snapshot-sentinel.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        apply_pending_migrations_on_connection(conn)
        poisoned_row = _zqtz_row(instrument_code="__moss_null__")
        _insert_raw_zqtz_row(conn, poisoned_row)

        with pytest.raises(RuntimeError, match="__moss_null__"):
            ensure_snapshot_natural_key_constraints(conn)
    finally:
        conn.close()
