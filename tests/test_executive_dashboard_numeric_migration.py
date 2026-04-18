"""W2.1 migration tests: schemas/executive_dashboard.py accepts both legacy str
and new Numeric shapes for governed numeric fields, and coerces legacy str into
display-only Numeric.
"""
from __future__ import annotations

from backend.app.schemas.common_numeric import Numeric
from backend.app.schemas.executive_dashboard import (
    AttributionSegment,
    ContributionRow,
    ExecutiveMetric,
    PnlAttributionPayload,
    RiskSignal,
)


class TestExecutiveMetricLegacyStr:
    def test_accepts_legacy_str_value_and_coerces_to_numeric(self) -> None:
        m = ExecutiveMetric(
            id="aum",
            label="资产规模",
            value="1,234.56 亿",
            delta="+2.34%",
            tone="positive",
            detail="...",
        )
        assert isinstance(m.value, Numeric)
        assert m.value.raw is None
        assert m.value.display == "1,234.56 亿"
        assert isinstance(m.delta, Numeric)
        assert m.delta.raw is None
        assert m.delta.display == "+2.34%"

    def test_accepts_native_numeric(self) -> None:
        value = Numeric(
            raw=123456000000.0,
            unit="yuan",
            display="1,234.56 亿",
            precision=2,
            sign_aware=False,
        )
        m = ExecutiveMetric(
            id="aum",
            label="资产规模",
            value=value,
            delta=Numeric(raw=None, unit="pct", display="无环比", precision=2, sign_aware=True),
            tone="positive",
            detail="...",
        )
        assert m.value.raw == 123456000000.0
        assert m.value.display == "1,234.56 亿"
        assert m.delta.display == "无环比"

    def test_roundtrip_json_keeps_numeric_shape(self) -> None:
        m = ExecutiveMetric(
            id="aum",
            label="资产规模",
            value="1,234.56 亿",
            delta="+2.34%",
            tone="positive",
            detail="...",
        )
        dumped = m.model_dump(mode="json")
        assert isinstance(dumped["value"], dict)
        assert set(dumped["value"].keys()) == {"raw", "unit", "display", "precision", "sign_aware"}
        assert dumped["value"]["raw"] is None
        restored = ExecutiveMetric.model_validate(dumped)
        assert restored.value.display == "1,234.56 亿"


class TestAttributionSegmentMergeAmountAndDisplay:
    def test_accepts_legacy_amount_plus_display(self) -> None:
        s = AttributionSegment(
            id="carry",
            label="Carry",
            amount=12.34,
            display_amount="+12.34 亿",
            tone="positive",
        )
        assert isinstance(s.amount, Numeric)
        assert s.amount.raw == 12.34 * 1e8
        assert s.amount.display == "+12.34 亿"
        assert s.amount.unit == "yuan"
        assert s.amount.sign_aware is True

    def test_accepts_native_numeric_amount(self) -> None:
        amount = Numeric(
            raw=1_234_000_000.0,
            unit="yuan",
            display="+12.34 亿",
            precision=2,
            sign_aware=True,
        )
        s = AttributionSegment(
            id="carry",
            label="Carry",
            amount=amount,
            tone="positive",
        )
        assert s.amount.raw == 1_234_000_000.0

    def test_serialized_shape_does_not_expose_display_amount(self) -> None:
        s = AttributionSegment(
            id="carry",
            label="Carry",
            amount=12.34,
            display_amount="+12.34 亿",
            tone="positive",
        )
        dumped = s.model_dump(mode="json")
        assert "display_amount" not in dumped
        assert isinstance(dumped["amount"], dict)
        assert dumped["amount"]["display"] == "+12.34 亿"


class TestPnlAttributionPayloadTotalNumeric:
    def test_accepts_legacy_str_total(self) -> None:
        p = PnlAttributionPayload(
            title="经营贡献拆解",
            total="+32.11 亿",
            segments=[
                AttributionSegment(
                    id="carry", label="Carry", amount=32.11, display_amount="+32.11 亿", tone="positive"
                ),
            ],
        )
        assert isinstance(p.total, Numeric)
        assert p.total.display == "+32.11 亿"
        assert p.total.raw is None


class TestRiskSignalValueNumeric:
    def test_accepts_legacy_str_value(self) -> None:
        r = RiskSignal(
            id="duration",
            label="久期风险",
            value="3.5 年",
            status="stable",
            detail="...",
        )
        assert isinstance(r.value, Numeric)
        assert r.value.display == "3.5 年"


class TestContributionRowContributionNumeric:
    def test_accepts_legacy_str_contribution(self) -> None:
        c = ContributionRow(
            id="rates",
            name="利率组",
            owner="按团队",
            contribution="+12.34 亿",
            completion=72,
            status="核心拉动",
        )
        assert isinstance(c.contribution, Numeric)
        assert c.contribution.display == "+12.34 亿"

    def test_completion_stays_int(self) -> None:
        c = ContributionRow(
            id="rates",
            name="利率组",
            owner="按团队",
            contribution="+12.34 亿",
            completion=72,
            status="核心拉动",
        )
        assert c.completion == 72
        assert isinstance(c.completion, int)


class TestBackwardCompatForExistingCallsites:
    """Legacy kwargs used by the current service layer must still succeed.

    W2.2 will switch service callsites to construct Numeric directly; until
    then these must continue to pass, otherwise the entire /ui/home/* stack
    would break.
    """

    def test_executive_overview_style_call(self) -> None:
        ExecutiveMetric(
            id="dv01",
            label="组合DV01",
            value="1,234,567",
            delta="+1.23%",
            tone="warning",
            detail="来自 bond analytics 风险快照...",
        )

    def test_pnl_attribution_style_call(self) -> None:
        PnlAttributionPayload(
            title="经营贡献拆解",
            total="+32.11 亿",
            segments=[
                AttributionSegment(id="carry", label="Carry", amount=12.1, display_amount="+12.10 亿", tone="positive"),
                AttributionSegment(id="roll", label="Roll-down", amount=-2.3, display_amount="-2.30 亿", tone="negative"),
            ],
        )
