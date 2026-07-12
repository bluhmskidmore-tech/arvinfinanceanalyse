from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.core_finance.finance_metric_xlsx import (
    FinanceMetricLedgerOnlySourceData,
    PeriodEvidence,
    SourceIssue,
)
from backend.app.services.candidate_financial_indicator_service import (
    CandidateFinancialIndicatorRequestError,
)
from backend.app.services import (
    candidate_financial_indicator_period_comparison_service as service,
)


SOURCE_DIR = Path(__file__).resolve().parents[1] / "data_input" / "pnl_总账对账-日均"
REAL_SOURCE_WORKBOOKS = (
    SOURCE_DIR / "总账对账202604.xlsx",
    SOURCE_DIR / "总账对账202605.xlsx",
    SOURCE_DIR / "总账对账202606.xlsx",
    SOURCE_DIR / "日均202605.xlsx",
)


@pytest.mark.skipif(
    not all(path.is_file() for path in REAL_SOURCE_WORKBOOKS),
    reason="requires local governed source workbooks for 202604/202605/202606",
)
def test_real_202606_period_comparison_is_partial_with_controlled_full_scope_gap() -> None:
    from backend.app.services.candidate_financial_indicator_period_comparison_service import (
        candidate_financial_indicator_period_comparison_envelope,
    )

    payload = candidate_financial_indicator_period_comparison_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
    )

    assert payload["report_month"] == "202606"
    assert payload["comparison_month"] == "202605"
    assert payload["two_month_prior"] == "202604"
    assert payload["comparison_scope"] == "ledger_only_key_metrics"
    assert payload["overall_status"] == "partial"
    assert payload["full_scope_status"] == "unavailable"
    assert payload["full_scope_reason_code"] == "missing_required_sheet"
    assert payload["full_scope_gaps"] == [
        {
            "reason_code": "missing_required_sheet",
            "source_kind": "daily",
            "month": "202605",
            "required_sheet": "微贷",
        }
    ]
    assert [item["lock_status"] for item in payload["source_periods"]] == [
        "locked_match",
        "unlocked",
        "unlocked",
    ]

    by_id = {item["metric_id"]: item for item in payload["metrics"]}
    assert sum(
        item["comparison_status"] == "comparable" for item in payload["metrics"]
    ) == 5
    assert sum(
        item["comparison_status"] == "not_comparable" for item in payload["metrics"]
    ) == 2
    interest = by_id["income.interest.net"]
    assert interest["current_source_value_yi"] == "57.3617558215"
    assert interest["previous_source_value_yi"] == "49.1381866345"
    assert interest["two_month_prior_source_value_yi"] == "38.3514959057"
    assert interest["current_value_yi"] == "8.2235691870"
    assert interest["previous_value_yi"] == "10.7866907288"
    assert interest["delta_yi"] == "-2.5631215418"
    assert interest["quality_status"] == "degraded_candidate"
    assert by_id["income.noninterest.total"]["quality_status"] == "not_comparable"
    assert by_id["income.operating.mother_bank"]["quality_status"] == "not_comparable"


@pytest.mark.parametrize(
    ("metric_evaluated", "calculation_status"),
    [(185, "warning"), (186, "error")],
)
def test_full_scope_probe_fails_closed_when_full_replay_is_incomplete_or_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    metric_evaluated: int,
    calculation_status: str,
) -> None:
    comparison_month = "202605"
    (tmp_path / f"{service.LEDGER_FILE_PREFIX}{comparison_month}.xlsx").write_bytes(
        b"ledger"
    )
    (tmp_path / f"{service.DAILY_FILE_PREFIX}{comparison_month}.xlsx").write_bytes(
        b"daily"
    )
    monkeypatch.setattr(
        service,
        "read_xlsx",
        lambda _path: SimpleNamespace(
            sheets={name: object() for name in service.REQUIRED_DAILY_SHEETS}
        ),
    )
    monkeypatch.setattr(
        service,
        "candidate_financial_indicator_envelope",
        lambda **_kwargs: {
            "result": {
                "rule_version": "qdb-finance-2026-v1.0.1",
                "rule_hash": "a" * 64,
                "calculation_status": calculation_status,
                "summary": {
                    "metric_total": 186,
                    "metric_evaluated": metric_evaluated,
                    "error_count": 1 if calculation_status == "error" else 0,
                    "validation_error_failed": 0,
                },
                "metrics": [{}] * metric_evaluated,
            }
        },
        raising=False,
    )

    result = service._probe_previous_full_scope(
        root=tmp_path,
        comparison_month=comparison_month,
        rule_version="qdb-finance-2026-v1.0.1",
        rule_hash="a" * 64,
    )

    assert result["full_scope_status"] == "unavailable"
    assert result["full_scope_reason_code"] == "full_replay_incomplete"
    assert result["full_scope_gaps"] == [
        {
            "reason_code": "full_replay_incomplete",
            "source_kind": "daily",
            "month": comparison_month,
        }
    ]


