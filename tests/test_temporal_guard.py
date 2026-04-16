from __future__ import annotations

import pytest

from tests.helpers import load_module


def test_temporal_guard_rejects_incomplete_contracts():
    module = load_module(
        "backend.app.governance.temporal_guard",
        "backend/app/governance/temporal_guard.py",
    )

    contract = module.TemporalDatasetContract(dataset_name="financial_statements")

    with pytest.raises(module.TemporalGuardError, match="incomplete"):
        module.filter_rows_as_of(
            rows=[{"statement_id": "fs-1"}],
            contract=contract,
            as_of_date="2026-03-31",
        )


def test_temporal_guard_filters_future_and_expired_rows():
    module = load_module(
        "backend.app.governance.temporal_guard",
        "backend/app/governance/temporal_guard.py",
    )

    contract = module.TemporalDatasetContract(
        dataset_name="financial_statements",
        published_at_field="published_at",
        effective_from_field="effective_from",
        effective_to_field="effective_to",
    )

    rows = [
        {
            "statement_id": "active",
            "published_at": "2026-03-15",
            "effective_from": "2026-03-01",
            "effective_to": "2026-04-01",
        },
        {
            "statement_id": "future_publish",
            "published_at": "2026-04-15",
            "effective_from": "2026-03-01",
            "effective_to": "2026-05-01",
        },
        {
            "statement_id": "expired",
            "published_at": "2026-02-01",
            "effective_from": "2026-02-01",
            "effective_to": "2026-03-01",
        },
    ]

    selected = module.filter_rows_as_of(
        rows=rows,
        contract=contract,
        as_of_date="2026-03-31",
    )

    assert [row["statement_id"] for row in selected] == ["active"]


def test_temporal_guard_fails_closed_when_no_rows_survive():
    module = load_module(
        "backend.app.governance.temporal_guard",
        "backend/app/governance/temporal_guard.py",
    )

    contract = module.TemporalDatasetContract(
        dataset_name="financial_statements",
        published_at_field="published_at",
        effective_from_field="effective_from",
        effective_to_field="effective_to",
    )

    with pytest.raises(module.TemporalGuardError, match="No point-in-time rows"):
        module.filter_rows_as_of(
            rows=[
                {
                    "statement_id": "future_only",
                    "published_at": "2026-04-15",
                    "effective_from": "2026-04-15",
                    "effective_to": "2026-05-01",
                }
            ],
            contract=contract,
            as_of_date="2026-03-31",
        )


def test_temporal_guard_respects_datetime_granularity():
    module = load_module(
        "backend.app.governance.temporal_guard",
        "backend/app/governance/temporal_guard.py",
    )

    contract = module.TemporalDatasetContract(
        dataset_name="choice_news_event",
        published_at_field="received_at",
        effective_from_field="received_at",
    )

    selected = module.filter_rows_as_of(
        rows=[
            {"event_key": "early", "received_at": "2026-04-10T10:20:00Z"},
            {"event_key": "exact", "received_at": "2026-04-10T10:21:00Z"},
            {"event_key": "late", "received_at": "2026-04-10T10:22:00Z"},
        ],
        contract=contract,
        as_of_date="2026-04-10T10:21:00Z",
    )

    assert [row["event_key"] for row in selected] == ["early", "exact"]
