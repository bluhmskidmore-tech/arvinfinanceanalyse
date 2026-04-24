from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

CURRENT_PAGE_EDGE_FILES = (
    ROOT / "backend" / "app" / "services" / "executive_service.py",
    ROOT / "backend" / "app" / "services" / "macro_bond_linkage_service.py",
    ROOT / "backend" / "app" / "core_finance" / "macro_bond_linkage.py",
    ROOT / "frontend" / "src" / "features" / "cross-asset" / "lib" / "crossAssetDriversPageModel.ts",
    ROOT / "frontend" / "src" / "features" / "cross-asset" / "pages" / "CrossAssetDriversPage.tsx",
    ROOT / "frontend" / "src" / "features" / "workbench" / "pages" / "DashboardPage.tsx",
)

FUTURE_SUPPLY_AUCTION_FILES = (
    ROOT / "backend" / "app" / "api" / "routes" / "research_calendar.py",
    ROOT / "backend" / "app" / "services" / "research_calendar_service.py",
    ROOT / "backend" / "app" / "repositories" / "research_calendar_repo.py",
    ROOT / "backend" / "app" / "schemas" / "research_calendar.py",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _landed_supply_auction_files() -> list[Path]:
    return [path for path in FUTURE_SUPPLY_AUCTION_FILES if path.exists()]


def test_approved_supply_auction_plan_pins_external_data_authority_and_payload_severity():
    route_src = _read(ROOT / "backend" / "app" / "api" / "routes" / "research_calendar.py")
    repo_src = _read(ROOT / "backend" / "app" / "repositories" / "research_calendar_repo.py")
    client_src = _read(ROOT / "frontend" / "src" / "api" / "client.ts")
    authority_src = "\n".join((route_src, repo_src, client_src))

    assert "research.calendar.supply_auction" in authority_src
    assert "std_external_supply_auction_calendar" in authority_src
    assert "vw_external_supply_auction_calendar" in authority_src
    assert "/ui/calendar/supply-auctions" in client_src
    assert "severity: event.severity" in client_src


def test_current_adjacent_calendar_surfaces_do_not_reuse_workbook_event_calendar():
    for path in CURRENT_PAGE_EDGE_FILES:
        src = _read(path)
        assert "event_calendar" not in src, f"{path} should not reuse workbook event_calendar for external research calendar rows"


def test_dedicated_supply_auction_files_do_not_define_schedule_from_workbook_event_calendar():
    files = _landed_supply_auction_files()
    if not files:
        pytest.skip("Dedicated supply/auction feature files are not present in this checkout yet.")

    for path in files:
        src = _read(path)
        assert "event_calendar" not in src, f"{path} should not import or derive schedule rows from workbook event_calendar"
        assert "balance_analysis" not in src, f"{path} should stay out of balance-analysis workbook logic"


def test_dedicated_supply_auction_files_keep_choice_news_as_enrichment_only():
    files = _landed_supply_auction_files()
    if not files:
        pytest.skip("Dedicated supply/auction feature files are not present in this checkout yet.")

    authority_markers = (
        "external_data",
        "std_external_supply_auction_calendar",
        "vw_external_supply_auction_calendar",
        "research.calendar.supply_auction",
    )
    choice_news_markers = (
        "choice_news",
        "choice_news_event",
    )

    for path in files:
        src = _read(path)
        has_choice_news = any(marker in src for marker in choice_news_markers)
        if has_choice_news:
            assert any(marker in src for marker in authority_markers), (
                f"{path} references choice_news but does not show an external_data-backed schedule authority"
            )
