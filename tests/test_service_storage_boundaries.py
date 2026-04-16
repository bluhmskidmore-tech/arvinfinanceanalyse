from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHOICE_NEWS_SERVICE = ROOT / "backend" / "app" / "services" / "choice_news_service.py"
EXECUTIVE_SERVICE = ROOT / "backend" / "app" / "services" / "executive_service.py"
MACRO_BOND_LINKAGE_SERVICE = ROOT / "backend" / "app" / "services" / "macro_bond_linkage_service.py"
MACRO_VENDOR_SERVICE = ROOT / "backend" / "app" / "services" / "macro_vendor_service.py"
PNL_BRIDGE_SERVICE = ROOT / "backend" / "app" / "services" / "pnl_bridge_service.py"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _assert_service_avoids_direct_storage_and_formal_sql(path: Path, text: str) -> None:
    """High-risk services must orchestrate via repositories, not duckdb.connect or embedded formal SQL."""
    assert path.is_file(), f"Missing service module: {path}"

    assert "duckdb.connect(" not in text, (
        f"{path.name}: must not call duckdb.connect; use repositories for storage access."
    )

    violations: list[str] = []
    # Block SQL-shaped references to formal fact tables (direct queries / DML).
    for pattern, kind in (
        (r"\bfrom\s+[`'\"]?(fact_formal_\w+)", "FROM fact_formal_*"),
        (r"\bjoin\s+[`'\"]?(fact_formal_\w+)", "JOIN fact_formal_*"),
        (r"\binto\s+[`'\"]?(fact_formal_\w+)", "INTO fact_formal_*"),
        (r"\bupdate\s+[`'\"]?(fact_formal_\w+)", "UPDATE fact_formal_*"),
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match is not None:
            violations.append(f"{kind}: {match.group(0)!r}")

    assert not violations, (
        f"{path.name}: must not embed SQL against fact_formal_* tables:\n"
        + "\n".join(violations)
    )


def test_choice_news_service_avoids_storage_bypass():
    text = _read_source(CHOICE_NEWS_SERVICE)
    assert "duckdb.connect(" not in text, (
        f"{CHOICE_NEWS_SERVICE.name}: must not call duckdb.connect; use repositories for storage access."
    )


def test_executive_service_avoids_storage_bypass():
    text = _read_source(EXECUTIVE_SERVICE)
    _assert_service_avoids_direct_storage_and_formal_sql(EXECUTIVE_SERVICE, text)


def test_macro_bond_linkage_service_avoids_storage_bypass():
    text = _read_source(MACRO_BOND_LINKAGE_SERVICE)
    _assert_service_avoids_direct_storage_and_formal_sql(MACRO_BOND_LINKAGE_SERVICE, text)


def test_macro_vendor_service_avoids_storage_bypass():
    text = _read_source(MACRO_VENDOR_SERVICE)
    _assert_service_avoids_direct_storage_and_formal_sql(MACRO_VENDOR_SERVICE, text)


def test_pnl_bridge_service_avoids_storage_bypass():
    text = _read_source(PNL_BRIDGE_SERVICE)
    _assert_service_avoids_direct_storage_and_formal_sql(PNL_BRIDGE_SERVICE, text)
