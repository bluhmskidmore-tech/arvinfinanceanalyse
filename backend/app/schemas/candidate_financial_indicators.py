from __future__ import annotations

import hashlib
import json
from calendar import monthrange
from datetime import date
from typing import Annotated, Literal

from backend.app.schemas.result_meta import ResultMeta
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

DecimalString = Annotated[str, Field(pattern=r"^-?\d+(?:\.\d+)?$")]
Sha256String = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
MetricId = Annotated[
    str,
    Field(
        pattern=(
            r"^[a-z0-9][a-z0-9_.]*"
            r"(?:::(?:point|ytd_average|month_average))?$"
        )
    ),
]

EXPECTED_VALIDATION_SEVERITIES = {
    "period.same_end_date": "error",
    "period.ytd_starts_jan1": "error",
    "period.month_is_calendar_month": "error",
    "currency.cnx_only": "error",
    "ledger.balance_identity": "error",
    "ledger.duplicate_full_code": "warning",
    "rules.missing_accounts": "warning",
    "recon.company_deposit": "warning",
    "recon.retail_deposit": "warning",
    "recon.personal_loan": "warning",
    "recon.loan_interest": "warning",
    "recon.noninterest": "warning",
}
EXPECTED_PERIOD_IDS = {
    "ledger",
    "daily_ytd",
    "daily_month",
    "microloan_ytd",
    "microloan_month",
    "microloan_ledger",
}


class _StrictCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CandidateFinancialIndicatorPeriod(_StrictCandidateModel):
    evidence_id: Literal[
        "ledger",
        "daily_ytd",
        "daily_month",
        "microloan_ytd",
        "microloan_month",
        "microloan_ledger",
    ]
    start: date
    end: date
    source_cell: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_period_order(self) -> CandidateFinancialIndicatorPeriod:
        if self.start > self.end:
            raise ValueError("period start must not be after end")
        return self


class CandidateFinancialIndicatorSource(_StrictCandidateModel):
    source_kind: Literal["ledger", "daily"]
    file_name: str = Field(min_length=1)
    exists: bool
    sha256: Sha256String | None
    locked_sha256: Sha256String | None
    locked_hash_match: bool | None
    sheets: list[str]
    periods: list[CandidateFinancialIndicatorPeriod]

    @model_validator(mode="after")
    def validate_source_evidence(self) -> CandidateFinancialIndicatorSource:
        if self.exists != (self.sha256 is not None):
            raise ValueError("existing source requires sha256 and missing source forbids it")
        if not self.exists and (self.sheets or self.periods):
            raise ValueError("missing source cannot expose sheet or period evidence")
        if self.locked_sha256 is None:
            if self.locked_hash_match is not None:
                raise ValueError("locked_hash_match requires locked_sha256")
        elif self.sha256 is None:
            if self.locked_hash_match is not None:
                raise ValueError("missing source cannot claim locked_hash_match")
        elif self.locked_hash_match != (self.sha256 == self.locked_sha256):
            raise ValueError("locked_hash_match must equal the SHA-256 comparison")
        return self


class CandidateFinancialIndicatorAccountLineage(_StrictCandidateModel):
    lineage_type: Literal["account"]
    source: Literal["main", "microloan", "ledger", "microloan_ledger"]
    basis: Literal["point", "ytd_average", "month_average", "cumulative"] | None
    level: Literal["l1", "l2", "l3", "full"]
    code: str = Field(pattern=r"^[0-9]+$")
    weight: DecimalString
    observed: bool
    raw_yuan: DecimalString
    contribution_yi: DecimalString
    evidence_refs: list[str]


class CandidateFinancialIndicatorMetricLineage(_StrictCandidateModel):
    lineage_type: Literal["metric"]
    metric_id: MetricId
    weight: DecimalString
    metric_value_yi: DecimalString | None
    contribution_yi: DecimalString | None
    dependency_status: Literal["ok", "warning", "manual_default", "error"]


class CandidateFinancialIndicatorManualLineage(_StrictCandidateModel):
    lineage_type: Literal["manual"]
    supplied: bool
    value_yi: DecimalString


