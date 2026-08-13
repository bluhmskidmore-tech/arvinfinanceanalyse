"""
apply_scenario_to_rows 零基准（baseline_ftp_rate_pct=0）边界（2026-08 PnL 归因审计 M6）。

旧行为：baseline 为 0 时 ratio 记 0，情景 FTP 恒为 0——情景利率被静默忽略。
新行为：按正式口径的 FTP 基线公式 scale × scenario_rate × days/365
（_calculate_ftp，与 calculate_read_model 叶子行一致，days 由行内
report_date/view 经 _days_for_view 推得）以情景利率直接重算；
行内 scale 全为 0 的汇总行（如 grand_total）保持 0。

范围：仅 Scenario 面（analysis_adapters 仅在 basis=scenario 时调用本函数），
Formal 读模型不经过本函数，行为零变化。
"""
from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.product_category_pnl import apply_scenario_to_rows


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "category_id": "cat_leaf",
        "category_name": "叶子类目",
        "side": "asset",
        "level": 1,
        "view": "monthly",
        "report_date": "2026-01-31",
        "baseline_ftp_rate_pct": Decimal("0"),
        "cnx_scale": Decimal("43800"),
        "cny_scale": Decimal("36500"),
        "foreign_scale": Decimal("7300"),
        "cnx_cash": Decimal("120"),
        "cny_cash": Decimal("100"),
        "foreign_cash": Decimal("20"),
        "cny_ftp": Decimal("0"),
        "foreign_ftp": Decimal("0"),
        "cny_net": Decimal("100"),
        "foreign_net": Decimal("20"),
        "business_net_income": Decimal("120"),
        "weighted_yield": None,
        "is_total": False,
        "children": [],
    }
    base.update(overrides)
    return base


def test_zero_baseline_recomputes_ftp_from_scale_rate_days() -> None:
    """手算：monthly 2026-01 → days=31；rate = 2.5% = 0.025。

    cny_ftp     = 36500 × 0.025 × 31/365 = 77.5
    foreign_ftp =  7300 × 0.025 × 31/365 = 15.5
    合计 93 = cnx_scale 公式 43800 × 0.025 × 31/365（分币种与全币种线性一致）。
    旧行为此处全部为 0（情景利率被忽略）。
    """
    (adjusted,) = apply_scenario_to_rows([_row()], Decimal("2.5"))

    assert adjusted["cny_ftp"] == Decimal("77.5")
    assert adjusted["foreign_ftp"] == Decimal("15.5")
    assert adjusted["cny_ftp"] + adjusted["foreign_ftp"] == Decimal("93")
    assert adjusted["cny_net"] == Decimal("100") - Decimal("77.5")
    assert adjusted["foreign_net"] == Decimal("20") - Decimal("15.5")
    assert adjusted["business_net_income"] == Decimal("27")
    assert adjusted["scenario_rate_pct"] == Decimal("2.5")


def test_zero_baseline_days_follow_row_view_and_report_date() -> None:
    """ytd 2026-02-28 → days = 31 + 28 = 59：cny_ftp = 36500 × 0.025 × 59/365 = 147.5。"""
    (adjusted,) = apply_scenario_to_rows(
        [_row(view="ytd", report_date="2026-02-28")],
        Decimal("2.5"),
    )

    assert adjusted["cny_ftp"] == Decimal("147.5")
    assert adjusted["foreign_ftp"] == Decimal("29.5")


def test_zero_baseline_zero_scale_total_row_stays_zero_without_date_parsing() -> None:
    """grand_total 形态（scale 全 0）：FTP 保持 0、净额=现金；
    即便 report_date 为 None（空 total 行边界）也不得崩溃。"""
    (adjusted,) = apply_scenario_to_rows(
        [
            _row(
                category_id="grand_total",
                is_total=True,
                report_date=None,
                cnx_scale=Decimal("0"),
                cny_scale=Decimal("0"),
                foreign_scale=Decimal("0"),
            )
        ],
        Decimal("2.5"),
    )

    assert adjusted["cny_ftp"] == Decimal("0")
    assert adjusted["foreign_ftp"] == Decimal("0")
    assert adjusted["cny_net"] == Decimal("100")
    assert adjusted["foreign_net"] == Decimal("20")
    assert adjusted["business_net_income"] == Decimal("120")


def test_zero_baseline_zero_scenario_rate_keeps_ftp_zero() -> None:
    """scenario_rate = 0：公式 scale × 0 × days/365 = 0，与旧行为一致。"""
    (adjusted,) = apply_scenario_to_rows([_row()], Decimal("0"))

    assert adjusted["cny_ftp"] == Decimal("0")
    assert adjusted["foreign_ftp"] == Decimal("0")
    assert adjusted["business_net_income"] == Decimal("120")


def test_nonzero_baseline_ratio_path_is_unchanged() -> None:
    """回归：非零基准仍走 ratio 缩放（3.2/1.6=2 → FTP 翻倍），
    而不是 scale 公式重算（那会给出 36500×0.032×31/365=99.2 ≠ 160）。"""
    (adjusted,) = apply_scenario_to_rows(
        [
            _row(
                baseline_ftp_rate_pct=Decimal("1.6"),
                cny_ftp=Decimal("80"),
                foreign_ftp=Decimal("8"),
                cny_net=Decimal("20"),
                foreign_net=Decimal("12"),
                business_net_income=Decimal("32"),
            )
        ],
        Decimal("3.2"),
    )

    assert adjusted["cny_ftp"] == Decimal("160")
    assert adjusted["foreign_ftp"] == Decimal("16")
    assert adjusted["cny_net"] == Decimal("100") - Decimal("160")
    assert adjusted["foreign_net"] == Decimal("20") - Decimal("16")
    assert adjusted["business_net_income"] == Decimal("-56")
    assert adjusted["scenario_rate_pct"] == Decimal("3.2")
