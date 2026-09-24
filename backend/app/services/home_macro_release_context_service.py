from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Literal, Protocol

from backend.app.repositories.home_macro_release_context_repo import (
    HomeMacroObservation,
    HomeMacroSeriesRead,
)
from backend.app.schemas.home_macro_release_context import (
    HomeMacroCoverage,
    HomeMacroHistoryItem,
    HomeMacroMetric,
    HomeMacroReleaseContextEnvelope,
    HomeMacroReleaseContextResult,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.home_macro_period_freshness import (
    home_macro_freshness_age_days,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Repository(Protocol):
    def read_recent_observations(
        self,
        *,
        table: str,
        series_id: str,
        cutoff_date: date,
        limit: int = 2,
    ) -> HomeMacroSeriesRead: ...


class _StrictConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _SourceCandidateBinding(_StrictConfigModel):
    table: Literal["fact_choice_macro_daily", "std_external_macro_daily"]
    series_id: str = Field(min_length=1)
    vendor_name: str = Field(min_length=1)
    priority: int = Field(ge=1)


class _MetricBinding(_StrictConfigModel):
    metric_key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    cadence: Literal["monthly", "quarterly", "event"]
    display_unit: Literal["index", "pct", "persons"]
    change_unit: Literal["index_point", "pct_point", "persons", "bp"]
    precision: int = Field(ge=0, le=6)
    table: Literal["fact_choice_macro_daily", "std_external_macro_daily"] | None = None
    series_id: str | None = None
    source_candidates: list[_SourceCandidateBinding] | None = None

    @model_validator(mode="after")
    def _validate_source_shape(self) -> _MetricBinding:
        legacy_bound = self.table is not None or self.series_id is not None
        if legacy_bound and (self.table is None or self.series_id is None):
            raise ValueError("legacy source binding requires both table and series_id")
        if legacy_bound and self.source_candidates:
            raise ValueError("metric must use exactly one source binding shape")
        if self.source_candidates:
            priorities = [candidate.priority for candidate in self.source_candidates]
            if len(priorities) != len(set(priorities)):
                raise ValueError("source candidate priorities must be unique")
        return self



class _GroupBinding(_StrictConfigModel):
    indicator_key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    region: Literal["CN", "US"]
    category: Literal["activity", "inflation", "growth", "employment", "monetary_policy"]
    importance: Literal["high", "medium", "low"]
    priority: int = Field(ge=1)
    availability: Literal["automatic", "source_pending"]
    publisher_name: str | None
    vendor_name: str | None
    metrics: list[_MetricBinding] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_source_binding(self) -> _GroupBinding:
        for metric in self.metrics:
            has_legacy = metric.table is not None and metric.series_id is not None
            has_candidates = bool(metric.source_candidates)
            if self.availability == "automatic" and has_legacy == has_candidates:
                raise ValueError(
                    "automatic metrics require exactly one source binding shape"
                )
            if self.availability == "source_pending" and (
                has_legacy or has_candidates
            ):
                raise ValueError("source_pending metrics must not bind a source")
        return self


class _Bindings(_StrictConfigModel):
    rule_version: str = Field(min_length=1)
    groups: list[_GroupBinding] = Field(min_length=1)


class HomeMacroReleaseContextService:
    _FRESH_DAYS = {"monthly": 45, "quarterly": 100, "event": 45}

    def __init__(self, *, repository: _Repository, bindings_path: str | Path) -> None:
        self._repository = repository
        self._bindings = _Bindings.model_validate_json(Path(bindings_path).read_text(encoding="utf-8"))

    def build_envelope(
        self,
        *,
        window_start_date: date,
        window_end_date: date,
        history_limit: int = 8,
    ) -> HomeMacroReleaseContextEnvelope:
        if window_end_date < window_start_date:
            raise ValueError("window_end_date must be on or after window_start_date")
        if history_limit <= 0:
            raise ValueError("history_limit must be positive")

        items: list[HomeMacroHistoryItem] = []
        observations: list[HomeMacroObservation] = []
        valid_observations: list[HomeMacroObservation] = []
        warnings: list[str] = []
        for group in sorted(self._bindings.groups, key=lambda item: item.priority):
            if group.availability == "source_pending":
                item = self._pending_item(group)
            else:
                item, group_observations, group_valid = self._automatic_item(
                    group,
                    cutoff_date=window_start_date,
                )
                observations.extend(group_observations)
                valid_observations.extend(group_valid)
            items.append(item)
            if item.source_status != "ready":
                warnings.append(f"{item.indicator_key}: {item.source_status}")

        coverage = self._coverage(items)
        result = HomeMacroReleaseContextResult(
            window_start_date=window_start_date,
            window_end_date=window_end_date,
            history_items=items[:history_limit],
            coverage=coverage,
            warnings=warnings,
        )
        source_version = self._version_hash("sv_home_macro_release_context", observations, "source_version")
        vendor_version = self._version_hash("vv_home_macro_release_context", observations, "vendor_version")
        tables_used = sorted({observation.table for observation in observations})
        as_of = max((item.observation_date for item in valid_observations), default=None)
        automatic_items = [item for item in items if item.region == "CN"]
        if not valid_observations:
            vendor_status = "vendor_unavailable"
        elif any(item.source_status in {"stale", "error"} for item in automatic_items):
            vendor_status = "vendor_stale"
        else:
            vendor_status = "ok"

        envelope = build_result_envelope(
            basis="analytical",
            trace_id="tr_home_macro_release_context",
            result_kind="home.macro_release_context",
            cache_version="cv_home_macro_release_context_v1",
            source_version=source_version,
            rule_version=self._bindings.rule_version,
            result_payload=result.model_dump(mode="json"),
            quality_flag="warning" if warnings else "ok",
            vendor_version=vendor_version,
            vendor_status=vendor_status,
            fallback_mode="none",
            filters_applied={
                "window_start_date": window_start_date.isoformat(),
                "window_end_date": window_end_date.isoformat(),
                "history_limit": history_limit,
            },
            tables_used=tables_used,
            evidence_rows=len(observations),
            source_surface="market_data",
            as_of_date=as_of.isoformat() if as_of else None,
            date_basis="macro_observation_period" if as_of else None,
        )
        return HomeMacroReleaseContextEnvelope.model_validate(envelope)

    def _automatic_item(
        self,
        group: _GroupBinding,
        *,
        cutoff_date: date,
    ) -> tuple[HomeMacroHistoryItem, list[HomeMacroObservation], list[HomeMacroObservation]]:
        metrics: list[HomeMacroMetric] = []
        notes: list[str] = []
        observations: list[HomeMacroObservation] = []
        valid: list[HomeMacroObservation] = []
        statuses: list[str] = []
        current_dates: list[date] = []
        previous_dates: list[date] = []
        vendors: set[str] = set()

        selected_sources: list[str] = []
        for binding in group.metrics:
            selected_vendor: str | None = None
            if binding.source_candidates:
                (
                    metric,
                    status,
                    metric_valid,
                    metric_notes,
                    selected_vendor,
                ) = self._build_candidate_metric(binding, cutoff_date)
                observations.extend(metric_valid)
            else:
                read = self._repository.read_recent_observations(
                    table=binding.table or "",
                    series_id=binding.series_id or "",
                    cutoff_date=cutoff_date,
                    limit=2,
                )
                observations.extend(read.observations)
                metric, status, metric_valid, metric_notes = self._build_metric(
                    binding,
                    read,
                    cutoff_date,
                )
            metrics.append(metric)
            statuses.append(status)
            valid.extend(metric_valid)
            notes.extend(metric_notes)
            if metric_valid:
                current_dates.append(metric_valid[0].observation_date)
                if len(metric_valid) > 1:
                    previous_dates.append(metric_valid[1].observation_date)
                vendor = selected_vendor or self._vendor_label(
                    metric_valid[0],
                    group.vendor_name,
                )
                vendors.add(vendor)
                if selected_vendor:
                    selected_sources.append(selected_vendor)

        status = self._combine_statuses(statuses)
        observation_date = self._aligned_date(current_dates, len(metrics))
        previous_observation_date = self._aligned_date(previous_dates, len(metrics))
        if current_dates and observation_date is None:
            status = "partial" if status == "ready" else status
            notes.append("Metric observation dates are not aligned.")
        if previous_dates and previous_observation_date is None:
            status = "partial" if status == "ready" else status
            notes.append("Previous metric observation dates are not aligned.")
        if vendors:
            notes.append(f"Vendor evidence: {', '.join(sorted(vendors))}.")

        return (
            HomeMacroHistoryItem(
                indicator_key=group.indicator_key,
                title=group.title,
                region=group.region,
                category=group.category,
                importance=group.importance,
                observation_date=observation_date,
                previous_observation_date=previous_observation_date,
                reference_period=self._reference_period(observation_date, group.metrics[0].cadence),
                previous_reference_period=self._reference_period(
                    previous_observation_date,
                    group.metrics[0].cadence,
                ),
                release_date=None,
                source_status=status,
                source_name=(
                    selected_sources[0]
                    if len(metrics) == 1 and len(selected_sources) == 1
                    else group.publisher_name
                ),
                metrics=metrics,
                notes=notes,
            ),
            observations,
            valid,
        )

    def _build_candidate_metric(
        self,
        binding: _MetricBinding,
        cutoff_date: date,
    ) -> tuple[
        HomeMacroMetric,
        str,
        list[HomeMacroObservation],
        list[str],
        str | None,
    ]:
        outcomes = []
        for candidate in sorted(
            binding.source_candidates or [],
            key=lambda item: item.priority,
        ):
            read = self._repository.read_recent_observations(
                table=candidate.table,
                series_id=candidate.series_id,
                cutoff_date=cutoff_date,
                limit=2,
            )
            metric, status, valid, notes = self._build_metric(
                binding,
                read,
                cutoff_date,
            )
            outcomes.append((candidate, metric, status, valid, notes))

        valid_outcomes = [outcome for outcome in outcomes if outcome[3]]
        if not valid_outcomes:
            rejected = [
                (
                    f"Rejected vendor: {candidate.vendor_name} "
                    f"({' '.join(candidate_notes) or 'source unavailable'})."
                )
                for candidate, _, _, _, candidate_notes in outcomes
            ]
            return self._empty_metric(binding), "error", [], rejected, None

        selected = max(
            valid_outcomes,
            key=lambda outcome: (
                outcome[2] != "stale",
                outcome[3][0].observation_date,
                -outcome[0].priority,
            ),
        )
        selected_candidate, metric, status, valid, selected_notes = selected
        notes = list(selected_notes)
        notes.append(
            f"Selected vendor: {selected_candidate.vendor_name} "
            f"({selected_candidate.series_id})."
        )

        for candidate, _, candidate_status, candidate_valid, candidate_notes in outcomes:
            if candidate is selected_candidate:
                continue
            if not candidate_valid:
                reason = " ".join(candidate_notes) or "source unavailable"
            elif status != "stale" and candidate_status == "stale":
                reason = f"stale observation {candidate_valid[0].observation_date.isoformat()}"
            elif candidate_valid[0].observation_date < valid[0].observation_date:
                reason = f"older period {candidate_valid[0].observation_date.isoformat()}"
            else:
                reason = "lower source priority for the same period"
            notes.append(f"Rejected vendor: {candidate.vendor_name} ({reason}).")

        primary_priority = min(candidate.priority for candidate, *_ in outcomes)
        if selected_candidate.priority != primary_priority and status in {"ready", "partial"}:
            primary = next(
                outcome for outcome in outcomes if outcome[0].priority == primary_priority
            )
            if not primary[3]:
                fallback_reason = "Official source unavailable or invalid"
            elif primary[2] == "stale":
                fallback_reason = "Official source stale"
            else:
                fallback_reason = "Higher-priority source not selected"
            notes.append(
                f"{fallback_reason}; {selected_candidate.vendor_name} selected as fallback."
            )
            status = "fallback"

        return metric, status, valid, notes, selected_candidate.vendor_name

    def _build_metric(
        self,
        binding: _MetricBinding,
        read: HomeMacroSeriesRead,
        cutoff_date: date,
    ) -> tuple[HomeMacroMetric, str, list[HomeMacroObservation], list[str]]:
        unavailable = self._empty_metric(binding)
        if read.error or not read.observations:
            return unavailable, "error", [], [f"Source unavailable for {binding.metric_key}."]
        current = read.observations[0]
        if current.cadence != binding.cadence:
            return unavailable, "error", [], [f"Cadence mismatch for {binding.metric_key}."]
        if current.unit != binding.display_unit:
            return unavailable, "error", [], [f"Unit mismatch for {binding.metric_key}."]
        if current.value is None:
            return unavailable, "error", [], [f"Current value is null for {binding.metric_key}."]

        age_days = home_macro_freshness_age_days(
            current.observation_date,
            cutoff_date,
            cadence=binding.cadence,
        )
        stale = age_days > self._FRESH_DAYS[binding.cadence]
        previous = read.observations[1] if len(read.observations) > 1 else None
        if previous is not None and (
            previous.cadence != binding.cadence or previous.unit != binding.display_unit
        ):
            previous = None
        previous_value = previous.value if previous is not None else None
        change = (
            round(current.value - previous_value, binding.precision)
            if previous_value is not None
            else None
        )
        direction = "unavailable"
        if change is not None:
            direction = "up" if change > 0 else "down" if change < 0 else "flat"
        metric = HomeMacroMetric(
            metric_key=binding.metric_key,
            label=binding.label,
            actual_value=current.value,
            previous_value=previous_value,
            change_value=change,
            display_unit=binding.display_unit,
            change_unit=binding.change_unit,
            precision=binding.precision,
            direction=direction,
        )
        valid = [current]
        if previous is not None and previous.value is not None:
            valid.append(previous)
        if stale:
            return metric, "stale", valid, [f"Observation is {age_days} days old."]
        if previous_value is None:
            return metric, "partial", valid, [f"Previous value unavailable for {binding.metric_key}."]
        return metric, "ready", valid, []

    @staticmethod
    def _empty_metric(binding: _MetricBinding) -> HomeMacroMetric:
        return HomeMacroMetric(
            metric_key=binding.metric_key,
            label=binding.label,
            actual_value=None,
            previous_value=None,
            change_value=None,
            display_unit=binding.display_unit,
            change_unit=binding.change_unit,
            precision=binding.precision,
            direction="unavailable",
        )

    def _pending_item(self, group: _GroupBinding) -> HomeMacroHistoryItem:
        return HomeMacroHistoryItem(
            indicator_key=group.indicator_key,
            title=group.title,
            region=group.region,
            category=group.category,
            importance=group.importance,
            source_status="source_pending",
            source_name=None,
            metrics=[self._empty_metric(metric) for metric in group.metrics],
            notes=["Source integration pending; no static fallback is used."],
        )

    @staticmethod
    def _combine_statuses(statuses: list[str]) -> str:
        for status in ("error", "partial", "stale", "fallback", "ready"):
            if status in statuses:
                return status
        return "error"

    @staticmethod
    def _aligned_date(values: list[date], expected_count: int) -> date | None:
        return values[0] if len(values) == expected_count and len(set(values)) == 1 else None

    @staticmethod
    def _reference_period(value: date | None, cadence: str) -> str | None:
        if value is None:
            return None
        if cadence == "quarterly":
            return f"{value.year}-Q{((value.month - 1) // 3) + 1}"
        return value.strftime("%Y-%m")

    @staticmethod
    def _vendor_label(observation: HomeMacroObservation, configured: str | None) -> str:
        evidence = " ".join(
            value for value in (observation.vendor_name, observation.vendor_version) if value
        ).lower()
        if "tushare" in evidence:
            return "Tushare"
        if "nbs_pmi_release" in evidence:
            return "NBS official artifact"
        if "choice" in evidence:
            return "Choice"
        return configured or "unknown vendor"

    @staticmethod
    def _coverage(items: list[HomeMacroHistoryItem]) -> HomeMacroCoverage:
        counts = {status: 0 for status in ("ready", "partial", "stale", "fallback", "source_pending", "error")}
        for item in items:
            counts[item.source_status] += 1
        return HomeMacroCoverage(
            configured_count=len(items),
            ready_count=counts["ready"],
            partial_count=counts["partial"],
            stale_count=counts["stale"],
            fallback_count=counts["fallback"],
            source_pending_count=counts["source_pending"],
            error_count=counts["error"],
        )

    @staticmethod
    def _version_hash(
        prefix: str,
        observations: list[HomeMacroObservation],
        field: Literal["source_version", "vendor_version"],
    ) -> str:
        tokens = sorted(
            f"{item.table}|{item.series_id}|{item.observation_date.isoformat()}|{getattr(item, field) or ''}"
            for item in observations
        )
        if not tokens:
            return f"{prefix}_empty"
        digest = hashlib.sha256(json.dumps(tokens, separators=(",", ":")).encode()).hexdigest()[:16]
        return f"{prefix}_{digest}"
