from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STRATEGY_YAML = _REPO_ROOT / "config" / "hybrid_fusion_strategy.yaml"


@dataclass(frozen=True)
class HybridFusionThresholds:
    life_long_top_q: float = 0.85
    life_long_pconf_top_q: float = 0.70
    life_long_crowd_max_q: float = 0.80
    stance_strong_q: float = 0.85
    stance_neutral_q: float = 0.50
    fusion_cycle_weight: float = 0.65
    fusion_life_weight: float = 0.35
    cycle_macro_weight: float = 0.30
    cycle_industry_weight: float = 0.35
    cycle_market_flow_weight: float = 0.20
    cycle_valuation_weight: float = 0.15
    legacy_cycle_sector_weight: float = 0.70
    legacy_cycle_factor_weight: float = 0.30


DEFAULT_HYBRID_FUSION_THRESHOLDS = HybridFusionThresholds()


def load_hybrid_fusion_thresholds(yaml_path: Path | None = None) -> HybridFusionThresholds:
    path = yaml_path or DEFAULT_STRATEGY_YAML
    if not path.exists():
        validate_thresholds(DEFAULT_HYBRID_FUSION_THRESHOLDS)
        return DEFAULT_HYBRID_FUSION_THRESHOLDS
    parsed = _parse_threshold_yaml(path)
    if not parsed:
        validate_thresholds(DEFAULT_HYBRID_FUSION_THRESHOLDS)
        return DEFAULT_HYBRID_FUSION_THRESHOLDS
    kwargs: dict[str, float] = {}
    for field in fields(HybridFusionThresholds):
        if field.name in parsed:
            kwargs[field.name] = parsed[field.name]
    thresholds = HybridFusionThresholds(**kwargs)
    validate_thresholds(thresholds)
    return thresholds


def validate_thresholds(thresholds: HybridFusionThresholds) -> None:
    weight_groups = (
        ("fusion_cycle_weight", "fusion_life_weight"),
        ("cycle_macro_weight", "cycle_industry_weight", "cycle_market_flow_weight", "cycle_valuation_weight"),
        ("legacy_cycle_sector_weight", "legacy_cycle_factor_weight"),
    )
    for group in weight_groups:
        total = sum(getattr(thresholds, field_name) for field_name in group)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"{', '.join(group)} must sum to 1.0, got {total:.6f}")

    for field in fields(HybridFusionThresholds):
        if field.name.endswith("_q"):
            value = getattr(thresholds, field.name)
            if not 0.0 < value < 1.0:
                raise ValueError(f"{field.name} must be in (0, 1), got {value}")

    if thresholds.stance_strong_q < thresholds.stance_neutral_q:
        raise ValueError(
            "stance_strong_q must be greater than or equal to stance_neutral_q, "
            f"got {thresholds.stance_strong_q} < {thresholds.stance_neutral_q}"
        )


def _parse_threshold_yaml(path: Path) -> dict[str, float]:
    section = ""
    out: dict[str, float] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1].strip()
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if section != "thresholds" or not value:
            continue
        try:
            out[key] = float(value)
        except ValueError:
            continue
    return out
