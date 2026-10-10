"""Compare the desktop homepage's current response contract with a local running API.

The CLI renders expected OpenAPI in its own fresh process without entering the
application lifespan. A passing fingerprint verifies response schemas only; it
does not attest the running process's complete implementation or business data.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api_contract_check import _load_openapi, _resolve_ref, _spec_sha256  # noqa: E402

HOME_GET_PATHS = (
    "/api/system-read-publication",
    "/ui/home/snapshot",
    "/ui/home/income-trend",
    "/ui/home/research-reports",
    "/ui/home/macro-release-context",
    "/api/ledger-pnl/candidate-financial-indicators",
    "/api/bond-dashboard/home-summary",
    "/api/bond-analytics/top-holdings",
    "/api/bond-analytics/position-changes",
    "/api/bond-analytics/portfolio-headlines",
    "/api/bond-analytics/credit-spread-migration",
    "/api/bond-analytics/return-decomposition",
    "/api/pnl-attribution/campisi/four-effects",
    "/api/bond-analytics/yield-curve-term-structure",
    "/api/bond-analytics/krd-curve-risk",
    "/ui/balance-analysis/dates",
    "/ui/balance-analysis/decision-items",
    "/ui/market-data/rates",
    "/ui/calendar/supply-auctions",
    "/ui/news/choice-events/latest-batch",
)
# Raw response fields used by the existing homepage clients. Numeric wire values
# may be Q8 strings or Numeric objects; their full shapes are compared separately.
HOME_CONSUMED_FIELDS = {
    "/ui/home/snapshot": (
        "result.report_date", "result.mode", "result.source_surface",
        "result.overview.metrics[].value", "result.attribution.segments[].amount",
        "result.domains_missing", "result.domains_effective_date",
    ),
    "/ui/home/income-trend": (
        "result.report_date", "result.window", "result.source_status",
        "result.points[].date", "result.points[].portfolio_pnl", "result.missing_components", "result.warnings",
    ),
    "/ui/home/research-reports": (
        "result.report_date", "result.source_status", "result.items[].title", "result.items[].published_at", "result.warnings",
    ),
    "/api/bond-analytics/top-holdings": (
        "result.report_date", "result.top_n", "result.items[].instrument_code",
        "result.items[].market_value", "result.total_market_value", "result.warnings", "result.computed_at",
    ),
    "/api/bond-analytics/position-changes": (
        "result.report_date", "result.prev_report_date", "result.source_status",
        "result.items[].change_market_value", "result.items[].direction", "result.total_market_value", "result.prev_total_market_value",
    ),
    "/api/bond-analytics/portfolio-headlines": (
        "result.report_date", "result.total_market_value", "result.weighted_duration",
        "result.total_dv01", "result.bond_count", "result.by_asset_class[].asset_class",
    ),
    "/api/bond-analytics/credit-spread-migration": (
        "result.report_date", "result.credit_bond_count", "result.credit_market_value", "result.spread_dv01",
        "result.spread_scenarios[].spread_change_bp", "result.spread_scenarios[].pnl_impact",
        "result.migration_scenarios[].scenario_name",
    ),
    "/api/bond-analytics/return-decomposition": (
        "result.report_date", "result.period_type", "result.period_start", "result.period_end",
        "result.carry", "result.actual_pnl", "result.by_asset_class[].asset_class",
        "result.by_accounting_class[].asset_class", "result.bond_details[].bond_code",
    ),
    "/api/bond-analytics/yield-curve-term-structure": (
        "result.report_date", "result.curves[].trade_date_resolved",
        "result.curves[].points[].yield_pct", "result.curves[].points[].delta_bp_prev",
    ),
    "/api/bond-analytics/krd-curve-risk": (
        "result.report_date", "result.portfolio_duration", "result.portfolio_dv01",
        "result.krd_buckets[].tenor", "result.krd_buckets[].dv01", "result.scenarios[].by_asset_class",
    ),
    "/ui/market-data/rates": (
        "result.read_target", "result.series[].series_id", "result.series[].value_numeric",
        "result.series[].trade_date", "result.series[].unit",
    ),
    "/ui/calendar/supply-auctions": (
        "result.series_id", "result.total_rows", "result.limit", "result.offset",
        "result.events[].event_date", "result.events[].event_kind", "result.events[].title",
    ),
    "/ui/news/choice-events/latest-batch": (
        "result.batches[].key", "result.batches[].events[].received_at",
        "result.batches[].events[].payload_text", "result.batches[].events[].payload_json",
    ),
}
# These are current expectation inputs, not evidence of the process's loaded files.
CONTRACT_SOURCE_PATHS = (
    "scripts/api_contract_check.py",
    "scripts/api_surface.py",
    "backend/app/main.py",
    "backend/app/api/routes/executive.py",
    "backend/app/api/routes/campisi_attribution.py",
    "backend/app/api/routes/bond_analytics.py",
    "backend/app/api/routes/bond_dashboard.py",
    "backend/app/api/routes/ledger_pnl.py",
    "backend/app/api/routes/balance_analysis.py",
    "backend/app/api/routes/macro_vendor.py",
    "backend/app/api/routes/research_calendar.py",
    "backend/app/api/routes/choice_news.py",
    "backend/app/api/routes/system_read_publication.py",
    "backend/app/schemas/campisi_attribution_read.py",
    "backend/app/schemas/bond_dashboard.py",
    "backend/app/schemas/balance_analysis.py",
    "backend/app/schemas/candidate_financial_indicators.py",
    "backend/app/schemas/home_macro_release_context.py",
    "backend/app/schemas/executive_dashboard.py",
    "backend/app/schemas/home_bond_read_contracts.py",
    "backend/app/schemas/home_support_read_contracts.py",
    "backend/app/schemas/macro_vendor.py",
    "backend/app/schemas/research_calendar.py",
    "backend/app/schemas/common_numeric.py",
    "backend/app/schemas/result_meta.py",
)
_ANNOTATIONS = frozenset({"title", "description", "example", "examples", "default", "deprecated", "$comment"})
_SCHEMA_MAPS = frozenset({"properties", "patternProperties", "dependentSchemas", "$defs", "definitions"})
_SCHEMA_LISTS = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})
_SCHEMA_VALUES = frozenset(
    {"items", "additionalProperties", "unevaluatedProperties", "contains", "propertyNames", "not", "if", "then", "else"}
)


class ContractCheckError(ValueError):
    """A bounded technical failure, safe to include without a response body."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _local_origin(base_url: str) -> str:
    parsed = urlsplit(base_url)
    hostname = parsed.hostname or ""
    try:
        is_local = hostname == "localhost" or ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        is_local = False
    if (
        parsed.scheme not in {"http", "https"}
        or not is_local
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ContractCheckError("base_url must be a loopback HTTP origin without credentials, path, query, or fragment")
    # Access validates the port; it is never used to construct another hostname.
    _ = parsed.port
    return base_url.rstrip("/")


def _fetch_openapi(base_url: str, timeout: float) -> dict[str, Any]:
    request = Request(f"{base_url}/openapi.json", headers={"Accept": "application/json"}, method="GET")
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.geturl() != request.full_url:
                raise ContractCheckError("live OpenAPI redirected")
            content_type = response.headers.get_content_type()
            if content_type != "application/json" and not content_type.endswith("+json"):
                raise ContractCheckError("live OpenAPI response is not JSON")
            raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ContractCheckError("live OpenAPI exceeds the bounded response size")
    except HTTPError as error:
        label = "redirected" if 300 <= error.code < 400 else f"returned HTTP {error.code}"
        raise ContractCheckError(f"live OpenAPI {label}") from error
    except (URLError, TimeoutError, OSError) as error:
        raise ContractCheckError("live OpenAPI is unreachable or timed out") from error
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise ContractCheckError("live OpenAPI response is not valid JSON") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("paths"), dict):
        raise ContractCheckError("live OpenAPI must be an object with a paths object")
    return payload


