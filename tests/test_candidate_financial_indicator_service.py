from __future__ import annotations

from copy import deepcopy
from datetime import date
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.core_finance.finance_metric_xlsx import (
    FinanceMetricSourceData,
    FinanceMetricXlsxError,
    LedgerObservation,
    PeriodEvidence,
)
from backend.app.schemas.candidate_financial_indicators import (
    CandidateFinancialIndicatorEnvelope,
)


def _service():
    from backend.app.services import candidate_financial_indicator_service

    return candidate_financial_indicator_service


def _periods(month: int = 5) -> tuple[PeriodEvidence, ...]:
    end = date(2026, month, 31 if month == 5 else 30)
    month_start = date(2026, month, 1)
    return (
        PeriodEvidence("ledger", "综本", "A2", "period", month_start, end),
        PeriodEvidence("daily_ytd", "年", "A2", "period", date(2026, 1, 1), end),
        PeriodEvidence("daily_month", "月", "A2", "period", month_start, end),
        PeriodEvidence("microloan_ytd", "微贷", "A2", "period", date(2026, 1, 1), end),
        PeriodEvidence("microloan_month", "微贷", "E2", "period", month_start, end),
        PeriodEvidence("microloan_ledger", "微贷", "I31", "period", month_start, end),
    )


def _ledger_row(
    *,
    row: int,
    code: str,
    ending: str,
    currency: str = "CNX",
) -> LedgerObservation:
    value = Decimal(ending)
    return LedgerObservation(
        source="main",
        sheet="综本",
        row=row,
        account_code=code,
        account_name=f"account-{code}",
        currency=currency,
        opening=value,
        debit=Decimal(0),
        credit=Decimal(0),
        ending=value,
        cell_refs=(
            ("组合科目代码", f"A{row}"),
            ("组合科目名称", f"B{row}"),
            ("币种", f"C{row}"),
            ("期初余额", f"D{row}"),
            ("本期借方", f"E{row}"),
            ("本期贷方", f"F{row}"),
            ("期末余额", f"G{row}"),
        ),
    )


def _source_data(*, month: str = "202605", currency: str = "CNX") -> FinanceMetricSourceData:
    rows = (
        _ledger_row(row=10, code="20100000001", ending="-100000000", currency=currency),
        _ledger_row(row=11, code="20100000002", ending="-200000000", currency=currency),
        _ledger_row(row=12, code="20300000001", ending="-100000000", currency=currency),
        _ledger_row(row=13, code="20400000001", ending="-100000000", currency=currency),
        _ledger_row(row=14, code="24300000001", ending="-100000000", currency=currency),
    )
    numeric_month = int(month[-2:])
    report_date = date(2026, numeric_month, 31 if numeric_month == 5 else 30)
    return FinanceMetricSourceData(
        report_month=month,
        report_date=report_date,
        ledger_sha256="a" * 64,
        daily_sha256="b" * 64,
        ledger=rows,
        averages=(),
        periods=_periods(numeric_month),
        excluded_currencies=(),
        issues=(),
        microloan_ledger_header_rows=(31,),
        selected_microloan_ledger_header_row=31,
    )


def _write_source_pair(source_dir: Path, month: str) -> None:
    (source_dir / f"总账对账{month}.xlsx").write_bytes(b"ledger-test")
    (source_dir / f"日均{month}.xlsx").write_bytes(b"daily-test")


