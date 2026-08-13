"""Two-way drift guard for the 2026-08-13 interest-spread metric promotion.

Contract sources:
- `docs/metric_dictionary.md` section 12.3.2
- `docs/page_contracts.md` section 14 `PAGE-PROD-CAT-PNL-001` subsection F.2
- `tests/golden_samples/GS-PROD-CAT-PNL-A/assertions.md`
- `backend/app/schemas/product_category_pnl.py`

The guard fails in three directions:
- a `MTR-PCP-013`..`MTR-PCP-029` dictionary row whose declared payload path does not exist in the
  backend schema (dictionary claims a metric the code does not produce);
- a field on `interest_spread` / `interest_earning_spread` / `liability_cost_decomposition` that has
  no dictionary row, page-contract binding, or golden-sample binding (code produces an ungoverned
  metric);
- a stale `pending_backend_landing` registration in the dictionary, i.e. an id still marked as
  awaiting backend delivery after the backend field actually landed.

`pending_backend_landing` follows the existing whitelist convention in
`tests/test_metric_dictionary_golden_sample_completeness.py`: approved-but-undelivered metric ids are
declared in the governance doc itself, and the declaration must go stale-free.

One cross-layer guard also reads `ProductCategoryPnlPage.tsx` statically, following the precedent in
`tests/test_no_finance_logic_in_frontend.py`. It enforces the *invariant* that the two spread charts
never share an asset-yield or spread series name, which the frontend suite can only pin as frozen
literals. See `test_two_spread_charts_cannot_share_asset_or_spread_series_names`.
"""

from __future__ import annotations

import re
import types
import typing

from pydantic import BaseModel

from backend.app.schemas import product_category_pnl as schemas
from tests.helpers import ROOT

METRIC_DICTIONARY = ROOT / "docs" / "metric_dictionary.md"
PAGE_CONTRACTS = ROOT / "docs" / "page_contracts.md"
GOLDEN_ASSERTIONS = ROOT / "tests" / "golden_samples" / "GS-PROD-CAT-PNL-A" / "assertions.md"

SPREAD_METRIC_IDS = tuple(f"MTR-PCP-{index:03d}" for index in range(13, 30))

# Payload sections promoted to formal metrics on 2026-08-13. Row-level detail fields stay governed by
# `MTR-PCP-004`..`MTR-PCP-012` and are deliberately out of scope here.
GOVERNED_PAYLOAD_SECTIONS = frozenset(
    {
        "interest_spread",
        "interest_earning_spread",
        "liability_cost_decomposition",
    }
)

ROW_PAYLOAD_FIELDS = frozenset({"rows", "asset_total", "liability_total", "grand_total"})

DICTIONARY_ROW_RE = re.compile(r"^\| `(MTR-PCP-0(?:1[3-9]|2[0-9]))` \|")
PENDING_LANDING_RE = re.compile(r"^- `pending_backend_landing: (.+)`$", re.MULTILINE)

PRODUCT_CATEGORY_PAGE = (
    ROOT
    / "frontend"
    / "src"
    / "features"
    / "product-category-pnl"
    / "pages"
    / "ProductCategoryPnlPage.tsx"
)

SERIES_NAME_RE = re.compile(r'name:\s*"([^"]+)"')


def _unwrap_optional(annotation: object) -> object:
    origin = typing.get_origin(annotation)
    if origin is typing.Union or isinstance(annotation, types.UnionType):
        args = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _resolve_payload_path(path: str) -> object | None:
    """Resolve `ProductCategoryPnlPayload.<section>.<field>` against the live pydantic models."""
    head, *rest = path.split(".")
    current: object | None = getattr(schemas, head, None)
    for part in rest:
        fields = getattr(current, "model_fields", None)
        if not fields or part not in fields:
            return None
        current = _unwrap_optional(fields[part].annotation)
    return current


def _dictionary_spread_rows() -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in METRIC_DICTIONARY.read_text(encoding="utf-8").splitlines():
        if not DICTIONARY_ROW_RE.match(line):
            continue
        columns = [column.strip() for column in line.strip().strip("|").split("|")]
        rows[columns[0].strip("`")] = columns
    return rows


def _declared_authority_path(columns: list[str]) -> str:
    return columns[4].strip("`")


