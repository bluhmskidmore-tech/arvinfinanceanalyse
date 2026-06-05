from __future__ import annotations

from pathlib import Path

from backend.app.core_finance.hybrid_fusion_config import (
    DEFAULT_HYBRID_FUSION_THRESHOLDS,
    HybridFusionThresholds,
    load_hybrid_fusion_thresholds,
)


def test_load_hybrid_fusion_thresholds_from_repo_yaml() -> None:
    thresholds = load_hybrid_fusion_thresholds()
    assert thresholds.life_long_top_q == 0.85
    assert thresholds.fusion_cycle_weight == 0.65
    assert thresholds.cycle_macro_weight == 0.30


def test_load_hybrid_fusion_thresholds_falls_back_when_yaml_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    thresholds = load_hybrid_fusion_thresholds(missing)
    assert thresholds == DEFAULT_HYBRID_FUSION_THRESHOLDS


def test_load_hybrid_fusion_thresholds_overrides_subset(tmp_path: Path) -> None:
    yaml_path = tmp_path / "hybrid.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "thresholds:",
                "  life_long_top_q: 0.90",
                "  fusion_cycle_weight: 0.70",
            ]
        ),
        encoding="utf-8",
    )
    thresholds = load_hybrid_fusion_thresholds(yaml_path)
    assert thresholds.life_long_top_q == 0.90
    assert thresholds.fusion_cycle_weight == 0.70
    assert thresholds.life_long_pconf_top_q == DEFAULT_HYBRID_FUSION_THRESHOLDS.life_long_pconf_top_q


def test_custom_thresholds_change_life_long_gate() -> None:
    from typing import Any, cast

    from backend.app.core_finance.hybrid_fusion_candidates import compute_hybrid_fusion_candidates

    strict = HybridFusionThresholds(
        life_long_top_q=0.99,
        life_long_pconf_top_q=0.99,
        life_long_crowd_max_q=0.01,
    )
    loose = HybridFusionThresholds(
        life_long_top_q=0.50,
        life_long_pconf_top_q=0.50,
        life_long_crowd_max_q=0.99,
    )
    payload = {
        "sector_rank_payload": {"items": [{"sector_code": "801080", "rank": 1}]},
        "stock_candidates_payload": {
            "items": [
                {
                    "rank": 1,
                    "stock_code": "688001.SH",
                    "stock_name": "A",
                    "sector_code": "801080",
                    "close_strength": 0.95,
                    "abnormal_turnover": 1.5,
                    "breakout_extension_norm": 0.12,
                },
                {
                    "rank": 2,
                    "stock_code": "000001.SZ",
                    "stock_name": "B",
                    "sector_code": "801080",
                    "close_strength": 0.55,
                    "abnormal_turnover": 1.2,
                    "breakout_extension_norm": 0.12,
                },
            ]
        },
        "factor_screen_payload": {
            "items": [
                {"rank": 1, "stock_code": "688001.SH", "stock_name": "A", "sector_code": "801080"},
                {"rank": 2, "stock_code": "000001.SZ", "stock_name": "B", "sector_code": "801080"},
            ]
        },
        "theme_breakout_payload": None,
    }
    strict_items = compute_hybrid_fusion_candidates(
        as_of_date="2026-05-08",
        market_state="HOT",
        thresholds=strict,
        **payload,
    ).payload["items"]
    loose_items = compute_hybrid_fusion_candidates(
        as_of_date="2026-05-08",
        market_state="HOT",
        thresholds=loose,
        **payload,
    ).payload["items"]
    strict_pass = sum(1 for item in strict_items if item["life_long_pass"])
    loose_pass = sum(1 for item in loose_items if item["life_long_pass"])
    assert strict_pass <= loose_pass