def test_period_comparison_fails_closed_for_duplicate_ledger_observations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_month = "202606"
    (tmp_path / f"{service.LEDGER_FILE_PREFIX}{report_month}.xlsx").write_bytes(
        b"ledger"
    )
    duplicate = SourceIssue(
        code="duplicate_ledger_observation",
        severity="warning",
        message="sensitive duplicate detail",
        key=("main", "10101000001", "CNX"),
        rows=(9, 10),
        cell_refs=("A9", "A10"),
    )
    source = FinanceMetricLedgerOnlySourceData(
        report_month=report_month,
        report_date=service._month_end(report_month),
        ledger_sha256="a" * 64,
        ledger=(),
        period=PeriodEvidence(
            evidence_id="ledger",
            sheet="综本",
            cell_ref="A5",
            raw_text="controlled",
            start=service._month_end(report_month).replace(day=1),
            end=service._month_end(report_month),
        ),
        issues=(duplicate,),
    )
    monkeypatch.setattr(
        service,
        "parse_finance_metric_ledger_only_source",
        lambda *_args, **_kwargs: source,
    )

    with pytest.raises(
        service.CandidateFinancialIndicatorPeriodComparisonRequestError
    ) as exc_info:
        service.candidate_financial_indicator_period_comparison_envelope(
            source_dir=str(tmp_path),
            report_month=report_month,
        )

    message = str(exc_info.value)
    assert "source quality controls failed" in message
    assert "sensitive duplicate detail" not in message
    assert str(tmp_path) not in message


@pytest.mark.parametrize(
    ("field", "changed_value"),
    [
        ("current_metric_status", "warning"),
        ("reasons", ["changed reason"]),
        ("rate_reason", "zero_denominator"),
        ("quality_status", "standard_candidate"),
    ],
)
def test_period_comparison_idempotency_binds_complete_metric_contract(
    field: str,
    changed_value: object,
) -> None:
    source_contracts = [
        {
            "month": "202606",
            "report_date": "2026-06-30",
            "ledger_file_name": "总账对账202606.xlsx",
            "ledger_sha256": "a" * 64,
            "locked_sha256": "a" * 64,
            "lock_status": "locked_match",
        }
    ]
    metrics = [
        {
            "metric_id": "income.interest.net",
            "current_metric_status": "ok",
            "reasons": [],
            "rate_reason": None,
            "quality_status": "degraded_candidate",
            "current_source_value_yi": "10",
            "previous_source_value_yi": "8",
        }
    ]
    full_scope = {
        "full_scope_status": "unavailable",
        "full_scope_reason_code": "missing_required_sheet",
        "full_scope_detail": "controlled",
        "full_scope_gaps": [],
    }
    kwargs = {
        "contract_version": "candidate-financial-indicator-period-comparison-v1",
        "months": ("202606", "202605", "202604"),
        "rule_hash": "b" * 64,
        "source_contracts": source_contracts,
        "full_scope": full_scope,
        "metrics": metrics,
    }
    baseline = service._build_period_comparison_idempotency_key(**kwargs)
    assert service._build_period_comparison_idempotency_key(**kwargs) == baseline

    changed_metrics = deepcopy(metrics)
    changed_metrics[0][field] = changed_value
    assert service._build_period_comparison_idempotency_key(
        **{**kwargs, "metrics": changed_metrics}
    ) != baseline

    changed_sources = deepcopy(source_contracts)
    changed_sources[0]["lock_status"] = "unlocked"
    assert service._build_period_comparison_idempotency_key(
        **{**kwargs, "source_contracts": changed_sources}
    ) != baseline

    changed_scope = deepcopy(full_scope)
    changed_scope["full_scope_detail"] = "changed"
    assert service._build_period_comparison_idempotency_key(
        **{**kwargs, "full_scope": changed_scope}
    ) != baseline


def _prepare_structural_full_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    comparison_month: str,
) -> None:
    (tmp_path / f"{service.LEDGER_FILE_PREFIX}{comparison_month}.xlsx").write_bytes(
        b"ledger"
    )
    (tmp_path / f"{service.DAILY_FILE_PREFIX}{comparison_month}.xlsx").write_bytes(
        b"daily"
    )
    monkeypatch.setattr(
        service,
        "read_xlsx",
        lambda _path: SimpleNamespace(
            sheets={name: object() for name in service.REQUIRED_DAILY_SHEETS}
        ),
    )


def test_full_scope_probe_does_not_swallow_unexpected_runtime_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison_month = "202605"
    _prepare_structural_full_scope(tmp_path, monkeypatch, comparison_month)

    def fail_unexpected(**_kwargs: object) -> dict[str, object]:
        raise RuntimeError("unexpected program bug")

    monkeypatch.setattr(
        service,
        "candidate_financial_indicator_envelope",
        fail_unexpected,
    )

    with pytest.raises(RuntimeError, match="unexpected program bug"):
        service._probe_previous_full_scope(
            root=tmp_path,
            comparison_month=comparison_month,
            rule_version="qdb-finance-2026-v1.0.1",
            rule_hash="a" * 64,
        )


def test_full_scope_probe_controls_known_candidate_request_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    comparison_month = "202605"
    _prepare_structural_full_scope(tmp_path, monkeypatch, comparison_month)

    def fail_known(**_kwargs: object) -> dict[str, object]:
        raise CandidateFinancialIndicatorRequestError("sensitive business detail")

    monkeypatch.setattr(
        service,
        "candidate_financial_indicator_envelope",
        fail_known,
    )

    with caplog.at_level("WARNING"):
        result = service._probe_previous_full_scope(
            root=tmp_path,
            comparison_month=comparison_month,
            rule_version="qdb-finance-2026-v1.0.1",
            rule_hash="a" * 64,
        )

    assert result["full_scope_status"] == "unavailable"
    assert result["full_scope_reason_code"] == "source_evaluation_error"
    assert "candidate full replay rejected" in caplog.text
    assert "sensitive business detail" not in caplog.text
