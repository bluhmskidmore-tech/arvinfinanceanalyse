"""executive_verdict：首屏 Pyramid 定调逻辑（确定性）。"""

from __future__ import annotations

from backend.app.schemas.common_numeric import Numeric
from backend.app.schemas.executive_dashboard import ExecutiveMetric, OverviewPayload
from backend.app.services.executive_service import executive_verdict


def _n(display: str) -> Numeric:
    return Numeric(raw=None, unit="yuan", display=display, precision=2, sign_aware=True)


def _metric(
    mid: str,
    *,
    tone: str,
    label: str = "指标",
    detail: str = "说明",
) -> ExecutiveMetric:
    return ExecutiveMetric(
        id=mid,
        label=label,
        value=_n("100.00"),
        delta=_n("0.00"),
        tone=tone,
        detail=detail,
    )


def test_all_positive_metrics_yields_positive_tone() -> None:
    overview = OverviewPayload(
        title="t",
        metrics=[
            _metric("a", tone="positive"),
            _metric("b", tone="positive"),
        ],
    )
    v = executive_verdict(
        overview=overview,
        attention_count=0,
        partial_note=None,
        client_mode="real",
    )
    assert v.tone == "positive"
    assert "偏多" in v.conclusion


def test_all_warning_metrics_yields_warning_tone() -> None:
    overview = OverviewPayload(
        title="t",
        metrics=[
            _metric("a", tone="warning"),
            _metric("b", tone="warning"),
        ],
    )
    v = executive_verdict(
        overview=overview,
        attention_count=0,
        partial_note=None,
        client_mode="real",
    )
    assert v.tone == "warning"
    assert "压力" in v.conclusion


def test_partial_note_yields_warning_and_conclusion_mentions_review() -> None:
    overview = OverviewPayload(
        title="t",
        metrics=[_metric("a", tone="positive")],
    )
    v = executive_verdict(
        overview=overview,
        attention_count=1,
        partial_note="部分业务域不可用: bond",
        client_mode="real",
    )
    assert v.tone == "warning"
    assert "复核" in v.conclusion


def test_reasons_at_most_three() -> None:
    overview = OverviewPayload(
        title="t",
        metrics=[
            _metric("1", tone="neutral"),
            _metric("2", tone="neutral"),
            _metric("3", tone="neutral"),
            _metric("4", tone="neutral"),
            _metric("5", tone="neutral"),
        ],
    )
    v = executive_verdict(
        overview=overview,
        attention_count=0,
        partial_note=None,
        client_mode="real",
    )
    assert len(v.reasons) <= 3
    assert len(v.reasons) == 3


def test_suggestions_at_least_one_and_warning_appends_bond() -> None:
    overview = OverviewPayload(
        title="t",
        metrics=[_metric("a", tone="warning")],
    )
    v = executive_verdict(
        overview=overview,
        attention_count=0,
        partial_note=None,
        client_mode="real",
    )
    assert len(v.suggestions) >= 2
    texts = [s.text for s in v.suggestions]
    assert any("下钻" in t for t in texts)
    assert any("信用利差" in t for t in texts)