def test_missing_fixed_source_pair_returns_strict_no_data_envelope(tmp_path: Path) -> None:
    service = _service()

    envelope = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path),
        report_month="202605",
        include_lineage=False,
        metric_id=None,
    )

    validated = CandidateFinancialIndicatorEnvelope.model_validate(envelope)
    assert validated.result.calculation_status == "no_data"
    assert validated.result.summary.metric_evaluated == 0
    assert [source.file_name for source in validated.result.sources] == [
        "总账对账202605.xlsx",
        "日均202605.xlsx",
    ]
    assert all(not source.exists for source in validated.result.sources)
    assert {gap.kind for gap in validated.result.gaps} == {"source_missing"}
    assert validated.result_meta.requested_report_date == "202605"
    readiness = validated.result.promotion_readiness
    assert readiness.status == "blocked"
    assert readiness.readiness_contract_version == "promotion-readiness-v1"
    assert len(readiness.readiness_evidence_key) == 64
    assert readiness.formal_contract_status == "missing_contract"
    assert readiness.owner_approval_required is True
    evidence_pack = readiness.evidence_pack
    assert evidence_pack.contract_version == "candidate-promotion-evidence-v1"
    assert evidence_pack.candidate_idempotency_key == validated.result.idempotency_key
    assert evidence_pack.readiness_evidence_key == readiness.readiness_evidence_key
    assert evidence_pack.owner_requirement_count == 3
    assert {item.category for item in evidence_pack.owner_requirements} == {
        "source_evidence",
        "formal_contract",
        "business_owner_approval",
    }
    assert all(item.status == "awaiting_owner_input" for item in evidence_pack.owner_requirements)
    assert all(item.submitted_value is None for item in evidence_pack.owner_requirements)
    assert "metrics" not in evidence_pack.model_dump(mode="json")
    assert "values" not in evidence_pack.model_dump(mode="json")
    assert [check.check_id for check in readiness.checks] == [
        "rule_asset",
        "source_evidence",
        "validation_controls",
        "manual_inputs",
        "account_coverage",
        "formal_contract",
    ]
    assert next(
        check for check in readiness.checks if check.check_id == "source_evidence"
    ).status == "blocked"
    assert next(
        check for check in readiness.checks if check.check_id == "validation_controls"
    ).status == "not_evaluated"


def test_formal_contract_lookup_failure_blocks_only_readiness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()

    def unavailable_contract(*, report_month: str) -> dict[str, object]:
        raise RuntimeError(f"formal registry unavailable for {report_month}")

    monkeypatch.setattr(
        service,
        "build_formal_financial_indicator_contract",
        unavailable_contract,
    )

    envelope = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path),
        report_month="202605",
        include_lineage=False,
        metric_id=None,
    )

    validated = CandidateFinancialIndicatorEnvelope.model_validate(envelope)
    assert validated.result.calculation_status == "no_data"
    readiness = validated.result.promotion_readiness
    assert readiness.formal_contract_status == "unavailable"
    formal_check = next(
        check for check in readiness.checks if check.check_id == "formal_contract"
    )
    assert formal_check.status == "blocked"
    assert formal_check.evidence_refs == ["formal-contract-registry-unavailable"]


def test_calculation_status_warns_when_source_hashes_are_not_locked() -> None:
    service = _service()

    status = service._calculation_status(
        metrics=(),
        validations=(),
        source_alignment="not_applicable",
        source_issues=(),
    )

    assert status == "warning"


def test_unlocked_source_hashes_create_visible_warning_gaps() -> None:
    service = _service()

    gaps = service._evaluated_gaps(
        metrics=(),
        validations=(),
        sources=[
            {
                "source_kind": source_kind,
                "locked_sha256": None,
                "locked_hash_match": None,
            }
            for source_kind in ("ledger", "daily")
        ],
        source_issues=(),
    )

    assert {gap["gap_id"] for gap in gaps} == {
        "source_hash_unlocked.ledger",
        "source_hash_unlocked.daily",
    }
    assert all(gap["kind"] == "source_hash" for gap in gaps)
    assert all(gap["severity"] == "warning" for gap in gaps)