def _pending_backend_landing_ids() -> set[str]:
    """Metric ids the dictionary declares as approved but not yet delivered by the backend."""
    matches = PENDING_LANDING_RE.findall(METRIC_DICTIONARY.read_text(encoding="utf-8"))
    entries = {item.strip() for match in matches for item in match.split(",")}
    return {entry for entry in entries if entry and entry != "none"}


def _landed_sections() -> set[str]:
    return {
        section
        for section in GOVERNED_PAYLOAD_SECTIONS
        if section in schemas.ProductCategoryPnlPayload.model_fields
    }


def _section_field_paths() -> dict[str, str]:
    """Every landed payload-section leaf field, as `ProductCategoryPnlPayload.<section>.<field>`."""
    paths: dict[str, str] = {}
    for section in sorted(_landed_sections()):
        section_model = _unwrap_optional(
            schemas.ProductCategoryPnlPayload.model_fields[section].annotation
        )
        for field_name in section_model.model_fields:
            paths[f"ProductCategoryPnlPayload.{section}.{field_name}"] = section
    return paths


def _pending_paths() -> set[str]:
    rows = _dictionary_spread_rows()
    return {
        _declared_authority_path(rows[metric_id])
        for metric_id in _pending_backend_landing_ids()
        if metric_id in rows
    }


def test_promoted_payload_sections_are_all_governed() -> None:
    section_fields = {
        name
        for name, field in schemas.ProductCategoryPnlPayload.model_fields.items()
        if name not in ROW_PAYLOAD_FIELDS
        and isinstance(_unwrap_optional(field.annotation), type)
        and issubclass(_unwrap_optional(field.annotation), BaseModel)
    }

    ungoverned = sorted(section_fields - GOVERNED_PAYLOAD_SECTIONS)
    assert not ungoverned, (
        "ProductCategoryPnlPayload gained a payload section with no governance. Every section-level "
        "payload block needs a metric dictionary matrix (docs/metric_dictionary.md section 12.3.2), "
        "a page contract binding (PAGE-PROD-CAT-PNL-001 subsection F.2), and golden-sample "
        f"assertions before it can ship. Ungoverned sections: {ungoverned}"
    )


def test_dictionary_spread_rows_bind_fields_the_backend_actually_produces() -> None:
    rows = _dictionary_spread_rows()

    assert sorted(rows) == sorted(SPREAD_METRIC_IDS), (
        "docs/metric_dictionary.md section 12.3.2 must define exactly "
        f"{SPREAD_METRIC_IDS[0]}..{SPREAD_METRIC_IDS[-1]}; found {sorted(rows)}"
    )

    pending = _pending_backend_landing_ids()
    assert pending <= set(SPREAD_METRIC_IDS), (
        f"`pending_backend_landing` names ids outside section 12.3.2: {sorted(pending - set(SPREAD_METRIC_IDS))}"
    )

    unresolved = {
        metric_id
        for metric_id in SPREAD_METRIC_IDS
        if _resolve_payload_path(_declared_authority_path(rows[metric_id])) is None
    }

    undeclared = sorted(unresolved - pending)
    assert not undeclared, (
        "Metric dictionary declares payload paths the backend schema does not produce, without a "
        "`pending_backend_landing` registration. Either the backend field was renamed/removed, or "
        "the dictionary row is stale:\n"
        + "\n".join(f"- {metric_id} -> {_declared_authority_path(rows[metric_id])}" for metric_id in undeclared)
    )

    stale = sorted(pending - unresolved)
    assert not stale, (
        "Stale `pending_backend_landing` registration in docs/metric_dictionary.md section 12.3.2: "
        "these metric ids now exist in the backend schema, so remove them from the pending line and "
        "add the section to tests/golden_samples/GS-PROD-CAT-PNL-A/response.json plus "
        f"tests/test_golden_samples_capture_ready.py::_validate_product_category. Stale ids: {stale}"
    )


