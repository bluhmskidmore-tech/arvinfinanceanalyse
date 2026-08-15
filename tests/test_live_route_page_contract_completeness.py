"""
Contract source:
- `frontend/src/app/navigation.ts` `workbenchNavigation`
- `docs/page_contracts.md` `PAGE-*` sections and their primary or explicitly governed detail routes

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

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.helpers import ROOT

NAVIGATION_PATH = ROOT / "frontend" / "src" / "app" / "navigation.ts"
PAGE_CONTRACTS_PATH = ROOT / "docs" / "page_contracts.md"
ROUTE_MATURITY_PATH = ROOT / "docs" / "live_route_maturity.md"

TEMP_EXCEPTION_ROUTE_PAGE_CONTRACT_WHITELIST = {
    "/market-finance": (
        "temporary-exception collaboration workbench; reuses market/PnL/balance reads without a dedicated PAGE yet."
    ),
    "/team-performance": (
        "temporary-exception route; no dedicated PAGE contract has been frozen yet."
    ),
    "/decision-items": (
        "temporary-exception route; decision items are documented as a section "
        "inside `PAGE-BALANCE-001`, not as a standalone page contract yet."
    ),
    "/stock-analysis": (
        "temporary-exception observation route; no governed page contract yet."
    ),
    "/platform-config": (
        "temporary-exception diagnostics/config route; outside the current page-contract pack."
    ),

    "/kpi": (
        "temporary-exception KPI route; no standalone `PAGE-*` contract yet."
    ),
    "/news-events": (
        "temporary-exception analytical route; `docs/page_contracts.md` only records "
        "it as a future analytical read surface note under market-data."
    ),
}

PAGE_HEADING_RE = re.compile(r"^##\s+[\d.]+\s+(PAGE-[A-Z0-9-]+)\b", re.MULTILINE)
FULL_PAGE_ID_RE = re.compile(r"PAGE-[A-Z0-9-]+")
TEMP_EXCEPTION_SIGNOFF_RE = re.compile(
    r"^- `(?P<route>/[^`]+)`: signoff_owner=`(?P<owner>[^`]+)`, "
    r"signoff_status=`(?P<status>[^`]+)`, "
    r"exposure_class=`(?P<exposure_class>[^`]+)`, "
    r"signoff_scope=`(?P<scope>[^`]+)`$"
)


@dataclass(frozen=True)
class LiveRoute:
    path: str
    governance_status: str | None


@dataclass(frozen=True)
class RouteMaturity:
    route: str
    nav_state: str
    maturity_tier: str
    page_contract: str
    owner: str
    risk: str
    exit_condition: str
    review_date: str
    verification: str


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


def _extract_governed_detail_routes(section_text: str) -> list[str]:
    return [
        _normalize_route_path(path)
        for path in re.findall(
            r"^- Governed detail route: `(/[^`]*)`$",
            section_text,
            re.MULTILINE,
        )
    ]


def _build_route_to_page_map() -> dict[str, str]:
    route_to_page: dict[str, str] = {}
    duplicates: list[str] = []

    for page_id, section_text in _extract_page_sections().items():
        primary_route = _extract_primary_route(section_text)
        routes = _extract_governed_detail_routes(section_text)
        if primary_route is not None:
            routes.insert(0, primary_route)
        for route in routes:
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


def _parse_markdown_table(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    header: list[str] | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append(dict(zip(header, cells, strict=True)))

    return rows


def _parse_route_maturity_registry() -> dict[str, RouteMaturity]:
    assert ROUTE_MATURITY_PATH.exists(), (
        "`docs/live_route_maturity.md` must exist and list every live route "
        "with maturity tier, owner, risk, exit condition, review date, and verification."
    )

    rows = _parse_markdown_table(ROUTE_MATURITY_PATH)
    required_columns = {
        "route",
        "nav_state",
        "maturity_tier",
        "page_contract",
        "owner",
        "risk",
        "exit_condition",
        "review_date",
        "verification",
    }
    if not rows:
        pytest.fail("`docs/live_route_maturity.md` has no route maturity rows.")

    missing_columns = required_columns - set(rows[0])
    if missing_columns:
        pytest.fail(
            "`docs/live_route_maturity.md` is missing columns: "
            + ", ".join(sorted(missing_columns))
        )

    registry: dict[str, RouteMaturity] = {}
    duplicates: list[str] = []

    for row in rows:
        route = _normalize_route_path(row["route"])
        if route in registry:
            duplicates.append(route)
            continue
        registry[route] = RouteMaturity(
            route=route,
            nav_state=row["nav_state"],
            maturity_tier=row["maturity_tier"],
            page_contract=row["page_contract"],
            owner=row["owner"],
            risk=row["risk"],
            exit_condition=row["exit_condition"],
            review_date=row["review_date"],
            verification=row["verification"],
        )

    if duplicates:
        pytest.fail(
            "`docs/live_route_maturity.md` has duplicate route rows:\n"
            + "\n".join(f"- {route}" for route in sorted(duplicates))
        )

    return registry


def _parse_temporary_exception_signoffs() -> dict[str, dict[str, str]]:
    text = ROUTE_MATURITY_PATH.read_text(encoding="utf-8")
    heading = "## Temporary Exception Signoff List"
    assert heading in text, (
        "`docs/live_route_maturity.md` must include a temporary-exception signoff list."
    )
    section = text.split(heading, maxsplit=1)[1]
    if "\n## " in section:
        section = section.split("\n## ", maxsplit=1)[0]

    signoffs: dict[str, dict[str, str]] = {}
    duplicates: list[str] = []
    for line in section.splitlines():
        match = TEMP_EXCEPTION_SIGNOFF_RE.match(line.strip())
        if match is None:
            continue
        route = _normalize_route_path(match.group("route"))
        if route in signoffs:
            duplicates.append(route)
            continue
        signoffs[route] = {
            "owner": match.group("owner").strip(),
            "status": match.group("status").strip(),
            "exposure_class": match.group("exposure_class").strip(),
            "scope": match.group("scope").strip(),
        }

    if duplicates:
        pytest.fail(
            "`docs/live_route_maturity.md` has duplicate temporary-exception signoff rows:\n"
            + "\n".join(f"- {route}" for route in sorted(duplicates))
        )

    return signoffs


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
                    f"`docs/page_contracts.md` or an explicit governed-detail mapping."
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


def test_live_routes_have_maturity_registry_rows():
    live_routes = _parse_live_routes()
    live_by_path = {route.path: route for route in live_routes}
    registry = _parse_route_maturity_registry()

    missing = sorted(path for path in live_by_path if path not in registry)
    stale = sorted(path for path in registry if path not in live_by_path)

    if missing or stale:
        lines = ["Live route maturity registry gap report:"]
        if missing:
            lines.append(f"missing={len(missing)}")
            lines.extend(f"- {path}: live in navigation but absent from route maturity registry." for path in missing)
        if stale:
            lines.append(f"stale={len(stale)}")
            lines.extend(f"- {path}: present in route maturity registry but not live in navigation." for path in stale)
        pytest.fail("\n".join(lines))


def test_live_route_maturity_page_contract_matches_mapped_route_contract():
    route_to_page = _build_route_to_page_map()
    registry = _parse_route_maturity_registry()
    mismatches = [
        f"{route}: maturity={registry[route].page_contract}, contract={page_id}"
        for route, page_id in route_to_page.items()
        if route in registry and registry[route].page_contract != page_id
    ]

    assert mismatches == []


def test_temporary_exception_routes_have_burn_down_metadata():
    live_routes = _parse_live_routes()
    registry = _parse_route_maturity_registry()
    allowed_tiers = {
        "governed",
        "governed-mixed-source",
        "candidate",
        "temporary-exception",
        "placeholder",
        "excluded",
    }
    missing: list[str] = []

    for route in live_routes:
        maturity = registry[route.path]
        expected_nav_state = (
            "temporary-exception"
            if route.governance_status == "temporary-exception"
            else "live"
        )
        if maturity.nav_state != expected_nav_state:
            missing.append(
                f"{route.path}: nav_state={maturity.nav_state!r}, expected {expected_nav_state!r}."
            )
        if maturity.maturity_tier not in allowed_tiers:
            missing.append(
                f"{route.path}: maturity_tier={maturity.maturity_tier!r} is not one of {sorted(allowed_tiers)}."
            )
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", maturity.review_date):
            missing.append(f"{route.path}: review_date must be YYYY-MM-DD.")
        for field_name in ("owner", "risk", "exit_condition", "verification"):
            value = getattr(maturity, field_name)
            if value.strip() in {"", "-", "TBD", "none"}:
                missing.append(f"{route.path}: {field_name} must be explicit.")
        if route.governance_status == "temporary-exception":
            for field_name in ("owner", "risk", "exit_condition"):
                value = getattr(maturity, field_name)
                if len(value.strip()) < 12:
                    missing.append(
                        f"{route.path}: temporary-exception {field_name} is too terse."
                    )

    if missing:
        pytest.fail(
            "Route maturity burn-down metadata gaps:\n"
            + "\n".join(f"- {item}" for item in missing)
        )


def test_temporary_exception_signoff_validation_rejects_owner_mismatch():
    registry = {
        "/temporary-page": RouteMaturity(
            route="/temporary-page",
            nav_state="temporary-exception",
            maturity_tier="temporary-exception",
            page_contract="GAP-TEMPORARY-PAGE",
            owner="Expected owner",
            risk="Temporary route can be overread as approved truth.",
            exit_condition="Add a dedicated page contract with visible boundaries.",
            review_date="2026-06-14",
            verification="python -m pytest tests/test_live_route_page_contract_completeness.py -q",
        )
    }
    signoffs = {
        "/temporary-page": {
            "owner": "Different owner",
            "status": "pending-owner-review",
            "exposure_class": "pending-confirmation",
            "scope": "Temporary route remains visible only while burn-down row is active.",
        }
    }

    gaps = _temporary_exception_signoff_gaps(
        registry=registry,
        signoffs=signoffs,
    )

    assert gaps == [
        "/temporary-page: signoff_owner='Different owner' must match registry owner "
        "'Expected owner'."
    ]


def _temporary_exception_signoff_gaps(
    *,
    registry: dict[str, RouteMaturity],
    signoffs: dict[str, dict[str, str]],
) -> list[str]:
    allowed_statuses = {
        "pending-owner-review",
        "owner-accepted-temporary",
        "ready-for-contract",
    }
    allowed_exposure_classes = {
        "demo-visible",
        "production-governed",
        "pending-confirmation",
        "debug-only",
    }
    gaps: list[str] = []

    for route, signoff in sorted(signoffs.items()):
        if signoff["status"] not in allowed_statuses:
            gaps.append(
                f"{route}: signoff_status={signoff['status']!r} is not one of {sorted(allowed_statuses)}."
            )
        if signoff["exposure_class"] not in allowed_exposure_classes:
            gaps.append(
                f"{route}: exposure_class={signoff['exposure_class']!r} is not one of "
                f"{sorted(allowed_exposure_classes)}."
            )
        registry_owner = registry.get(route).owner if route in registry else None
        if registry_owner is not None and signoff["owner"] != registry_owner:
            gaps.append(
                f"{route}: signoff_owner={signoff['owner']!r} must match registry owner "
                f"{registry_owner!r}."
            )
        for field_name in ("owner", "scope"):
            value = signoff[field_name]
            if value.strip() in {"", "-", "TBD", "none"} or len(value.strip()) < 8:
                gaps.append(f"{route}: signoff_{field_name} must be explicit.")

    return gaps


def test_temporary_exception_routes_have_explicit_signoff_list():
    live_routes = _parse_live_routes()
    temporary_routes = {
        route.path
        for route in live_routes
        if route.governance_status == "temporary-exception"
    }
    registry = _parse_route_maturity_registry()
    signoffs = _parse_temporary_exception_signoffs()

    missing = sorted(temporary_routes - set(signoffs))
    stale = sorted(set(signoffs) - temporary_routes)
    invalid = _temporary_exception_signoff_gaps(
        registry=registry,
        signoffs=signoffs,
    )

    if missing or stale or invalid:
        lines = ["Temporary-exception signoff list gaps:"]
        if missing:
            lines.append(f"missing={len(missing)}")
            lines.extend(f"- {route}: missing signoff list entry." for route in missing)
        if stale:
            lines.append(f"stale={len(stale)}")
            lines.extend(f"- {route}: no longer a temporary-exception live route." for route in stale)
        lines.extend(f"- {item}" for item in invalid)
        pytest.fail("\n".join(lines))


def test_temporary_exception_exposure_classes_are_defined_for_owner_signoff():
    text = ROUTE_MATURITY_PATH.read_text(encoding="utf-8")
    required_heading = "## Temporary Exception Exposure Class Definitions"
    assert required_heading in text, (
        "`docs/live_route_maturity.md` must define the temporary-exception "
        "exposure classes used by owner signoff rows."
    )
    section = text.split(required_heading, maxsplit=1)[1]
    if "\n## " in section:
        section = section.split("\n## ", maxsplit=1)[0]

    definitions = {
        "demo-visible": "can be shown for demonstration",
        "production-governed": "can be used in production",
        "pending-confirmation": "requires owner confirmation",
        "debug-only": "diagnostics or operator debugging only",
    }
    missing = [
        f"{exposure_class}: expected definition to include {meaning!r}"
        for exposure_class, meaning in definitions.items()
        if f"- `{exposure_class}`:" not in section or meaning not in section
    ]
    assert not missing, (
        "Temporary-exception exposure class definition gaps:\n"
        + "\n".join(f"- {item}" for item in missing)
    )
