"""The page-facing walk-forward verdict table must match the report it cites.

``strategy_walk_forward_verdicts._VERDICTS`` is a hand-copied excerpt of
``docs/strategy-reports/walk-forward-rerun-20260813.md`` §0.1. Nothing else ties the
two together, so a re-run that rewrites the report (or an edit to the constants)
would silently desynchronise what the stock-analysis page discloses from the
evidence it points at. This test parses §0.1 by column name and the §8
``generated_at`` stamp, and compares every anchored field including the wording
of ``reason``.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.core_finance import strategy_walk_forward_verdicts as verdicts
from tests.helpers import ROOT

_VERDICT_BY_LABEL = {
    "样本外支持": verdicts.VERDICT_SUPPORTED,
    "样本外削弱": verdicts.VERDICT_WEAKENED,
    "不可判(窗数不足)": verdicts.VERDICT_NOT_ASSESSABLE,
}
_REQUIRED_COLUMNS = ("signal_kind", "OOS窗数", "OOS链式超额(vs gate)", "正超额窗", "全窗口IS收益", "判定")


def _report_path() -> Path:
    path = ROOT / verdicts.WALK_FORWARD_REPORT
    if not path.exists():
        pytest.fail(f"cited walk-forward report is missing: {path}")
    return path


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _section_01_rows(text: str) -> dict[str, dict[str, str]]:
    """Return §0.1 rows keyed by signal_kind, each row keyed by header name."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("### 0.1 "))
    header: list[str] | None = None
    rows: dict[str, dict[str, str]] = {}
    for line in lines[start + 1 :]:
        if line.startswith("### ") or line.startswith("## "):
            break
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = _split_row(line)
        if header is None:
            header = cells
            missing = [name for name in _REQUIRED_COLUMNS if name not in header]
            assert not missing, f"report §0.1 header lost columns {missing}: {header}"
            continue
        row = dict(zip(header, cells, strict=True))
        rows[row["signal_kind"]] = row
    assert header is not None, "report §0.1 table header not found"
    return rows


def _pct_to_ratio(text: str) -> Decimal:
    return (Decimal(text.rstrip("%")) / Decimal("100")).quantize(Decimal("0.0001"))


def test_verdict_table_matches_cited_report_section_01() -> None:
    rows = _section_01_rows(_report_path().read_text(encoding="utf-8"))
    assert set(rows) == set(verdicts._VERDICTS), "report §0.1 and the verdict table cover different signal kinds"

    for signal_kind, row in rows.items():
        entry = verdicts.walk_forward_verdict(signal_kind)
        assert entry is not None
        label = row["判定"]
        assert entry["verdict"] == _VERDICT_BY_LABEL[label], signal_kind
        assert entry["verdict_label"] == ("样本外未检验" if label == "不可判(窗数不足)" else label), signal_kind

        if entry["verdict"] == verdicts.VERDICT_NOT_ASSESSABLE:
            assert int(row["OOS窗数"]) < 3, signal_kind
            assert entry["oos_windows"] is None and entry["positive_excess_windows"] is None
            assert entry["chained_excess_return"] is None
            assert entry["reason"].startswith(verdicts._NOT_ASSESSABLE_REASON), signal_kind
            if signal_kind == "factor_screen":
                assert row["全窗口IS收益"] in entry["reason"]
            continue

        oos_windows = int(row["OOS窗数"])
        positive, total = (int(part) for part in row["正超额窗"].split("/"))
        assert entry["oos_windows"] == oos_windows == total, signal_kind
        assert entry["positive_excess_windows"] == positive, signal_kind
        assert Decimal(str(entry["chained_excess_return"])) == _pct_to_ratio(row["OOS链式超额(vs gate)"]), signal_kind
        # The human-readable reason must quote the same window counts and percentage.
        reason = entry["reason"]
        assert f"{oos_windows} 个验证窗" in reason, signal_kind
        assert (f"{positive}/{total} 个" in reason) or (f"仅 {positive} 窗" in reason), signal_kind
        assert row["OOS链式超额(vs gate)"].lstrip("+") in reason, signal_kind


def test_verdict_judged_at_matches_report_generation_stamp() -> None:
    text = _report_path().read_text(encoding="utf-8")
    match = re.search(r'"generated_at":\s*"(\d{4}-\d{2}-\d{2})', text)
    assert match is not None, "report §8 machine-readable summary lacks generated_at"
    assert verdicts.WALK_FORWARD_JUDGED_AT == match.group(1)
    # The split named in the contract must be the primary split the report judged on.
    assert "primary_6t_2v_2s" in text
    assert "等权 fixed_20d" in text
    assert verdicts.WALK_FORWARD_SPLIT.startswith("primary_")
    assert "fixed_20d" in verdicts.WALK_FORWARD_SPLIT