def test_service_evaluates_all_metrics_but_filters_response_and_aggregates_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    _write_source_pair(tmp_path, "202605")
    monkeypatch.setattr(
        service,
        "parse_finance_metric_sources",
        lambda *_args, **_kwargs: _source_data(),
    )
    original_validate = service.validate_finance_metrics

    def validations_with_value_bearing_sample(*args, **kwargs):
        validations = list(original_validate(*args, **kwargs))
        index = next(
            index
            for index, item in enumerate(validations)
            if item.id == "recon.company_deposit"
        )
        validations[index] = replace(
            validations[index],
            passed=False,
            delta_yi=Decimal("123.45"),
            sample=("delta_yi=123.45",),
        )
        return tuple(validations)

    monkeypatch.setattr(service, "validate_finance_metrics", validations_with_value_bearing_sample)

    envelope = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path),
        report_month="202605",
        include_lineage=True,
        metric_id="balance.deposit.corporate.demand::point",
    )

    result = CandidateFinancialIndicatorEnvelope.model_validate(envelope).result
    assert result.summary.metric_evaluated == 186
    assert result.summary.metric_returned == 1
    assert result.summary.validation_evaluated == 12
    assert result.calculation_status == "warning"
    assert result.source_alignment == "not_applicable"
    metric = result.metrics[0]
    assert metric.metric_id == "balance.deposit.corporate.demand::point"
    assert metric.value == "6"
    aggregated = next(
        item
        for item in metric.lineage
        if item.lineage_type == "account" and item.code == "201"
    )
    assert aggregated.raw_yuan == "-300000000"
    assert aggregated.contribution_yi == "3"
    assert aggregated.evidence_refs == ["综本!G10", "综本!G11"]
    assert [period.evidence_id for period in result.sources[0].periods] == ["ledger"]
    assert {period.evidence_id for period in result.sources[1].periods} == {
        "daily_ytd",
        "daily_month",
        "microloan_ytd",
        "microloan_month",
        "microloan_ledger",
    }
    assert result.summary.manual_default_count == 19
    assert any(gap.kind == "manual_input" for gap in result.gaps)
    assert {gap.gap_id for gap in result.gaps} >= {
        "source_hash_unlocked.ledger",
        "source_hash_unlocked.daily",
    }
    assert all("E+" not in (metric.value or "") for metric in result.metrics)
    readiness = result.promotion_readiness
    assert readiness.status == "blocked"
    assert readiness.blocking_count >= 3
    assert readiness.candidate_idempotency_key == result.idempotency_key
    assert readiness.evidence_pack.owner_requirement_count >= 22
    assert readiness.evidence_pack.contains_metric_values is False
    assert readiness.evidence_pack.contains_formal_values is False
    assert readiness.evidence_pack.certification_effect == "none"
    assert "delta_yi=" not in readiness.evidence_pack.model_dump_json()
    assert "123.45" not in readiness.evidence_pack.model_dump_json()
    assert next(
        check for check in readiness.checks if check.check_id == "manual_inputs"
    ).status == "blocked"
    assert next(
        check for check in readiness.checks if check.check_id == "formal_contract"
    ).status == "blocked"


def test_service_uses_locked_hashes_only_for_202606(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    _write_source_pair(tmp_path, "202606")
    monkeypatch.setattr(
        service,
        "parse_finance_metric_sources",
        lambda *_args, **_kwargs: _source_data(month="202606"),
    )

    result = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path),
        report_month="202606",
        include_lineage=False,
        metric_id="income.interest.net",
    )["result"]

    assert result["source_alignment"] == "mismatch"
    assert all(source["locked_sha256"] is not None for source in result["sources"])
    assert all(source["locked_hash_match"] is False for source in result["sources"])
    assert any(gap["kind"] == "source_hash" for gap in result["gaps"])


def test_structural_parse_error_is_a_non_leaking_error_domain_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    _write_source_pair(tmp_path, "202605")

    def fail_parse(*_args, **_kwargs):
        raise FinanceMetricXlsxError(
            "secret workbook cell payload",
            code="formula_in_data_cell",
            sheet="综本",
            cell="G10",
        )

    monkeypatch.setattr(service, "parse_finance_metric_sources", fail_parse)

    envelope = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path),
        report_month="202605",
        include_lineage=False,
        metric_id=None,
    )

    validated = CandidateFinancialIndicatorEnvelope.model_validate(envelope)
    assert validated.result.calculation_status == "error"
    assert validated.result.metrics == []
    assert validated.result.validations == []
    parse_gap = next(gap for gap in validated.result.gaps if gap.kind == "source_parse")
    assert parse_gap.gap_id == "source_parse.formula_in_data_cell"
    assert "secret workbook cell payload" not in parse_gap.detail
    assert "G10" in parse_gap.detail


