from __future__ import annotations

"""
Contract source:
- `frontend/src/mocks/navigation.ts` `workbenchNavigation`
- `docs/page_contracts.md` `PAGE-*` sections and their primary front-end route

Whitelist:
- `TEMP_EXCEPTION_ROUTE_PAGE_CONTRACT_WHITELIST` only covers live routes that are
  still marked `governanceStatus: "temporary-exception"` in navigation and do
  not yet have a dedicated `PAGE-*` section.
- The whitelist is explicit so future contract landings force cleanup instead of
  silently staying exempt forever.

Follow-up plan:
- Add dedicated page contracts for any non-whitelisted live routes still missing
  coverage.
- Remove whitelist entries as soon as the corresponding `PAGE-*` section lands.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.helpers import ROOT

NAVIGATION_PATH = ROOT / "frontend" / "src" / "mocks" / "navigation.ts"
PAGE_CONTRACTS_PATH = ROOT / "docs" / "page_contracts.md"

TEMP_EXCEPTION_ROUTE_PAGE_CONTRACT_WHITELIST = {
    "/bond-analysis": (
        "temporary-exception live route; the current contract pack documents "
        "`/bond-dashboard` but not the governed `/bond-analysis` workbench yet."
    ),
    "/cross-asset": (
        "temporary-exception analytical route; current page contracts stop at "
        "`/market-data` and do not yet define a dedicated cross-asset PAGE."
    ),
    "/team-performance": (
        "temporary-exception route; no dedicated PAGE contract has been frozen yet."
    ),
    "/decision-items": (
        "temporary-exception route; decision items are documented as a section "
        "inside `PAGE-BALANCE-001`, not as a standalone page contract yet."
    ),
    "/macro-toolkit": (
        "temporary-exception macro tooling route; page-level contract is still deferred."
    ),
    "/stock-analysis": (
        "temporary-exception observation route; no governed page contract yet."
    ),
    "/platform-config": (
        "temporary-exception diagnostics/config route; outside the current page-contract pack."
    ),
    "/average-balance": (
        "temporary-exception analytical/compat route; formal truth remains on balance analysis."
    ),
    "/bank-ledger-dashboard": (
        "temporary-exception ledger cockpit route; contract still pending."
    ),
    "/concentration-monitor": (
        "temporary-exception satellite risk route; no standalone `PAGE-*` contract yet."
    ),
    "/cashflow-projection": (
        "temporary-exception liquidity route; no standalone `PAGE-*` contract yet."
    ),
    "/kpi": (
        "temporary-exception KPI route; no standalone `PAGE-*` contract yet."
    ),
    "/news-events": (
        "temporary-exception analytical route; `docs/page_contracts.md` only records "
        "it as a future analytical read surface note under market-data."
    ),
    "/pnl-by-business": (
        "temporary-exception route; business-line PnL still lacks a standalone page contract."
    ),
}

PAGE_HEADING_RE = re.compile(r"^##\s+[\d.]+\s+(PAGE-[A-Z0-9-]+)\b", re.MULTILINE)
FULL_PAGE_ID_RE = re.compile(r"PAGE-[A-Z0-9-]+")


@dataclass(frozen=True)
class LiveRoute:
    path: str
    governance_status: str | None


def _normalize_route_path(path: str) -> str:
    if "?" in path:
        path = path.split("?", maxsplit=1)[0]
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return path


def _iter_navigation_blocks(source: str) -> list[str]:
    blocks: list[str] = []
    in_array = False
    current: list[str] = []

    for line in source.splitlines():
        if not in_array:
            if line.startswith("export const workbenchNavigation:"):
                in_array = True
            continue

        if line.strip() == "];":
            if current:
                blocks.append("\n".join(current))
            break

        if line.strip() == "{":
            current = [line]
            continue

        if current:
            current.append(line)
            if line.strip() == "},":
                blocks.append("\n".join(current))
                current = []

    return blocks


def _parse_live_routes() -> list[LiveRoute]:
    source = NAVIGATION_PATH.read_text(encoding="utf-8")
    routes: list[LiveRoute] = []

    for block in _iter_navigation_blocks(source):
        path_match = re.search(r'path:\s*"([^"]+)"', block)
        readiness_match = re.search(r'readiness:\s*"([^"]+)"', block)
        governance_match = re.search(r'governanceStatus:\s*"([^"]+)"', block)
        if path_match is None or readiness_match is None:
            continue
        if readiness_match.group(1) != "live":
            continue
        routes.append(
            LiveRoute(
                path=_normalize_route_path(path_match.group(1)),
                governance_status=governance_match.group(1) if governance_match else None,
            )
        )

    return routes


def _extract_page_sections() -> dict[str, str]:
    text = PAGE_CONTRACTS_PATH.read_text(encoding="utf-8")
    matches = list(PAGE_HEADING_RE.finditer(text))
    sections: dict[str, str] = {}

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[start:end]

    return sections


def _extract_primary_route(section_text: str) -> str | None:
    header_window = "\n".join(section_text.splitlines()[:30])
    paths = [
        _normalize_route_path(path)
        for path in re.findall(r"`(/[^`]*)`", header_window)
        if not path.startswith("/api/")
        and not path.startswith("/ui/")
        and "*" not in path
    ]
    return paths[0] if paths else None


def _build_route_to_page_map() -> dict[str, str]:
    route_to_page: dict[str, str] = {}
    duplicates: list[str] = []

    for page_id, section_text in _extract_page_sections().items():
        route = _extract_primary_route(section_text)
        if route is None:
            continue
        existing = route_to_page.get(route)
        if existing is not None and existing != page_id:
            duplicates.append(f"{route}: {existing}, {page_id}")
            continue
        route_to_page[route] = page_id

    if duplicates:
        pytest.fail(
            "Primary route extraction mapped the same route to multiple page contracts:\n"
            + "\n".join(f"- {item}" for item in duplicates)
        )

    return route_to_page


def test_live_routes_have_page_contracts_or_explicit_temporary_exception_whitelist():
    live_routes = _parse_live_routes()
    live_by_path = {route.path: route for route in live_routes}
    route_to_page = _build_route_to_page_map()

    unknown_whitelist = sorted(
        path for path in TEMP_EXCEPTION_ROUTE_PAGE_CONTRACT_WHITELIST if path not in live_by_path
    )
    non_temp_exception_whitelist = sorted(
        path
        for path, route in live_by_path.items()
        if path in TEMP_EXCEPTION_ROUTE_PAGE_CONTRACT_WHITELIST
        and route.governance_status != "temporary-exception"
    )
    stale_whitelist = sorted(
        path for path in TEMP_EXCEPTION_ROUTE_PAGE_CONTRACT_WHITELIST if path in route_to_page
    )
    missing = sorted(
        path
        for path in live_by_path
        if path not in route_to_page
        and path not in TEMP_EXCEPTION_ROUTE_PAGE_CONTRACT_WHITELIST
    )

    if unknown_whitelist or non_temp_exception_whitelist or stale_whitelist or missing:
        lines = ["Live route -> page contract completeness gap report:"]

        if missing:
            lines.append(f"unexpected_missing={len(missing)}")
            lines.extend(
                f"- {path}: live in navigation but missing a dedicated `PAGE-*` section in "
                f"`docs/page_contracts.md`."
                for path in missing
            )

        if stale_whitelist:
            lines.append(f"stale_whitelist={len(stale_whitelist)}")
            lines.extend(
                f"- {path}: now resolves to `{route_to_page[path]}`; remove it from "
                "`TEMP_EXCEPTION_ROUTE_PAGE_CONTRACT_WHITELIST`."
                for path in stale_whitelist
            )

        if non_temp_exception_whitelist:
            lines.append(f"invalid_whitelist_status={len(non_temp_exception_whitelist)}")
            lines.extend(
                f"- {path}: whitelist is reserved for `temporary-exception` routes, but "
                f"navigation now reports `{live_by_path[path].governance_status}`."
                for path in non_temp_exception_whitelist
            )

        if unknown_whitelist:
            lines.append(f"unknown_whitelist={len(unknown_whitelist)}")
            lines.extend(
                f"- {path}: no longer appears as a live route; remove the whitelist entry."
                for path in unknown_whitelist
            )

        pytest.fail("\n".join(lines))
