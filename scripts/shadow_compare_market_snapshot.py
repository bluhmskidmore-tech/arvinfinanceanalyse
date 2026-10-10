"""Compare the market snapshot tape with the current frontend selection rules.

This is a read-only Phase 1.5 gate.  The legacy side deliberately preserves the
regular-expression selection from ``marketOverviewDenseModel.ts`` so every
disagreement can be classified before WP-H changes the page.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_TEN_YEAR_HINT = re.compile(r"10\s*(?:y|yr|year)|10\s*年", re.IGNORECASE)
_CHINA_SOVEREIGN_HINT = re.compile(r"\b(?:china|cgb)\b|中国|中债|国债", re.IGNORECASE)
_FOREIGN_SOVEREIGN_HINT = re.compile(
    r"\b(?:us|u\.s\.|usa|uk|u\.k\.|gbr|jp|jpn|japan|treasury|gilt|jgb)\b|美国|英国|日本",
    re.IGNORECASE,
)
_LEGACY_SLOT_ORDER = (
    ("gov_10y", "10Y sovereign"),
    ("dr007", "DR007"),
    ("omo_7d", "7D reverse repo"),
    ("shibor_3m", "SHIBOR 3M"),
    ("csi300_close", "CSI 300"),
    ("brent", "Brent"),
    ("usd_cny_mid", "USD/CNY"),
    ("copper_main", "Copper"),
)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[object]:
    return (
        value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes))
        else ()
    )


def _series(envelope: Mapping[str, object]) -> list[Mapping[str, object]]:
    return [
        item
        for item in _sequence(_mapping(envelope.get("result")).get("series"))
        if isinstance(item, Mapping)
    ]


def _text(point: Mapping[str, object]) -> str:
    return f"{point.get('series_id') or ''} {point.get('series_name') or ''}".lower()


def _find(
    points: Sequence[Mapping[str, object]],
    predicate: Any,
) -> Mapping[str, object] | None:
    return next((point for point in points if predicate(_text(point), point)), None)


def _is_china_ten_year(point: Mapping[str, object]) -> bool:
    search_text = f"{point.get('series_id') or ''} {point.get('series_name') or ''}"
    if not _TEN_YEAR_HINT.search(search_text):
        return False
    if _FOREIGN_SOVEREIGN_HINT.search(search_text):
        return False
    return bool(
        re.match(r"^cn[._-]", str(point.get("series_id") or ""), re.IGNORECASE)
    ) or bool(_CHINA_SOVEREIGN_HINT.search(search_text))


def _legacy_selection(
    *, latest: Sequence[Mapping[str, object]], rates: Sequence[Mapping[str, object]]
) -> dict[str, Mapping[str, object] | None]:
    """Port ``buildDenseTapeMetrics`` selection only; no formatting is involved."""
    merged = [*rates, *latest]
    return {
        "gov_10y": next((point for point in merged if _is_china_ten_year(point)), None),
        "dr007": _find(
            merged, lambda text, _point: bool(re.search(r"dr\s*0?07", text, re.I))
        ),
        "omo_7d": _find(
            merged,
            lambda text, point: (
                str(point.get("series_id") or "") == "EMM00088132"
                or bool(
                    re.search(r"逆回购", text) and re.search(r"7\s*天|7d", text, re.I)
                )
            ),
        ),
        "shibor_3m": _find(
            merged,
            lambda text, point: (
                str(point.get("series_id") or "") == "NCD.SHIBOR.3M"
                or bool(
                    re.search(r"shibor", text, re.I)
                    and re.search(r"3\s*m|3\s*月", text, re.I)
                )
            ),
        ),
        "csi300_close": _find(
            latest,
            lambda text, _point: (
                bool(re.search(r"沪深\s*300|csi\s*300|hs300", text, re.I))
                and bool(re.search(r"收盘|close", text, re.I))
            ),
        ),
        "brent": _find(
            latest, lambda text, _point: bool(re.search(r"brent|布伦特", text, re.I))
        ),
        "usd_cny_mid": _find(
            latest,
            lambda text, _point: bool(
                re.search(r"usd\s*/?\s*cny|美元兑人民币|usdcny", text, re.I)
            ),
        ),
        "copper_main": _find(
            latest,
            lambda text, point: (
                str(point.get("series_id") or "") == "CA.COPPER"
                or bool(re.search(r"铜.*(收盘|期货)|copper", text, re.I))
            ),
        ),
    }


def _row_value(point: Mapping[str, object] | None, field: str) -> str:
    if point is None:
        return "unresolved"
    value = point.get(field)
    return str(value) if value not in (None, "") else "unresolved"


def _conclusion(
    *, old_id: str, old_date: str, new_id: str, new_date: str
) -> tuple[str, str]:
    if old_id == new_id and old_date == new_date and old_id != "unresolved":
        return (
            "yes",
            "legacy regex and registered aliases selected the same landed point",
        )
    if new_id == "unresolved":
        return (
            "no",
            "registered alias did not resolve; inspect the alias table before frontend cutover",
        )
    if old_id == "unresolved":
        return (
            "no",
            "legacy regex did not resolve; registered alias selected the governed series",
        )
    if old_id != new_id:
        return (
            "no",
            "legacy regex selected a different series; registered alias takes precedence",
        )
    return (
        "no",
        "same series_id but different trade_date; inspect landed-date selection before frontend cutover",
    )


def compare(duckdb_path: str) -> list[tuple[str, str, str, str, str, str, str]]:
    # Importing main wires the macro-toolkit read builders without starting an
    # HTTP server; the comparison invokes only existing read-model builders.
    from backend.app import main as app_main
    from backend.app.services.macro_toolkit_refresh_receipt_service import (
        load_macro_toolkit_refresh_receipt_health,
    )
    from backend.app.services.macro_vendor_service import (
        choice_macro_formal_envelope,
        choice_macro_latest_envelope,
    )
    from backend.app.services.market_overview_service import (
        DEFAULT_MARKET_OVERVIEW_INCLUDE,
        build_market_snapshot,
    )

    _ = app_main
    health = load_macro_toolkit_refresh_receipt_health()
    snapshot = build_market_snapshot(
        include=DEFAULT_MARKET_OVERVIEW_INCLUDE,
        duckdb_path=duckdb_path,
        refresh_receipt_health=health,
    )
    tape = _mapping(_mapping(snapshot.get("result")).get("tape"))
    new_slots = {
        str(slot.get("key")): slot
        for slot in _sequence(tape.get("slots"))
        if isinstance(slot, Mapping)
    }
    latest = _series(choice_macro_latest_envelope(duckdb_path, category=None))
    rates = _series(choice_macro_formal_envelope(duckdb_path))
    legacy = _legacy_selection(latest=latest, rates=rates)

    rows: list[tuple[str, str, str, str, str, str, str]] = []
    for key, label in _LEGACY_SLOT_ORDER:
        old_point = legacy[key]
        new_point = _mapping(new_slots.get(key))
        old_id = _row_value(old_point, "series_id")
        old_date = _row_value(old_point, "trade_date")
        new_id = _row_value(new_point, "series_id")
        new_date = _row_value(new_point, "trade_date")
        match, conclusion = _conclusion(
            old_id=old_id,
            old_date=old_date,
            new_id=new_id,
            new_date=new_date,
        )
        rows.append((label, old_id, old_date, new_id, new_date, match, conclusion))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duckdb", default="data/moss.duckdb", help="Read-only DuckDB path"
    )
    args = parser.parse_args()
    duckdb_path = str(Path(args.duckdb))

    print(
        "| slot | old series_id | old trade_date | new series_id | new trade_date | match | conclusion |"
    )
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for row in compare(duckdb_path):
        print("| " + " | ".join(row) + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
