"""Measure how much of the API response surface the OpenAPI contract gate can actually see.

`api_contract_check.py` only catches a renamed or retyped response field if the
field is *in* the schema. An operation declaring `response_model=dict` renders as
`{"additionalProperties": true, "type": "object"}`: it has content, it has a
schema, and it pins exactly zero business fields. This script separates those
opaque operations from the ones carrying a real field-level contract, so the
"how protected are we" number stops being a guess.

Usage:

    python scripts/api_contract_coverage.py --surface full
    python scripts/api_contract_coverage.py --surface full --format json
    python scripts/api_contract_coverage.py --spec contracts/openapi/openapi.full.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api_contract_check import _load_openapi, extract_contract  # noqa: E402
from scripts.api_surface import SURFACE_CHOICES, SURFACE_HELP  # noqa: E402

# Types the flattener emits for a node that groups other nodes rather than
# carrying a value. They are real contract entries, but counting them as
# "protected business fields" would inflate the number.
CONTAINER_TYPES = frozenset({"object", "array", "object-map"})

STRUCTURED = "structured"
# `response_model=dict` -> {"additionalProperties": true, "type": "object"}.
OPAQUE_OBJECT = "opaque_object"
# No `response_model` at all -> an empty `{}` schema.
OPAQUE_UNKNOWN = "opaque_unknown"
# A union the flattener will not descend into, e.g. anyOf[EnvelopeA, EnvelopeB].
OPAQUE_UNION = "opaque_union"
NO_SCHEMA = "no_schema"
NO_SUCCESS_RESPONSE = "no_success_response"

UNCOVERED_KINDS = (OPAQUE_OBJECT, OPAQUE_UNKNOWN, OPAQUE_UNION, NO_SCHEMA, NO_SUCCESS_RESPONSE)


def _primary_success(responses: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Lowest-numbered 2xx response; that is the one clients actually read."""
    for status in sorted(responses):
        if status != "204":
            return status, responses[status]
    return next(iter(sorted(responses.items())), None)


def classify_operation(contract: dict[str, Any]) -> dict[str, Any]:
    """Bucket one operation contract by how much of its response body is pinned.

    The dividing line is whether the flattened schema names any field at all. A
    schema that only yields the anonymous root entry `"."` tells the diff engine
    "some object comes back" and nothing more, so a renamed business field inside
    it is invisible to the gate.
    """
    primary = _primary_success(contract.get("responses") or {})
    if primary is None:
        return {"status": None, "kind": NO_SUCCESS_RESPONSE, "leaf_fields": 0, "field_paths": 0}

    status, response = primary
    if not response.get("has_schema"):
        return {"status": status, "kind": NO_SCHEMA, "leaf_fields": 0, "field_paths": 0}

    fields: dict[str, Any] = response.get("fields") or {}
    named = {path: facts for path, facts in fields.items() if path != "."}
    if named:
        leaf_fields = sum(1 for facts in named.values() if facts.get("type") not in CONTAINER_TYPES)
        return {"status": status, "kind": STRUCTURED, "leaf_fields": leaf_fields, "field_paths": len(named)}

    root_type = str((fields.get(".") or {}).get("type") or "")
    if root_type == "unknown":
        kind = OPAQUE_UNKNOWN
    elif root_type.startswith(("anyOf[", "oneOf[")):
        kind = OPAQUE_UNION
    else:
        kind = OPAQUE_OBJECT
    return {"status": status, "kind": kind, "leaf_fields": 0, "field_paths": 0}


def measure(spec: dict[str, Any]) -> dict[str, Any]:
    contract = extract_contract(spec)
    operations: list[dict[str, Any]] = []
    for operation, operation_contract in sorted(contract.items()):
        classification = classify_operation(operation_contract)
        operations.append(
            {
                "operation": operation,
                "operation_id": operation_contract.get("operation_id", ""),
                "response_status": classification["status"],
                "kind": classification["kind"],
                "leaf_fields": classification["leaf_fields"],
                "field_paths": classification["field_paths"],
            }
        )

    counts = {kind: 0 for kind in (STRUCTURED, *UNCOVERED_KINDS)}
    for row in operations:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1

    total = len(operations)
    return {
        "schema_version": 1,
        "summary": {
            "operation_count": total,
            "structured_operations": counts[STRUCTURED],
            "opaque_object_operations": counts[OPAQUE_OBJECT],
            "opaque_unknown_operations": counts[OPAQUE_UNKNOWN],
            "opaque_union_operations": counts[OPAQUE_UNION],
            "no_schema_operations": counts[NO_SCHEMA],
            "no_success_response_operations": counts[NO_SUCCESS_RESPONSE],
            "uncovered_operations": sum(counts[kind] for kind in UNCOVERED_KINDS),
            "managed_leaf_fields": sum(row["leaf_fields"] for row in operations),
            "managed_field_paths": sum(row["field_paths"] for row in operations),
            "structured_operation_pct": round(100.0 * counts[STRUCTURED] / total, 2) if total else 0.0,
        },
        "operations": operations,
    }


def _render_text(report: dict[str, Any], label: str, *, list_gaps: int) -> str:
    summary = report["summary"]
    lines = [
        f"API response contract coverage ({label})",
        "=" * 48,
        f"  operations                   : {summary['operation_count']}",
        f"  with field-level structure   : {summary['structured_operations']} "
        f"({summary['structured_operation_pct']}%)",
        f"  opaque: response_model=dict  : {summary['opaque_object_operations']}",
        f"  opaque: no response_model    : {summary['opaque_unknown_operations']}",
        f"  opaque: undescended union    : {summary['opaque_union_operations']}",
        f"  no response schema           : {summary['no_schema_operations']}",
        f"  no 2xx response at all       : {summary['no_success_response_operations']}",
        f"  managed leaf fields          : {summary['managed_leaf_fields']}",
        f"  managed field paths (+nodes) : {summary['managed_field_paths']}",
    ]
    if list_gaps:
        gaps = [row for row in report["operations"] if row["kind"] in UNCOVERED_KINDS]
        lines.append("")
        lines.append(f"Uncovered operations (first {min(list_gaps, len(gaps))} of {len(gaps)}):")
        lines.extend(f"  [{row['kind']}] {row['operation']}" for row in gaps[:list_gaps])
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--surface", choices=SURFACE_CHOICES, default="full", help=SURFACE_HELP)
    source.add_argument("--spec", default=None, help="Measure a saved OpenAPI JSON file instead of live code.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", default="-", help="Output path, or '-' for stdout.")
    parser.add_argument(
        "--list-gaps",
        type=int,
        default=0,
        metavar="N",
        help="Also print the first N uncovered operations (text format only).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.spec:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        label = args.spec
    else:
        spec = _load_openapi(args.surface)
        label = f"surface={args.surface}"

    report = measure(spec)
    report["source"] = label
    text = (
        json.dumps(report, ensure_ascii=False, indent=2)
        if args.format == "json"
        else _render_text(report, label, list_gaps=args.list_gaps)
    )
    if args.output == "-":
        print(text)
    else:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
