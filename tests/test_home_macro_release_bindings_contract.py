from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "home_macro_release_bindings.json"

FORBIDDEN_RUNTIME_KEYS = {
    "history",
    "latest_value",
    "previous_value",
    "change_value",
    "observation_date",
    "release_date",
}

EXPECTED_GROUP_KEYS = {
    "cn_pmi",
    "cn_inflation",
    "cn_growth",
    "us_ism",
    "us_inflation",
    "us_employment",
    "us_growth",
    "fomc",
}

EXPECTED_AUTOMATIC_BINDINGS = {
    ("cn_pmi", "manufacturing_pmi"): {
        "table": "fact_choice_macro_daily",
        "series_id": "M0017126",
        "cadence": "monthly",
        "display_unit": "index",
        "change_unit": "index_point",
        "precision": 1,
    },
    ("cn_inflation", "cpi_yoy"): {
        "table": "std_external_macro_daily",
        "series_id": "tushare.macro.cn_cpi.monthly",
        "cadence": "monthly",
        "display_unit": "pct",
        "change_unit": "pct_point",
        "precision": 1,
    },
    ("cn_inflation", "ppi_yoy"): {
        "table": "std_external_macro_daily",
        "series_id": "tushare.macro.cn_ppi.monthly",
        "cadence": "monthly",
        "display_unit": "pct",
        "change_unit": "pct_point",
        "precision": 1,
    },
    ("cn_growth", "gdp_yoy"): {
        "source_candidates": [
            {
                "table": "std_external_macro_daily",
                "series_id": "nbs.macro.cn_gdp.quarterly",
                "vendor_name": "NBS official release",
                "priority": 1,
            },
            {
                "table": "std_external_macro_daily",
                "series_id": "tushare.macro.cn_gdp.quarterly",
                "vendor_name": "Tushare",
                "priority": 2,
            },
        ],
        "cadence": "quarterly",
        "display_unit": "pct",
        "change_unit": "pct_point",
        "precision": 1,
    },
}

EXPECTED_SOURCE_PENDING_GROUPS = {
    "us_ism",
    "us_inflation",
    "us_employment",
    "us_growth",
    "fomc",
}
GROUP_FIELDS = {
    "indicator_key",
    "title",
    "region",
    "category",
    "importance",
    "priority",
    "availability",
    "publisher_name",
    "vendor_name",
    "metrics",
}

METRIC_SEMANTIC_FIELDS = {
    "metric_key",
    "label",
    "cadence",
    "display_unit",
    "change_unit",
    "precision",
}

METRIC_BINDING_FIELDS = {"table", "series_id"}



def _load_bindings() -> dict[str, object]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _find_forbidden_key_paths(value: object, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_RUNTIME_KEYS:
                found.append(child_path)
            found.extend(_find_forbidden_key_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_find_forbidden_key_paths(child, f"{path}[{index}]"))
    return found


def test_home_macro_release_bindings_are_semantic_only_and_versioned() -> None:
    config = _load_bindings()
    assert set(config) == {"rule_version", "groups"}

    assert config["rule_version"] == "rv_home_macro_release_context_v1"
    assert _find_forbidden_key_paths(config) == []


def test_home_macro_release_bindings_cover_all_eight_stable_groups() -> None:
    config = _load_bindings()
    groups = config["groups"]
    assert isinstance(groups, list)

    indicator_keys = [group["indicator_key"] for group in groups]
    assert len(indicator_keys) == 8
    assert len(indicator_keys) == len(set(indicator_keys))
    assert set(indicator_keys) == EXPECTED_GROUP_KEYS
    assert [group["priority"] for group in groups] == list(range(1, 9))

    for group in groups:
        assert set(group) == GROUP_FIELDS
        assert group["indicator_key"]
        assert group["title"]
        assert group["region"] in {"CN", "US"}
        assert group["availability"] in {"automatic", "source_pending"}
        assert isinstance(group["metrics"], list) and group["metrics"]
        if group["availability"] == "automatic":
            assert isinstance(group["publisher_name"], str)
            assert group["publisher_name"]
            assert isinstance(group["vendor_name"], str)
            assert group["vendor_name"]
        else:
            assert group["publisher_name"] is None
            assert group["vendor_name"] is None
        for metric in group["metrics"]:
            binding_fields = set(metric) - METRIC_SEMANTIC_FIELDS
            if group["availability"] == "automatic":
                assert binding_fields in (
                    {"table", "series_id"},
                    {"source_candidates"},
                )
            else:
                assert binding_fields == set()
            assert metric["metric_key"]
            assert metric["label"]


def test_connected_metrics_have_governed_source_and_display_bindings() -> None:
    config = _load_bindings()
    groups = config["groups"]
    actual: dict[tuple[str, str], dict[str, object]] = {}

    for group in groups:
        if group["availability"] != "automatic":
            continue
        for metric in group["metrics"]:
            key = (group["indicator_key"], metric["metric_key"])
            semantic = {
                field: metric[field]
                for field in ("cadence", "display_unit", "change_unit", "precision")
            }
            if "source_candidates" in metric:
                actual[key] = {
                    "source_candidates": metric["source_candidates"],
                    **semantic,
                }
            else:
                actual[key] = {
                    "table": metric["table"],
                    "series_id": metric["series_id"],
                    **semantic,
                }

    assert actual == EXPECTED_AUTOMATIC_BINDINGS


def test_unconnected_us_groups_are_explicitly_source_pending() -> None:
    config = _load_bindings()
    groups = config["groups"]
    pending = {
        group["indicator_key"]
        for group in groups
        if group["availability"] == "source_pending"
    }

    assert pending == EXPECTED_SOURCE_PENDING_GROUPS
    for group in groups:
        if group["indicator_key"] not in EXPECTED_SOURCE_PENDING_GROUPS:
            continue
        assert group["region"] == "US"
        for metric in group["metrics"]:
            assert "table" not in metric
            assert "series_id" not in metric