CandidateFinancialIndicatorLineage = Annotated[
    CandidateFinancialIndicatorAccountLineage
    | CandidateFinancialIndicatorMetricLineage
    | CandidateFinancialIndicatorManualLineage,
    Field(discriminator="lineage_type"),
]


class CandidateFinancialIndicatorMetric(_StrictCandidateModel):
    metric_id: MetricId
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    basis: Literal["point", "ytd_average", "month_average", "cumulative"]
    unit: Literal["亿元"]
    value: DecimalString | None
    status: Literal["ok", "warning", "manual_default", "error"]
    reasons: list[str]
    lineage: list[CandidateFinancialIndicatorLineage]

    @model_validator(mode="after")
    def validate_metric_status(self) -> CandidateFinancialIndicatorMetric:
        if self.status == "ok" and self.reasons:
            raise ValueError("ok metric cannot carry warning reasons")
        if self.status != "ok" and not self.reasons:
            raise ValueError("non-ok metric requires at least one reason")
        if self.status != "error" and self.value is None:
            raise ValueError("non-error metric requires a decimal value")
        return self


class CandidateFinancialIndicatorValidation(_StrictCandidateModel):
    validation_id: str = Field(pattern=r"^[a-z0-9_.]+$")
    severity: Literal["error", "warning"]
    passed: bool
    message: str = Field(min_length=1)
    delta_yi: DecimalString | None
    sample: list[str]


class CandidateFinancialIndicatorGap(_StrictCandidateModel):
    gap_id: str = Field(pattern=r"^[a-z0-9_.:-]+$")
    severity: Literal["error", "warning", "info"]
    kind: Literal[
        "source_missing",
        "source_hash",
        "source_parse",
        "validation",
        "missing_account",
        "manual_input",
        "calculation",
    ]
    title: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    metric_ids: list[MetricId]


class CandidateFinancialIndicatorSummary(_StrictCandidateModel):
    metric_total: Literal[186]
    metric_evaluated: int = Field(ge=0, le=186)
    metric_returned: int = Field(ge=0, le=186)
    ok_count: int = Field(ge=0, le=186)
    warning_count: int = Field(ge=0, le=186)
    manual_default_count: int = Field(ge=0, le=186)
    error_count: int = Field(ge=0, le=186)
    validation_total: Literal[12]
    validation_evaluated: int = Field(ge=0, le=12)
    validation_passed: int = Field(ge=0, le=12)
    validation_warning_failed: int = Field(ge=0, le=12)
    validation_error_failed: int = Field(ge=0, le=12)

    @model_validator(mode="after")
    def validate_counts(self) -> CandidateFinancialIndicatorSummary:
        metric_status_total = (
            self.ok_count
            + self.warning_count
            + self.manual_default_count
            + self.error_count
        )
        if metric_status_total != self.metric_evaluated:
            raise ValueError("metric status counts must equal metric_evaluated")
        validation_status_total = (
            self.validation_passed
            + self.validation_warning_failed
            + self.validation_error_failed
        )
        if validation_status_total != self.validation_evaluated:
            raise ValueError("validation status counts must equal validation_evaluated")
        return self


PromotionCheckId = Literal[
    "rule_asset",
    "source_evidence",
    "validation_controls",
    "manual_inputs",
    "account_coverage",
    "formal_contract",
]
EXPECTED_PROMOTION_CHECK_IDS = (
    "rule_asset",
    "source_evidence",
    "validation_controls",
    "manual_inputs",
    "account_coverage",
    "formal_contract",
)


def _json_date_default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"unsupported promotion evidence value: {type(value).__name__}")