def test_error_severity_validation_failure_blocks_calculation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    _write_source_pair(tmp_path, "202605")
    monkeypatch.setattr(
        service,
        "parse_finance_metric_sources",
        lambda *_args, **_kwargs: _source_data(currency="CNY"),
    )

    result = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path),
        report_month="202605",
        include_lineage=False,
        metric_id="balance.deposit.corporate.demand::point",
    )["result"]

    assert result["calculation_status"] == "error"
    currency_check = next(
        item for item in result["validations"] if item["validation_id"] == "currency.cnx_only"
    )
    assert currency_check["passed"] is False
    assert any(
        gap["gap_id"] == "validation.currency.cnx_only"
        for gap in result["gaps"]
    )


def test_unknown_exact_metric_id_is_a_typed_request_error(tmp_path: Path) -> None:
    service = _service()

    with pytest.raises(
        service.CandidateFinancialIndicatorRequestError,
        match="Unknown candidate financial metric_id",
    ):
        service.candidate_financial_indicator_envelope(
            source_dir=str(tmp_path),
            report_month="202605",
            include_lineage=False,
            metric_id="income.unknown",
        )


def test_service_idempotency_key_binds_the_requested_report_month(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    _write_source_pair(tmp_path, "202605")
    _write_source_pair(tmp_path, "202606")

    def parse_for_month(*_args, requested_month: str, **_kwargs):
        return _source_data(month=requested_month)

    monkeypatch.setattr(service, "parse_finance_metric_sources", parse_for_month)

    may = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path),
        report_month="202605",
        include_lineage=False,
        metric_id=None,
    )
    june = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path),
        report_month="202606",
        include_lineage=False,
        metric_id=None,
    )

    assert may["result"]["idempotency_key"] != june["result"]["idempotency_key"]


def _revalidation_request(base: dict, *, metric_id: str | None = None):
    from backend.app.schemas.candidate_financial_indicators import (
        CandidateFinancialIndicatorRevalidationRequest,
    )

    overrides = {}
    if metric_id is not None:
        overrides[metric_id] = {
            "value_yi": "1.25",
            "submitted_evidence_refs": ["voucher:202605:approved"],
        }
    return CandidateFinancialIndicatorRevalidationRequest.model_validate(
        {
            "base_candidate_idempotency_key": base["result"]["idempotency_key"],
            "base_evidence_pack_key": base["result"]["promotion_readiness"][
                "evidence_pack"
            ]["evidence_pack_key"],
            "manual_overrides": overrides,
        }
    )


def test_revalidation_rejects_stale_candidate_and_evidence_keys(
    tmp_path: Path,
) -> None:
    service = _service()
    base = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path),
        report_month="202605",
    )
    request = _revalidation_request(base)

    for field in ("base_candidate_idempotency_key", "base_evidence_pack_key"):
        stale = request.model_copy(update={field: "9" * 64})
        with pytest.raises(service.CandidateFinancialIndicatorConflictError):
            service.revalidate_candidate_financial_indicators(
                source_dir=str(tmp_path),
                report_month="202605",
                include_lineage=False,
                metric_id=None,
                request=stale,
            )


@pytest.mark.parametrize(
    "metric_id",
    ["input.adjustment.unknown", "income.interest.net"],
)
def test_revalidation_rejects_unknown_or_non_manual_override(
    tmp_path: Path,
    metric_id: str,
) -> None:
    service = _service()
    base = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path), report_month="202605"
    )

    with pytest.raises(service.CandidateFinancialIndicatorRequestError):
        service.revalidate_candidate_financial_indicators(
            source_dir=str(tmp_path),
            report_month="202605",
            include_lineage=False,
            metric_id=None,
            request=_revalidation_request(base, metric_id=metric_id),
        )


