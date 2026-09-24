from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


UtcDatetime = Annotated[AwareDatetime, AfterValidator(_as_utc)]
LowerHexDigest = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9a-f]{64}$"),
]


class ThemeOverlayMember(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    stock_code: str = Field(min_length=1)
    stock_name: str | None = None
    theme_key: str = Field(min_length=1)
    theme_name: str = Field(min_length=1)

    @field_validator("stock_code", "theme_key", mode="before")
    @classmethod
    def _uppercase_identity(cls, value: object) -> str:
        return str(value or "").strip().upper()


class ThemeOverlayObservationAnchor(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    cache_key: str = Field(min_length=1)
    report_date: date
    created_at: UtcDatetime
    source_version: str = Field(min_length=1)
    vendor_version: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    run_id: str | None = None


class ThemeOverlayArchiveContent(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    schema_version: Literal["stock-analysis-theme-overlay-v1"] = "stock-analysis-theme-overlay-v1"
    source_kind: Literal["tushare_ths_current_overlay"] = "tushare_ths_current_overlay"
    membership_observed_at: UtcDatetime
    observed_market_date: date
    run_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    vendor_version: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    point_in_time: Literal[False] = False
    historical_use_allowed: Literal[False] = False
    members: tuple[ThemeOverlayMember, ...] = Field(min_length=1)
    observation_anchor: ThemeOverlayObservationAnchor


class ThemeOverlayArchiveDocument(ThemeOverlayArchiveContent):
    content_hash: LowerHexDigest
    lineage_hash: LowerHexDigest

    @model_validator(mode="after")
    def _hashes_match_content(self) -> Self:
        validate_theme_overlay_document_hashes(self)
        return self


class ThemeOverlayArchiveResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal[
        "completed",
        "dry_run",
        "source_unavailable",
        "empty_source",
        "source_failed",
    ]
    run_id: str = Field(min_length=1)
    observation_cache_key: str = Field(min_length=1)
    cache_key: str = Field(min_length=1)
    membership_observed_at: UtcDatetime
    observed_market_date: date | None = None
    member_count: int = 0
    content_hash: LowerHexDigest | None = None
    lineage_hash: LowerHexDigest | None = None
    archived_path: str | None = None
    manifest_written: bool = False
    message: str | None = None


def build_theme_overlay_archive_document(
    *,
    membership_observed_at: datetime,
    run_id: str,
    source_version: str,
    vendor_version: str,
    rule_version: str,
    members: Sequence[ThemeOverlayMember],
    observation_anchor: ThemeOverlayObservationAnchor,
) -> ThemeOverlayArchiveDocument:
    content = ThemeOverlayArchiveContent(
        membership_observed_at=membership_observed_at,
        observed_market_date=observation_anchor.report_date,
        run_id=run_id,
        source_version=source_version,
        vendor_version=vendor_version,
        rule_version=rule_version,
        members=tuple(members),
        observation_anchor=observation_anchor,
    )
    return ThemeOverlayArchiveDocument(
        **content.model_dump(),
        content_hash=compute_theme_overlay_content_hash(content),
        lineage_hash=compute_theme_overlay_lineage_hash(content),
    )


def compute_theme_overlay_content_hash(
    value: ThemeOverlayArchiveContent,
) -> str:
    return _canonical_hash(_content_payload(value))


def compute_theme_overlay_lineage_hash(
    value: ThemeOverlayArchiveContent,
) -> str:
    content_hash = compute_theme_overlay_content_hash(value)
    return _canonical_hash(
        {
            "content_hash": content_hash,
            "observation_anchor": value.observation_anchor.model_dump(mode="json"),
        }
    )


def validate_theme_overlay_document_hashes(
    document: ThemeOverlayArchiveDocument,
) -> None:
    expected_content_hash = compute_theme_overlay_content_hash(document)
    if document.content_hash != expected_content_hash:
        raise ValueError("content_hash mismatch")
    expected_lineage_hash = compute_theme_overlay_lineage_hash(document)
    if document.lineage_hash != expected_lineage_hash:
        raise ValueError("lineage_hash mismatch")


def canonical_theme_overlay_document_bytes(
    document: ThemeOverlayArchiveDocument,
) -> bytes:
    return _canonical_json_bytes(document.model_dump(mode="json"))


def utc_datetime_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _content_payload(
    value: ThemeOverlayArchiveContent,
) -> dict[str, object]:
    fields = {name: getattr(value, name) for name in ThemeOverlayArchiveContent.model_fields}
    content = ThemeOverlayArchiveContent.model_validate(fields)
    return content.model_dump(mode="json")


def _canonical_hash(payload: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