def build_promotion_readiness_evidence_key(
    *,
    candidate_idempotency_key: str,
    formal_contract_status: str,
    checks: list[dict[str, object]],
) -> str:
    evidence_payload = {
        "readiness_contract_version": "promotion-readiness-v1",
        "candidate_idempotency_key": candidate_idempotency_key,
        "formal_contract_status": formal_contract_status,
        "checks": checks,
    }
    return hashlib.sha256(
        json.dumps(
            evidence_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def build_promotion_evidence_pack_key(
    *,
    evidence_pack: dict[str, object],
) -> str:
    evidence_payload = dict(evidence_pack)
    evidence_payload.pop("evidence_pack_key", None)
    return hashlib.sha256(
        json.dumps(
            evidence_payload,
            default=_json_date_default,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class CandidateFinancialIndicatorPromotionCheck(_StrictCandidateModel):
    check_id: PromotionCheckId
    label: str = Field(min_length=1)
    status: Literal["passed", "blocked", "not_evaluated"]
    blocking: bool
    summary: str = Field(min_length=1)
    evidence_refs: list[str]
    action: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_blocking_status(self) -> CandidateFinancialIndicatorPromotionCheck:
        if self.status == "passed" and self.blocking:
            raise ValueError("passed promotion check cannot be blocking")
        if self.status != "passed" and not self.blocking:
            raise ValueError("non-passed promotion check must remain blocking")
        return self


PromotionOwnerRequirementCategory = Literal[
    "source_evidence",
    "validation_control",
    "manual_input",
    "account_coverage",
    "formal_contract",
    "business_owner_approval",
]


class CandidateFinancialIndicatorPromotionOwnerRequirement(_StrictCandidateModel):
    requirement_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    category: PromotionOwnerRequirementCategory
    status: Literal["awaiting_owner_input"]
    submitted_value: Literal[None]
    evidence_refs: list[str]
    required_evidence: list[str] = Field(min_length=1)
    action: str = Field(min_length=1)


class CandidateFinancialIndicatorPromotionEvidencePack(_StrictCandidateModel):
    contract_version: Literal["candidate-promotion-evidence-v1"]
    evidence_pack_key: Sha256String
    report_month: str = Field(pattern=r"^[0-9]{4}(?:0[1-9]|1[0-2])$")
    report_date: date
    rule_version: Literal["qdb-finance-2026-v1.0.0", "qdb-finance-2026-v1.0.1"]
    rule_hash: Sha256String
    source_version: str = Field(min_length=1)
    source_alignment: Literal["matched", "mismatch", "not_applicable", "incomplete"]
    candidate_idempotency_key: Sha256String
    readiness_contract_version: Literal["promotion-readiness-v1"]
    readiness_evidence_key: Sha256String
    metric_status: Literal["candidate"]
    formal_use_allowed: Literal[False]
    owner_approval_required: Literal[True]
    contains_metric_values: Literal[False]
    contains_formal_values: Literal[False]
    certification_effect: Literal["none"]
    blocking_count: int = Field(ge=0, le=6)
    check_total: Literal[6]
    formal_contract_status: Literal["missing_contract", "contract_fixture", "unavailable"]
    formal_sample_id: str = Field(min_length=1)
    formal_source_version: str = Field(min_length=1)
    formal_release_gate_status: str | None
    formal_metric_count: int = Field(ge=0)
    checks: list[CandidateFinancialIndicatorPromotionCheck]
    owner_requirement_count: int = Field(ge=1)
    owner_requirements: list[CandidateFinancialIndicatorPromotionOwnerRequirement]
    outcome_status: Literal["blocked", "awaiting_owner_approval"]

    @model_validator(mode="after")
    def validate_evidence_pack(self) -> CandidateFinancialIndicatorPromotionEvidencePack:
        if tuple(check.check_id for check in self.checks) != EXPECTED_PROMOTION_CHECK_IDS:
            raise ValueError("evidence pack checks must be complete and in contract order")
        if self.blocking_count != sum(check.blocking for check in self.checks):
            raise ValueError("evidence pack blocking_count must match checks")
        requirement_ids = [item.requirement_id for item in self.owner_requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("evidence pack owner requirement IDs must be unique")
        if self.owner_requirement_count != len(self.owner_requirements):
            raise ValueError("owner_requirement_count must match owner_requirements")
        if self.outcome_status == "blocked" and self.blocking_count == 0:
            raise ValueError("blocked evidence pack must have a blocking check")
        if self.outcome_status == "awaiting_owner_approval" and self.blocking_count != 0:
            raise ValueError("awaiting owner approval requires zero blocking checks")
        expected_key = build_promotion_evidence_pack_key(
            evidence_pack=self.model_dump(mode="json", exclude={"evidence_pack_key"})
        )
        if self.evidence_pack_key != expected_key:
            raise ValueError("evidence_pack_key must match promotion evidence pack")
        return self


class CandidateFinancialIndicatorPromotionReadiness(_StrictCandidateModel):
    readiness_contract_version: Literal["promotion-readiness-v1"]
    readiness_evidence_key: Sha256String
    status: Literal["blocked", "review_required"]
    blocking_count: int = Field(ge=0, le=6)
    check_total: Literal[6]
    candidate_idempotency_key: Sha256String
    formal_contract_status: Literal["missing_contract", "contract_fixture", "unavailable"]
    formal_use_allowed: Literal[False]
    owner_approval_required: Literal[True]
    next_action: str = Field(min_length=1)
    checks: list[CandidateFinancialIndicatorPromotionCheck]
    evidence_pack: CandidateFinancialIndicatorPromotionEvidencePack

    @model_validator(mode="after")
    def validate_readiness(self) -> CandidateFinancialIndicatorPromotionReadiness:
        check_ids = tuple(check.check_id for check in self.checks)
        if check_ids != EXPECTED_PROMOTION_CHECK_IDS:
            raise ValueError("promotion checks must be complete and in contract order")
        blocking_count = sum(check.blocking for check in self.checks)
        if self.blocking_count != blocking_count:
            raise ValueError("blocking_count must match blocking promotion checks")
        if (self.status == "blocked") != (blocking_count > 0):
            raise ValueError("promotion readiness status must match blocking_count")
        expected_evidence_key = build_promotion_readiness_evidence_key(
            candidate_idempotency_key=self.candidate_idempotency_key,
            formal_contract_status=self.formal_contract_status,
            checks=[
                {
                    "check_id": check.check_id,
                    "status": check.status,
                    "evidence_refs": check.evidence_refs,
                }
                for check in self.checks
            ],
        )
        if self.readiness_evidence_key != expected_evidence_key:
            raise ValueError("readiness_evidence_key must match promotion evidence")
        if self.evidence_pack.candidate_idempotency_key != self.candidate_idempotency_key:
            raise ValueError("evidence pack must bind the candidate idempotency key")
        if self.evidence_pack.readiness_evidence_key != self.readiness_evidence_key:
            raise ValueError("evidence pack must bind the readiness evidence key")
        if self.evidence_pack.readiness_contract_version != self.readiness_contract_version:
            raise ValueError("evidence pack must bind the readiness contract version")
        if self.evidence_pack.formal_contract_status != self.formal_contract_status:
            raise ValueError("evidence pack formal contract status must match readiness")
        if self.evidence_pack.blocking_count != self.blocking_count:
            raise ValueError("evidence pack blocking count must match readiness")
        if self.evidence_pack.checks != self.checks:
            raise ValueError("evidence pack checks must match readiness checks")
        return self


class CandidateFinancialIndicatorSourceVersionImpact(_StrictCandidateModel):
    contract_version: Literal["candidate-source-version-impact-v1"]
    impact_asset_sha256: Sha256String
    status: Literal[
        "numerically_unchanged",
        "numeric_digest_mismatch",
        "comparison_incomplete",
    ]
    comparison_basis: Literal["canonical_decimal_value"]
    report_month: str = Field(pattern=r"^[0-9]{4}(?:0[1-9]|1[0-2])$")
    reference_rule_version: Literal["qdb-finance-2026-v1.0.0"]
    current_rule_version: Literal["qdb-finance-2026-v1.0.1"]
    reference_result_sha256: Sha256String
    reference_ledger_sha256: Sha256String
    current_ledger_sha256: Sha256String
    daily_sha256: Sha256String
    metric_total: Literal[186]
    compared_metric_count: int = Field(ge=0, le=186)
    reference_numeric_digest: Sha256String
    current_numeric_digest: Sha256String
    numeric_changed_count: int | None = Field(default=None, ge=0, le=186)
    serialization_only_count: int = Field(ge=0, le=186)
    serialization_only_metric_ids: list[MetricId]
    formal_use_allowed: Literal[False]
    certification_effect: Literal["none"]

    @model_validator(mode="after")
    def validate_impact(self) -> CandidateFinancialIndicatorSourceVersionImpact:
        if self.serialization_only_count != len(self.serialization_only_metric_ids):
            raise ValueError("serialization_only_count must match metric IDs")
        if len(self.serialization_only_metric_ids) != len(
            set(self.serialization_only_metric_ids)
        ):
            raise ValueError("serialization-only metric IDs must be unique")
        if self.status == "numerically_unchanged":
            if self.compared_metric_count != self.metric_total:
                raise ValueError("unchanged impact must compare every metric")
            if self.numeric_changed_count != 0:
                raise ValueError("unchanged impact must have zero numeric changes")
            if self.current_numeric_digest != self.reference_numeric_digest:
                raise ValueError("unchanged impact digests must match")
        elif self.status == "numeric_digest_mismatch":
            if self.compared_metric_count != self.metric_total:
                raise ValueError("mismatched impact must compare every metric")
            if self.numeric_changed_count is not None:
                raise ValueError("mismatched impact cannot infer a numeric change count")
            if self.current_numeric_digest == self.reference_numeric_digest:
                raise ValueError("mismatched impact digests must differ")
            if self.serialization_only_count != 0:
                raise ValueError("mismatched impact cannot claim serialization-only metrics")
        else:
            if self.compared_metric_count >= self.metric_total:
                raise ValueError("incomplete impact must omit at least one metric")
            if self.numeric_changed_count is not None:
                raise ValueError("incomplete impact cannot infer a numeric change count")
            if self.serialization_only_count != 0:
                raise ValueError("incomplete impact cannot claim serialization-only metrics")
        return self


class CandidateFinancialIndicatorPayload(_StrictCandidateModel):
    report_month: str = Field(pattern=r"^[0-9]{4}(?:0[1-9]|1[0-2])$")
    report_date: date
    currency: Literal["CNX"]
    basis: Literal["ledger"]
    metric_status: Literal["candidate"]
    formal_use_allowed: Literal[False]
    calculation_status: Literal["ready", "warning", "error", "no_data"]
    source_alignment: Literal["matched", "mismatch", "not_applicable", "incomplete"]
    source_version: str = Field(min_length=1)
    rule_version: Literal["qdb-finance-2026-v1.0.0", "qdb-finance-2026-v1.0.1"]
    rule_hash: Sha256String
    idempotency_key: Sha256String
    requested_metric_id: MetricId | None
    include_lineage: bool
    source_version_impact: CandidateFinancialIndicatorSourceVersionImpact | None = None
    promotion_readiness: CandidateFinancialIndicatorPromotionReadiness
    sources: list[CandidateFinancialIndicatorSource]
    summary: CandidateFinancialIndicatorSummary
    metrics: list[CandidateFinancialIndicatorMetric]
    validations: list[CandidateFinancialIndicatorValidation]
    gaps: list[CandidateFinancialIndicatorGap]

    @model_validator(mode="after")
    def validate_payload_coherence(self) -> CandidateFinancialIndicatorPayload:
        year = int(self.report_month[:4])
        month = int(self.report_month[4:])
        expected_date = date(year, month, monthrange(year, month)[1])
        if self.report_date != expected_date:
            raise ValueError("report_date must equal the requested report month end")
        impact = self.source_version_impact
        if impact is not None:
            if impact.report_month != self.report_month:
                raise ValueError("source impact report_month must bind the payload")
            if impact.current_rule_version != self.rule_version:
                raise ValueError("source impact rule_version must bind the payload")
            source_hashes = {
                source.source_kind: source.sha256
                for source in self.sources
                if source.exists
            }
            if (
                len(source_hashes) != 2
                or impact.current_ledger_sha256 != source_hashes.get("ledger")
                or impact.daily_sha256 != source_hashes.get("daily")
            ):
                raise ValueError("source impact source hashes must bind the payload")
            if self.source_alignment != "matched" or not all(
                source.locked_hash_match is True for source in self.sources
            ):
                raise ValueError("source impact requires matched locked sources")
        if self.promotion_readiness.candidate_idempotency_key != self.idempotency_key:
            raise ValueError("promotion readiness must bind the candidate idempotency key")
        evidence_pack = self.promotion_readiness.evidence_pack
        payload_bindings = (
            (evidence_pack.report_month, self.report_month, "report_month"),
            (evidence_pack.report_date, self.report_date, "report_date"),
            (evidence_pack.rule_version, self.rule_version, "rule_version"),
            (evidence_pack.rule_hash, self.rule_hash, "rule_hash"),
            (evidence_pack.source_version, self.source_version, "source_version"),
            (evidence_pack.source_alignment, self.source_alignment, "source_alignment"),
            (evidence_pack.metric_status, self.metric_status, "metric_status"),
            (evidence_pack.formal_use_allowed, self.formal_use_allowed, "formal_use_allowed"),
        )
        for pack_value, payload_value, field_name in payload_bindings:
            if pack_value != payload_value:
                raise ValueError(f"evidence pack must bind payload {field_name}")

        checks = {
            check.check_id: check for check in self.promotion_readiness.checks
        }
        contradictions: list[str] = []
        sources_locked = bool(self.sources) and all(
            source.exists and source.locked_hash_match is True for source in self.sources
        )
        period_controls_passed = all(
            validation.passed
            for validation in self.validations
            if validation.validation_id.startswith("period.")
        ) and sum(
            validation.validation_id.startswith("period.")
            for validation in self.validations
        ) == 3
        if checks["source_evidence"].status == "passed" and not (
            self.source_alignment == "matched"
            and sources_locked
            and period_controls_passed
        ):
            contradictions.append("source_evidence")

        validations_complete = (
            self.summary.validation_evaluated == self.summary.validation_total
            and self.summary.validation_passed == self.summary.validation_total
            and all(validation.passed for validation in self.validations)
        )
        if checks["validation_controls"].status == "passed" and not validations_complete:
            contradictions.append("validation_controls")
        if checks["manual_inputs"].status == "passed" and self.summary.manual_default_count > 0:
            contradictions.append("manual_inputs")

        missing_account_control = next(
            (
                validation
                for validation in self.validations
                if validation.validation_id == "rules.missing_accounts"
            ),
            None,
        )
        if checks["account_coverage"].status == "passed" and (
            missing_account_control is None or not missing_account_control.passed
        ):
            contradictions.append("account_coverage")
        if (
            checks["formal_contract"].status == "passed"
            and self.promotion_readiness.formal_contract_status != "contract_fixture"
        ):
            contradictions.append("formal_contract")
        if contradictions:
            raise ValueError(
                "promotion readiness contradicts payload evidence: "
                + ", ".join(contradictions)
            )

        metric_ids = [metric.metric_id for metric in self.metrics]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("returned metric IDs must be unique")
        if self.summary.metric_returned != len(self.metrics):
            raise ValueError("metric_returned must equal the metrics list length")
        if self.requested_metric_id is not None and metric_ids not in (
            [],
            [self.requested_metric_id],
        ):
            raise ValueError("requested_metric_id must match the only returned metric")
        if (
            self.requested_metric_id is None
            and self.summary.metric_evaluated == 186
            and self.summary.metric_returned != 186
        ):
            raise ValueError("unfiltered evaluated result must return all 186 metrics")
        if not self.include_lineage and any(metric.lineage for metric in self.metrics):
            raise ValueError("lineage must be empty when include_lineage is false")

        validation_ids = [item.validation_id for item in self.validations]
        if len(validation_ids) != len(set(validation_ids)):
            raise ValueError("returned validation IDs must be unique")
        if self.summary.validation_evaluated and len(self.validations) != 12:
            raise ValueError("evaluated result must return all 12 validations")
        if self.summary.validation_evaluated and {
            item.validation_id: item.severity for item in self.validations
        } != EXPECTED_VALIDATION_SEVERITIES:
            raise ValueError("validation IDs and severities must match the rule contract")
        if self.summary.validation_evaluated:
            validation_counts = (
                sum(item.passed for item in self.validations),
                sum(
                    not item.passed and item.severity == "warning"
                    for item in self.validations
                ),
                sum(
                    not item.passed and item.severity == "error"
                    for item in self.validations
                ),
            )
            expected_validation_counts = (
                self.summary.validation_passed,
                self.summary.validation_warning_failed,
                self.summary.validation_error_failed,
            )
            if validation_counts != expected_validation_counts:
                raise ValueError(
                    "validation summary counts must match returned validations"
                )

        source_kinds = [source.source_kind for source in self.sources]
        if self.summary.metric_evaluated and (
            len(source_kinds) != 2 or set(source_kinds) != {"ledger", "daily"}
        ):
            raise ValueError("evaluated result requires one ledger and one daily source")
        period_ids = [
            period.evidence_id for source in self.sources for period in source.periods
        ]
        if self.summary.metric_evaluated and (
            len(period_ids) != 6 or set(period_ids) != EXPECTED_PERIOD_IDS
        ):
            raise ValueError("evaluated result requires six unique source period records")

        expected_alignment = _source_alignment(self.sources)
        if self.source_alignment != expected_alignment:
            raise ValueError("source_alignment must match source hash evidence")

        if self.calculation_status in {"ready", "warning"}:
            if self.summary.metric_evaluated != 186:
                raise ValueError("ready or warning calculation must evaluate 186 metrics")
            if self.summary.validation_evaluated != 12:
                raise ValueError("ready or warning calculation must evaluate 12 validations")
        if self.calculation_status == "no_data" and (
            self.summary.metric_evaluated or self.metrics
        ):
            raise ValueError("no_data calculation cannot expose evaluated metrics")
        if self.calculation_status == "ready":
            if self.source_alignment == "not_applicable":
                raise ValueError("ready calculation requires locked source hashes")
            has_non_ok_metric = any(
                (
                    self.summary.warning_count,
                    self.summary.manual_default_count,
                    self.summary.error_count,
                )
            )
            has_failed_validation = any(
                (
                    self.summary.validation_warning_failed,
                    self.summary.validation_error_failed,
                )
            )
            if (
                self.gaps
                or has_non_ok_metric
                or has_failed_validation
                or self.source_alignment in {"mismatch", "incomplete"}
            ):
                raise ValueError("ready calculation cannot carry visible gaps or warnings")
        elif not self.gaps:
            raise ValueError("non-ready calculation requires at least one visible gap")
        return self


def _source_alignment(
    sources: list[CandidateFinancialIndicatorSource],
) -> Literal["matched", "mismatch", "not_applicable", "incomplete"]:
    if not sources or any(not source.exists for source in sources):
        return "incomplete"
    comparisons = [
        source.locked_hash_match
        for source in sources
        if source.locked_sha256 is not None
    ]
    if not comparisons:
        return "not_applicable"
    if any(match is False for match in comparisons):
        return "mismatch"
    return "matched"


class CandidateFinancialIndicatorFilters(_StrictCandidateModel):
    report_month: str = Field(pattern=r"^[0-9]{4}(?:0[1-9]|1[0-2])$")
    include_lineage: bool
    metric_id: MetricId | None


class CandidateFinancialIndicatorResultMeta(ResultMeta):
    model_config = ConfigDict(extra="forbid")

    basis: Literal["ledger"] = "ledger"
    result_kind: Literal[
        "ledger_pnl.candidate_financial_indicators"
    ] = "ledger_pnl.candidate_financial_indicators"
    formal_use_allowed: Literal[False] = False
    amount_currency_basis: Literal["CNX"] = "CNX"
    amount_currency_basis_note: str = Field(min_length=1)
    vendor_version: Literal["vv_none"] = "vv_none"
    quality_flag: Literal["ok", "warning", "error"] = "ok"
    vendor_status: Literal["ok"] = "ok"
    fallback_mode: Literal["none"] = "none"
    requested_report_date: str = Field(pattern=r"^[0-9]{4}(?:0[1-9]|1[0-2])$")
    resolved_report_date: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    scenario_flag: Literal[False] = False
    as_of_date: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    date_basis: Literal["report_month_end"] = "report_month_end"
    fallback_date: Literal[None] = None
    filters_applied: CandidateFinancialIndicatorFilters
    evidence_rows: int = Field(ge=0)
    source_surface: Literal[None] = None


class CandidateFinancialIndicatorEnvelope(_StrictCandidateModel):
    result_meta: CandidateFinancialIndicatorResultMeta
    result: CandidateFinancialIndicatorPayload

    @model_validator(mode="after")
    def validate_envelope_coherence(self) -> CandidateFinancialIndicatorEnvelope:
        if self.result_meta.rule_version != self.result.rule_version:
            raise ValueError("result_meta and result rule_version must match")
        if self.result_meta.source_version != self.result.source_version:
            raise ValueError("result_meta and result source_version must match")
        if self.result_meta.cache_key != self.result.idempotency_key:
            raise ValueError("cache_key must equal the result idempotency_key")
        filters = self.result_meta.filters_applied
        if (
            filters.report_month != self.result.report_month
            or filters.include_lineage != self.result.include_lineage
            or filters.metric_id != self.result.requested_metric_id
        ):
            raise ValueError("result_meta filters must match the result request boundary")
        if (
            self.result_meta.requested_report_date != self.result.report_month
            or self.result_meta.resolved_report_date
            != self.result.report_date.isoformat()
            or self.result_meta.as_of_date != self.result.report_date.isoformat()
        ):
            raise ValueError("result_meta dates must match the result report boundary")
        return self


EvidenceRef = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class CandidateFinancialIndicatorManualOverride(_StrictCandidateModel):
    value_yi: DecimalString
    submitted_evidence_refs: list[EvidenceRef] = Field(min_length=1)


class CandidateFinancialIndicatorRevalidationRequest(_StrictCandidateModel):
    base_candidate_idempotency_key: Sha256String
    base_evidence_pack_key: Sha256String
    manual_overrides: dict[MetricId, CandidateFinancialIndicatorManualOverride]


class CandidateFinancialIndicatorRequirementResolutionItem(_StrictCandidateModel):
    requirement_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    status: Literal[
        "awaiting_owner_input",
        "evidence_received",
        "validation_failed",
        "verified",
    ]
    status_detail: str = Field(min_length=1)
    submitted_evidence_refs: list[EvidenceRef]
    validation_evidence_refs: list[EvidenceRef]


def build_candidate_requirement_resolution_key(
    *, requirement_resolution: dict[str, object]
) -> str:
    payload = dict(requirement_resolution)
    payload.pop("resolution_key", None)
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class CandidateFinancialIndicatorRequirementResolution(_StrictCandidateModel):
    contract_version: Literal["candidate-promotion-resolution-v1"]
    resolution_key: Sha256String
    base_evidence_pack_key: Sha256String
    result_evidence_pack_key: Sha256String
    base_requirement_ids: list[str] = Field(min_length=1)
    requirements: list[CandidateFinancialIndicatorRequirementResolutionItem] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_resolution(self) -> CandidateFinancialIndicatorRequirementResolution:
        requirement_ids = [item.requirement_id for item in self.requirements]
        if len(self.base_requirement_ids) != len(set(self.base_requirement_ids)):
            raise ValueError("base requirement IDs must be unique")
        if requirement_ids != self.base_requirement_ids:
            raise ValueError("resolution must cover base requirements in contract order")
        expected_key = build_candidate_requirement_resolution_key(
            requirement_resolution=self.model_dump(
                mode="json", exclude={"resolution_key"}
            )
        )
        if self.resolution_key != expected_key:
            raise ValueError("resolution_key must bind the complete resolution")
        return self


class CandidateFinancialIndicatorRevalidationReceipt(_StrictCandidateModel):
    contract_version: Literal["candidate-financial-indicator-revalidation-v1"]
    revalidation_effect: Literal["none"]
    persisted: Literal[False]
    formal_use_allowed: Literal[False]
    base_candidate_idempotency_key: Sha256String
    base_evidence_pack_key: Sha256String
    manual_override_count: int = Field(ge=0)
    requirement_resolution: CandidateFinancialIndicatorRequirementResolution
    result: CandidateFinancialIndicatorEnvelope

    @model_validator(mode="after")
    def validate_receipt(self) -> CandidateFinancialIndicatorRevalidationReceipt:
        resolution = self.requirement_resolution
        if resolution.base_evidence_pack_key != self.base_evidence_pack_key:
            raise ValueError("resolution must bind the base evidence pack key")
        result_pack_key = (
            self.result.result.promotion_readiness.evidence_pack.evidence_pack_key
        )
        if resolution.result_evidence_pack_key != result_pack_key:
            raise ValueError("resolution must bind the result evidence pack key")
        return self