def test_revalidation_override_changes_key_reduces_manual_blocker_and_binds_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.schemas.candidate_financial_indicators import (
        CandidateFinancialIndicatorRevalidationReceipt,
    )

    service = _service()
    _write_source_pair(tmp_path, "202605")
    monkeypatch.setattr(
        service,
        "parse_finance_metric_sources",
        lambda *_args, **_kwargs: _source_data(),
    )
    base = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path), report_month="202605"
    )
    manual_id = "input.adjustment.noninterest.r010"
    receipt = service.revalidate_candidate_financial_indicators(
        source_dir=str(tmp_path),
        report_month="202605",
        include_lineage=False,
        metric_id=None,
        request=_revalidation_request(base, metric_id=manual_id),
    )
    repeated_receipt = service.revalidate_candidate_financial_indicators(
        source_dir=str(tmp_path),
        report_month="202605",
        include_lineage=False,
        metric_id=None,
        request=_revalidation_request(base, metric_id=manual_id),
    )

    validated = CandidateFinancialIndicatorRevalidationReceipt.model_validate(receipt)
    assert validated.contract_version == "candidate-financial-indicator-revalidation-v1"
    assert validated.revalidation_effect == "none"
    assert validated.persisted is False
    assert validated.formal_use_allowed is False
    assert validated.manual_override_count == 1
    assert repeated_receipt["result"]["result"]["idempotency_key"] == receipt[
        "result"
    ]["result"]["idempotency_key"]
    assert repeated_receipt["requirement_resolution"]["resolution_key"] == receipt[
        "requirement_resolution"
    ]["resolution_key"]
    assert validated.result.result.formal_use_allowed is False
    assert validated.result.result.idempotency_key != base["result"]["idempotency_key"]
    assert validated.result.result.summary.manual_default_count == 18
    base_requirements = base["result"]["promotion_readiness"]["evidence_pack"][
        "owner_requirements"
    ]
    resolution = validated.requirement_resolution
    assert set(resolution.base_requirement_ids) == {
        item["requirement_id"] for item in base_requirements
    }
    resolved = next(
        item
        for item in resolution.requirements
        if manual_id in next(
            base_item["evidence_refs"]
            for base_item in base_requirements
            if base_item["requirement_id"] == item.requirement_id
        )
    )
    assert resolved.status == "evidence_received"
    assert resolved.submitted_evidence_refs == ["voucher:202605:approved"]
    assert "approval" in resolved.status_detail.lower()
    assert all(item.status != "verified" for item in resolution.requirements)
    assert all(
        item.status == "awaiting_owner_input"
        for item in resolution.requirements
        if item.requirement_id != resolved.requirement_id
    )
    dumped = validated.model_dump(mode="json")
    assert dumped["base_candidate_idempotency_key"] == base["result"]["idempotency_key"]
    assert dumped["base_evidence_pack_key"] == base["result"]["promotion_readiness"]["evidence_pack"]["evidence_pack_key"]
    assert "approved" not in dumped
    assert "certified" not in dumped


def test_revalidation_never_resolves_non_manual_requirement_on_evidence_ref_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.schemas.candidate_financial_indicators import (
        build_promotion_evidence_pack_key,
    )

    service = _service()
    _write_source_pair(tmp_path, "202605")
    monkeypatch.setattr(
        service,
        "parse_finance_metric_sources",
        lambda *_args, **_kwargs: _source_data(),
    )
    manual_id = "input.adjustment.noninterest.r010"
    base = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path), report_month="202605"
    )
    result = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path),
        report_month="202605",
        manual_overrides={manual_id: Decimal("1.25")},
    )
    base_pack = base["result"]["promotion_readiness"]["evidence_pack"]
    non_manual = next(
        item for item in base_pack["owner_requirements"] if item["category"] != "manual_input"
    )
    non_manual["evidence_refs"] = [manual_id]
    base_pack["evidence_pack_key"] = build_promotion_evidence_pack_key(
        evidence_pack=base_pack
    )
    envelopes = iter((base, result))
    monkeypatch.setattr(
        service,
        "candidate_financial_indicator_envelope",
        lambda **_kwargs: next(envelopes),
    )

    receipt = service.revalidate_candidate_financial_indicators(
        source_dir=str(tmp_path),
        report_month="202605",
        include_lineage=False,
        metric_id=None,
        request=_revalidation_request(base, metric_id=manual_id),
    )

    resolution = next(
        item
        for item in receipt["requirement_resolution"]["requirements"]
        if item["requirement_id"] == non_manual["requirement_id"]
    )
    assert resolution["status"] == "awaiting_owner_input"
    assert resolution["submitted_evidence_refs"] == []