def _schema_shape(schema: dict[str, Any], spec: dict[str, Any], references: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if key in _ANNOTATIONS:
            continue
        if key == "$ref":
            if not isinstance(value, str) or not value.startswith("#/"):
                raise ContractCheckError("response schema has a non-local or invalid reference")
            target = _resolve_ref(spec, value)
            if target is None:
                raise ContractCheckError(f"response schema reference is missing: {value}")
            if value not in references:
                references[value] = {}  # Reserve before descending through cyclic graphs.
                references[value] = _schema_shape(target, spec, references)
        elif key in _SCHEMA_MAPS and isinstance(value, dict):
            value = {
                field: _schema_shape(child, spec, references) if isinstance(child, dict) else child
                for field, child in value.items()
            }
        elif key in _SCHEMA_LISTS and isinstance(value, list):
            value = [_schema_shape(child, spec, references) if isinstance(child, dict) else child for child in value]
        elif key in _SCHEMA_VALUES and isinstance(value, dict):
            value = _schema_shape(value, spec, references)
        elif key in {"required", "enum", "type"} and isinstance(value, list):
            value = sorted(value, key=lambda item: json.dumps(item, sort_keys=True))
        result[key] = value
    return result


def extract_home_response_contract(spec: dict[str, Any]) -> dict[str, Any]:
    """Select only homepage GET success shapes and every referenced schema."""
    paths: dict[str, Any] = {}
    for path in HOME_GET_PATHS:
        path_item = spec.get("paths", {}).get(path)
        operation = path_item.get("get") if isinstance(path_item, dict) else None
        if not isinstance(operation, dict):
            raise ContractCheckError(f"GET route is missing: {path}")
        references: dict[str, Any] = {}
        responses: dict[str, Any] = {}
        raw_responses = operation.get("responses")
        if not isinstance(raw_responses, dict):
            raise ContractCheckError(f"GET route has no responses: {path}")
        for status, response in raw_responses.items():
            if not str(status).startswith("2"):
                continue
            if not isinstance(response, dict):
                raise ContractCheckError(f"GET route has invalid success response: {path}")
            if "$ref" in response:
                response_ref = response["$ref"]
                if not isinstance(response_ref, str) or not response_ref.startswith("#/"):
                    raise ContractCheckError(f"GET route has invalid success response reference: {path}")
                response = _resolve_ref(spec, response_ref)
            content = response.get("content") if isinstance(response, dict) else None
            media = content.get("application/json") if isinstance(content, dict) else None
            schema = media.get("schema") if isinstance(media, dict) else None
            if not isinstance(schema, dict):
                raise ContractCheckError(f"GET route has no JSON success response shape: {path}")
            responses[str(status)] = _schema_shape(schema, spec, references)
        if not responses:
            raise ContractCheckError(f"GET route has no JSON success response shape: {path}")
        paths[path] = {"responses": responses, "referenced_schemas": references}
    return {"paths": paths}


def _schema_node(schema: Any, spec: dict[str, Any], seen: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Resolve a coverage node without the field flattener's depth cutoff."""
    if not isinstance(schema, dict):
        return {}
    reference = schema.get("$ref")
    if isinstance(reference, str):
        if reference in seen:
            return {}
        return _schema_node(_resolve_ref(spec, reference), spec, seen | {reference})
    for combinator in ("anyOf", "oneOf"):
        choices = schema.get(combinator)
        if isinstance(choices, list):
            concrete = [choice for choice in choices if isinstance(choice, dict) and choice.get("type") != "null"]
            if len(concrete) == 1:
                return _schema_node(concrete[0], spec, seen)
    members = schema.get("allOf")
    if isinstance(members, list):
        properties = {
            name: child
            for member in members
            for name, child in (_schema_node(member, spec, seen).get("properties") or {}).items()
        }
        if properties:
            return {"type": "object", "properties": properties}
    return schema


def _field_schema(schema: dict[str, Any], field: str, spec: dict[str, Any]) -> dict[str, Any]:
    node = schema
    for part in field.split("."):
        properties = _schema_node(node, spec).get("properties")
        if not isinstance(properties, dict):
            return {}
        node = properties.get(part.removesuffix("[]"), {})
        if part.endswith("[]"):
            node = _schema_node(node, spec).get("items", {})
    return _schema_node(node, spec)


def _concrete_shape(schema: Any, spec: dict[str, Any]) -> bool:
    node = _schema_node(schema, spec)
    if isinstance(node.get("properties"), dict) and node["properties"]:
        return True
    primitive_types = {"string", "number", "integer", "boolean", "null"}
    schema_type = node.get("type")
    if isinstance(schema_type, list):
        return bool(schema_type) and all(isinstance(value, str) and value in primitive_types for value in schema_type)
    if isinstance(schema_type, str) and schema_type in primitive_types:
        return True
    if schema_type == "array":
        return _concrete_shape(node.get("items"), spec)
    if schema_type == "object" and isinstance(node.get("additionalProperties"), dict):
        return _concrete_shape(node["additionalProperties"], spec)
    for combinator in ("anyOf", "oneOf", "allOf"):
        choices = node.get(combinator)
        if isinstance(choices, list) and choices:
            return all(_concrete_shape(choice, spec) for choice in choices)
    return False


def _coverage_gaps(spec: dict[str, Any]) -> list[str]:
    """Reject opaque roots and undeclared fields in the scoped homepage reads."""
    gaps: list[str] = []
    for path in HOME_GET_PATHS:
        for status, response in spec["paths"][path]["get"]["responses"].items():
            if not str(status).startswith("2"):
                continue
            if "$ref" in response:
                response = _resolve_ref(spec, response["$ref"])
            schema = response["content"]["application/json"]["schema"]
            root = _schema_node(schema, spec)
            properties = root.get("properties")
            if not isinstance(properties, dict) or not properties:
                gaps.append(
                    f"GET {path} response {status} has no named root response fields"
                )
                continue
            if path not in HOME_CONSUMED_FIELDS:
                continue
            required_fields = (
                "result_meta.basis", "result_meta.quality_flag", "result_meta.formal_use_allowed",
                *HOME_CONSUMED_FIELDS[path],
            )
            missing = [field for field in required_fields if not _concrete_shape(_field_schema(schema, field, spec), spec)]
            if missing:
                gaps.append(f"GET {path} response {status} lacks concrete consumed fields: {', '.join(missing)}")
    return gaps


def _source_files(source_root: Path) -> list[dict[str, str]]:
    return [
        {"path": path, "sha256": hashlib.sha256((source_root / path).read_bytes()).hexdigest()}
        for path in CONTRACT_SOURCE_PATHS
    ]


def verify_home_runtime_contract(
    base_url: str = "http://127.0.0.1:7888",
    *,
    timeout: float = 15,
    expected_loader: Callable[[], dict[str, Any]] | None = None,
    source_root: Path = ROOT,
) -> dict[str, Any]:
    """Produce an evidence receipt without recording schemas or business payloads."""
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "receipt_kind": "dashboard_home_backend_contract",
        "scope": "dashboard-home-desktop",
        "status": "failed",
        "base_url": None,
        "started_at": datetime.now(UTC).isoformat(),
        "expected_contract_sha256": None,
        "observed_contract_sha256": None,
        "checked_paths": list(HOME_GET_PATHS),
        "failures": [],
        "coverage_gaps": [],
        "source_files": [],
        "source_stable": False,
        "limitations": [
            "Matching response schemas do not attest the running backend's full implementation or business data.",
            "Source hashes attest current expectation files only, not the files loaded by the running process.",
        ],
    }
    try:
        receipt["base_url"] = _local_origin(base_url)
        if timeout <= 0:
            raise ContractCheckError("timeout must be positive")
        receipt["source_files"] = _source_files(source_root)
        expected_spec = (expected_loader or (lambda: _load_openapi("current")))()
        expected = extract_home_response_contract(expected_spec)
        receipt["coverage_gaps"] = _coverage_gaps(expected_spec)
        receipt["expected_contract_sha256"] = _spec_sha256(expected).lower()
        receipt["source_stable"] = receipt["source_files"] == _source_files(source_root)
        if not receipt["source_stable"]:
            raise ContractCheckError("expected contract source files changed during export")
        if receipt["coverage_gaps"]:
            raise ContractCheckError("expected homepage response contract has opaque or missing consumed fields")
        observed_spec = _fetch_openapi(receipt["base_url"], timeout)
        observed = extract_home_response_contract(observed_spec)
        receipt["observed_contract_sha256"] = _spec_sha256(observed).lower()
        observed_gaps = _coverage_gaps(observed_spec)
        receipt["coverage_gaps"].extend(f"running {gap}" for gap in observed_gaps)
        if observed_gaps:
            receipt["failures"].append("running homepage response contract has opaque or missing consumed fields")
        for path in HOME_GET_PATHS:
            if expected["paths"][path] != observed["paths"][path]:
                receipt["failures"].append(f"running GET response contract differs: {path}")
        receipt["status"] = "failed" if receipt["failures"] else "passed"
    except (OSError, RuntimeError, ValueError, ImportError) as error:
        # Expected bounded technical messages never contain HTTP body or business data.
        message = str(error) if isinstance(error, ContractCheckError) else f"expected contract export failed: {type(error).__name__}"
        receipt["failures"].append(message)
    receipt["finished_at"] = datetime.now(UTC).isoformat()
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:7888")
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--output", help="Optional path for the technical JSON receipt.")
    args = parser.parse_args(argv)
    receipt = verify_home_runtime_contract(args.base_url, timeout=args.timeout)
    serialized = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