def test_every_landed_payload_field_has_exactly_one_dictionary_row() -> None:
    rows = _dictionary_spread_rows()
    declared_paths = [_declared_authority_path(columns) for columns in rows.values()]
    expected_paths = set(_section_field_paths())

    duplicates = sorted({path for path in declared_paths if declared_paths.count(path) > 1})
    assert not duplicates, f"Duplicate metric bindings for the same payload path: {duplicates}"

    missing = sorted(expected_paths - set(declared_paths))
    extra = sorted(set(declared_paths) - expected_paths - _pending_paths())

    assert not missing, (
        "Backend produces governed payload fields with no metric dictionary row. Add a "
        "`MTR-PCP-*` row in docs/metric_dictionary.md section 12.3.2 before shipping:\n"
        + "\n".join(f"- {path}" for path in missing)
    )
    assert not extra, (
        "Metric dictionary binds payload paths outside the governed, landed sections:\n"
        + "\n".join(f"- {path}" for path in extra)
    )


def test_spread_dictionary_rows_are_business_formal_metrics() -> None:
    for metric_id, columns in _dictionary_spread_rows().items():
        assert columns[2] == "business", f"{metric_id} type column is {columns[2]!r}"
        assert columns[3].strip("`") == "formal", f"{metric_id} basis column is {columns[3]!r}"


def test_spread_metrics_are_bound_in_page_contract_and_golden_sample() -> None:
    page_contracts = PAGE_CONTRACTS.read_text(encoding="utf-8")
    product_category_section = page_contracts.split("## 14. PAGE-PROD-CAT-PNL-001", maxsplit=1)[
        1
    ].split("## 14.1 PAGE-AGENT-001", maxsplit=1)[0]
    golden_assertions = GOLDEN_ASSERTIONS.read_text(encoding="utf-8")

    for metric_id, columns in _dictionary_spread_rows().items():
        # Page contract and golden sample use the outward `result.<section>.<field>` path.
        outward_path = _declared_authority_path(columns).replace(
            "ProductCategoryPnlPayload.", "result."
        )
        assert metric_id in product_category_section, f"{metric_id} missing from PAGE-PROD-CAT-PNL-001"
        assert (
            f"`{outward_path}`" in product_category_section
        ), f"{metric_id} field path {outward_path} missing from PAGE-PROD-CAT-PNL-001"
        assert metric_id in golden_assertions, f"{metric_id} missing from GS-PROD-CAT-PNL-A assertions"
        assert (
            f"`{outward_path}`" in golden_assertions
        ), f"{metric_id} field path {outward_path} missing from GS-PROD-CAT-PNL-A assertions"


def test_cln_drag_bp_unit_contract_is_documented_and_supported() -> None:
    dictionary = METRIC_DICTIONARY.read_text(encoding="utf-8")
    cln_drag_row = _dictionary_spread_rows()["MTR-PCP-028"]
    assert _declared_authority_path(cln_drag_row).endswith("liability_cost_decomposition.cln_drag_bp")
    assert '`unit="bp"`' in cln_drag_row[6], "MTR-PCP-028 display rule must state the bp unit"
    assert '`unit="bp"`' in dictionary

    if "MTR-PCP-028" in _pending_backend_landing_ids():
        return

    unit_annotation = schemas.ProductCategoryMetricValue.model_fields["unit"].annotation
    assert set(typing.get_args(unit_annotation)) == {"percent", "bp"}, (
        "MTR-PCP-028 is no longer pending, so ProductCategoryMetricValue.unit must accept `bp`."
    )


def test_two_spread_calibers_stay_explicitly_distinguished() -> None:
    dictionary = METRIC_DICTIONARY.read_text(encoding="utf-8")
    page_contracts = PAGE_CONTRACTS.read_text(encoding="utf-8")
    golden_assertions = GOLDEN_ASSERTIONS.read_text(encoding="utf-8")

    for required in (
        "两个利差的口径差异（必须显式区分）",
        "不含 `141`（TPL）",
        "含 `141`（TPL）",
        "`0.78%`（78BP）",
        "`0.93%`（93BP）",
        "同一报告日的 monthly 与 ytd 利差不同属正常",
        "被解释为外币口径或美元负债成本",
    ):
        assert required in dictionary, f"missing caliber statement in metric dictionary: {required}"

    for required in (
        "两个利差必须分别标注口径",
        "monthly / ytd 双口径",
        "78BP 与 93BP",
        "不得据此给出美元/外币负债成本结论",
    ):
        assert required in page_contracts, f"missing caliber statement in page contract: {required}"

    for required in (
        "They must never be presented under the same series name.",
        "A missing denominator or a missing `credit_linked_notes` row yields `null`, never `0`.",
        "do not recompute and\n  overwrite them from a local run",
    ):
        assert required in golden_assertions, f"missing statement in golden assertions: {required}"