@pytest.mark.parametrize(
    ("requested_metric_id", "override_metric_id"),
    [
        (
            "input.adjustment.noninterest.r019",
            "input.adjustment.noninterest.r010",
        ),
        ("income.interest.net", "input.adjustment.noninterest.r010"),
    ],
)
def test_revalidation_rejects_filtered_override_that_is_not_the_same_manual_metric(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    requested_metric_id: str,
    override_metric_id: str,
) -> None:
    service = _service()
    _write_source_pair(tmp_path, "202605")
    monkeypatch.setattr(
        service,
        "parse_finance_metric_sources",
        lambda *_args, **_kwargs: _source_data(),
    )
    base = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path),
        report_month="202605",
        metric_id=requested_metric_id,
    )

    with pytest.raises(service.CandidateFinancialIndicatorRequestError):
        service.revalidate_candidate_financial_indicators(
            source_dir=str(tmp_path),
            report_month="202605",
            include_lineage=False,
            metric_id=requested_metric_id,
            request=_revalidation_request(base, metric_id=override_metric_id),
        )


def test_revalidation_rejects_overrides_when_base_has_no_calculation(
    tmp_path: Path,
) -> None:
    service = _service()
    base = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path), report_month="202605"
    )

    with pytest.raises(service.CandidateFinancialIndicatorRequestError, match="no_data"):
        service.revalidate_candidate_financial_indicators(
            source_dir=str(tmp_path),
            report_month="202605",
            include_lineage=False,
            metric_id=None,
            request=_revalidation_request(
                base, metric_id="input.adjustment.noninterest.r010"
            ),
        )


def test_revalidation_rejects_override_without_matching_base_manual_requirement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.schemas.candidate_financial_indicators import (
        build_promotion_evidence_pack_key,
    )

    service = _service()
    _write_source_pair(tmp_path, "202605")
    monkeypatch.setattr(
        service,
        "parse_finance_metric_sources",
        lambda *_args, **_kwargs: _source_data(),
    )
    manual_id = "input.adjustment.noninterest.r010"
    base = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path), report_month="202605"
    )
    base_pack = base["result"]["promotion_readiness"]["evidence_pack"]
    base_pack["owner_requirements"] = [
        item
        for item in base_pack["owner_requirements"]
        if not (
            item["category"] == "manual_input"
            and manual_id in item["evidence_refs"]
        )
    ]
    base_pack["owner_requirement_count"] = len(base_pack["owner_requirements"])
    base_pack["evidence_pack_key"] = build_promotion_evidence_pack_key(
        evidence_pack=base_pack
    )
    monkeypatch.setattr(
        service,
        "candidate_financial_indicator_envelope",
        lambda **_kwargs: base,
    )

    with pytest.raises(service.CandidateFinancialIndicatorRequestError, match="requirement"):
        service.revalidate_candidate_financial_indicators(
            source_dir=str(tmp_path),
            report_month="202605",
            include_lineage=False,
            metric_id=None,
            request=_revalidation_request(base, metric_id=manual_id),
        )


@pytest.mark.parametrize(
    ("field", "drifted_value"),
    [
        ("report_month", "202606"),
        ("report_date", "2026-06-30"),
        ("rule_version", "qdb-finance-2026-v9.9.9"),
        ("rule_hash", "9" * 64),
        ("source_version", "sv_candidate_changed_during_revalidation"),
    ],
)
def test_revalidation_rejects_result_boundary_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    drifted_value: str,
) -> None:
    service = _service()
    base = service.candidate_financial_indicator_envelope(
        source_dir=str(tmp_path), report_month="202605"
    )
    drifted = deepcopy(base)
    drifted["result"][field] = drifted_value
    envelopes = iter((base, drifted))
    monkeypatch.setattr(
        service,
        "candidate_financial_indicator_envelope",
        lambda **_kwargs: next(envelopes),
    )

    with pytest.raises(service.CandidateFinancialIndicatorConflictError, match="changed"):
        service.revalidate_candidate_financial_indicators(
            source_dir=str(tmp_path),
            report_month="202605",
            include_lineage=False,
            metric_id=None,
            request=_revalidation_request(base),
        )
