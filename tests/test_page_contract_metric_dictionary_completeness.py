from __future__ import annotations

"""
Contract source:
- `docs/page_contracts.md` `PAGE-*` sections and their markdown metric tables
- `docs/metric_dictionary.md` canonical `MTR-*` definitions

Whitelist:
- `PAGES_WITHOUT_FORMAL_METRIC_BINDINGS` lists page contracts that intentionally
  carry no approved `metric_id` bindings yet, or are narrative-only by design.
- If any whitelisted page later gains metric rows, this test fails so the
  whitelist can be cleaned up immediately.

Follow-up plan:
- Replace each whitelist entry with real `metric_id` rows once the page-level
  binding is approved.
- Keep the failure list focused on missing or stale bindings instead of broad
  document rewrites.
"""

import re

import pytest

from tests.helpers import ROOT

PAGE_CONTRACTS_PATH = ROOT / "docs" / "page_contracts.md"
METRIC_DICTIONARY_PATH = ROOT / "docs" / "metric_dictionary.md"

PAGES_WITHOUT_FORMAL_METRIC_BINDINGS = {
    "PAGE-EXEC-SUMMARY-001": (
        "narrative-only executive summary; no business metric bindings by design."
    ),
    "PAGE-BOND-001": (
        "candidate / blocked-by-contract-gap; page contract keeps display-field truth "
        "without promoting standalone `MTR-*` bindings yet."
    ),
    "PAGE-POS-001": (
        "positions DTO remains page/schema truth only; no approved `MTR-*` page bindings yet."
    ),
}

PAGE_HEADING_RE = re.compile(r"^##\s+[\d.]+\s+(PAGE-[A-Z0-9-]+)\b", re.MULTILINE)
FULL_METRIC_ID_RE = re.compile(r"\bMTR-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d+[A-Z]?\b")


def _extract_page_sections() -> dict[str, str]:
    text = PAGE_CONTRACTS_PATH.read_text(encoding="utf-8")
    matches = list(PAGE_HEADING_RE.finditer(text))
    sections: dict[str, str] = {}

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[start:end]

    return sections


def _extract_metric_ids_from_section(section_text: str) -> set[str]:
    return set(FULL_METRIC_ID_RE.findall(section_text))


def test_page_contract_metric_bindings_exist_in_metric_dictionary():
    page_sections = _extract_page_sections()
    metric_dictionary_ids = set(
        FULL_METRIC_ID_RE.findall(METRIC_DICTIONARY_PATH.read_text(encoding="utf-8"))
    )

    unknown_whitelist = sorted(
        page_id for page_id in PAGES_WITHOUT_FORMAL_METRIC_BINDINGS if page_id not in page_sections
    )

    missing_by_page: list[tuple[str, list[str]]] = []
    stale_whitelist: list[str] = []
    unexpected_pages_without_metrics: list[str] = []

    for page_id, section_text in sorted(page_sections.items()):
        page_metric_ids = _extract_metric_ids_from_section(section_text)
        missing_metric_ids = sorted(page_metric_ids - metric_dictionary_ids)

        if missing_metric_ids:
            missing_by_page.append((page_id, missing_metric_ids))

        if not page_metric_ids and page_id not in PAGES_WITHOUT_FORMAL_METRIC_BINDINGS:
            unexpected_pages_without_metrics.append(page_id)

        if page_metric_ids and page_id in PAGES_WITHOUT_FORMAL_METRIC_BINDINGS:
            stale_whitelist.append(page_id)

    if unknown_whitelist or missing_by_page or stale_whitelist or unexpected_pages_without_metrics:
        lines = ["Page contract -> metric dictionary completeness gap report:"]

        if missing_by_page:
            lines.append(f"missing_metric_ids={sum(len(ids) for _, ids in missing_by_page)}")
            for page_id, metric_ids in missing_by_page:
                lines.append(f"- {page_id}: missing from `docs/metric_dictionary.md` -> {', '.join(metric_ids)}")

        if unexpected_pages_without_metrics:
            lines.append(f"unexpected_pages_without_metrics={len(unexpected_pages_without_metrics)}")
            lines.extend(
                f"- {page_id}: page contract has no table-bound `MTR-*` rows and is not explicitly whitelisted."
                for page_id in unexpected_pages_without_metrics
            )

        if stale_whitelist:
            lines.append(f"stale_whitelist={len(stale_whitelist)}")
            lines.extend(
                f"- {page_id}: now has `MTR-*` rows; remove it from `PAGES_WITHOUT_FORMAL_METRIC_BINDINGS`."
                for page_id in stale_whitelist
            )

        if unknown_whitelist:
            lines.append(f"unknown_whitelist={len(unknown_whitelist)}")
            lines.extend(
                f"- {page_id}: whitelist entry no longer matches a `PAGE-*` section."
                for page_id in unknown_whitelist
            )

        pytest.fail("\n".join(lines))