def test_annualization_and_days_for_view_caliber_are_documented() -> None:
    dictionary = METRIC_DICTIONARY.read_text(encoding="utf-8")

    for required in (
        "weighted_yield_pct = cash / days_for_view * 365 / scale * 100",
        "spread_pct         = asset_yield_pct - liability_yield_pct",
        "cln_drag_bp        = (liability_yield_pct - liability_yield_ex_cln_pct) * 100",
        "年化基数固定 `365`",
        "`_days_for_view(report_date, view)`",
        "**不得回落为 0**",
    ):
        assert required in dictionary, f"missing formula statement: {required}"


def _chart_series_names(option_symbol: str) -> list[str]:
    """Series names declared inside one `useMemo` chart-option block on the product-category page."""
    source = PRODUCT_CATEGORY_PAGE.read_text(encoding="utf-8")
    anchor = f"\n  const {option_symbol} = useMemo("
    start = source.find(anchor)
    assert start != -1, (
        f"{option_symbol} chart-option block not found in {PRODUCT_CATEGORY_PAGE.name}. If the chart "
        "was renamed or restructured, update this guard rather than deleting it."
    )
    next_declaration = source.find("\n  const ", start + len(anchor))
    block = source[start:next_declaration] if next_declaration != -1 else source[start:]
    return SERIES_NAME_RE.findall(block)


def test_two_spread_charts_cannot_share_asset_or_spread_series_names() -> None:
    """Cross-layer invariant behind `MTR-PCP-015` vs `MTR-PCP-021` (78BP vs 93BP).

    `frontend/src/test/ProductCategoryPnlPage.test.tsx` pins today's legend strings with `toEqual`,
    which does catch a straight revert. It cannot catch a *good-faith rename* that updates both the
    page and those frozen literals and happens to land on the same name for both charts. This guard
    encodes the invariant instead of the wording.
    """
    with_tpl = _chart_series_names("interestSpreadOption")
    interest_earning = _chart_series_names("interestEarningSpreadOption")

    assert len(with_tpl) == 3, f"expected 3 series on the with-TPL spread chart, got {with_tpl}"
    assert len(interest_earning) == 3, (
        f"expected 3 series on the interest-earning spread chart, got {interest_earning}"
    )

    tpl_asset, tpl_liability, tpl_spread = with_tpl
    earning_asset, earning_liability, earning_spread = interest_earning

    # The liability line is the documented same-source mirror (`MTR-PCP-014` / `MTR-PCP-020`), so the
    # two charts are expected to share exactly this one name.
    assert tpl_liability == earning_liability, (
        "The two spread charts read the same `liability_total` line, so their liability series should "
        f"stay identically named. Got {tpl_liability!r} vs {earning_liability!r}."
    )

    for label, tpl_name, earning_name in (
        ("asset-yield", tpl_asset, earning_asset),
        ("spread", tpl_spread, earning_spread),
    ):
        assert tpl_name != earning_name, (
            f"The two spread charts share the same {label} series name {tpl_name!r}. "
            "`MTR-PCP-021` (asset-side caliber, includes TPL / derivatives / intermediate business) "
            "and `MTR-PCP-015` (interest-earning caliber, excludes them) are 93BP and 78BP on "
            "2026-07-31/ytd. docs/metric_dictionary.md section 12.3.2 and PAGE-PROD-CAT-PNL-001 "
            "subsection F.2 forbid presenting them under a shared series name."
        )

    crosswise = {tpl_asset, tpl_spread} & {earning_asset, earning_spread}
    assert not crosswise, (
        "An asset-yield or spread series name is reused across the two spread charts in a different "
        f"position, which is just as ambiguous for a reader: {sorted(crosswise)}"
    )

    # Caliber marking, asserted as a property rather than as a frozen string so the guard survives
    # legitimate rewording.
    assert "TPL" in tpl_asset and "TPL" in tpl_spread, (
        "The with-TPL chart must mark its caliber in the asset-yield and spread series names, "
        f"otherwise it reads as the interest-earning caliber. Got {with_tpl}."
    )
    assert "TPL" not in earning_asset and "TPL" not in earning_spread, (
        "The interest-earning chart excludes TPL, so its series names must not claim otherwise. "
        f"Got {interest_earning}."
    )
