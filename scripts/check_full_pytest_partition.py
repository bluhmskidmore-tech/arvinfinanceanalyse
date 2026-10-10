"""Verify complementary full-CI inventories against real JUnit executions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

NODE_PROPERTY = "full_pytest_nodeid"


def _read_inventory(directory: Path, platform: str) -> dict:
    payload = json.loads((directory / "full-pytest-inventory.json").read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("platform") != platform:
        raise ValueError(f"Invalid {platform} inventory identity")
    collection = payload.get("collection")
    selected = payload.get("selected")
    if not isinstance(collection, dict) or not collection or not isinstance(selected, list):
        raise ValueError(f"Missing {platform} full collection or selection")
    if any(not isinstance(node, str) or owner not in {"linux", "windows"}
           for node, owner in collection.items()):
        raise ValueError(f"Invalid {platform} collected test ownership")
    if any(not isinstance(node, str) for node in selected) or len(selected) != len(set(selected)):
        raise ValueError(f"Invalid or duplicate {platform} selected test nodes")
    expected = {node for node, owner in collection.items() if owner == platform}
    if set(selected) != expected or not expected:
        raise ValueError(f"{platform} selection is not its complete platform partition")
    return payload


def _read_execution(directory: Path, expected: set[str], platform: str) -> dict:
    report = ET.parse(directory / "full-pytest-report.xml")
    outcomes = {}
    rank = {"passed": 0, "skipped": 1, "failed": 2, "errors": 3}
    testcase_count = 0
    for case in report.iter("testcase"):
        testcase_count += 1
        node_properties = [prop.get("value") for prop in case.findall("properties/property")
                           if prop.get("name") == NODE_PROPERTY]
        if len(node_properties) != 1 or not node_properties[0]:
            raise ValueError(f"{platform} JUnit testcase lacks exactly one collected node identity")
        node = node_properties[0]
        status = ("errors" if case.find("error") is not None else
                  "failed" if case.find("failure") is not None else
                  "skipped" if case.find("skipped") is not None else "passed")
        previous = outcomes.get(node, "passed")
        outcomes[node] = max((previous, status), key=rank.__getitem__)
    actual = set(outcomes)
    if actual != expected:
        raise ValueError(f"{platform} execution mismatch: missing={len(expected - actual)}, "
                         f"unexpected={len(actual - expected)}")
    counts = {status: sum(value == status for value in outcomes.values()) for status in rank}
    if platform == "windows" and counts["skipped"]:
        raise ValueError("Windows native contracts were skipped instead of executed")
    return {"tests": len(outcomes), "junit_testcases": testcase_count, **counts}


def check_partition(linux_dir: Path, windows_dir: Path) -> dict:
    linux = _read_inventory(linux_dir, "linux")
    windows = _read_inventory(windows_dir, "windows")
    if not linux.get("commit") or linux["commit"] != windows.get("commit"):
        raise ValueError("Full CI partitions executed different or unidentified commits")
    linux_collection = linux["collection"]
    windows_collection = windows["collection"]
    # Portable parameter lists can legitimately depend on os.name (for example,
    # foreign Windows/Posix archive paths). Linux remains the full-suite ledger;
    # Windows must collect and execute exactly every native node in that ledger.
    native = {node for node, owner in linux_collection.items() if owner == "windows"}
    if native != {node for node, owner in windows_collection.items() if owner == "windows"}:
        raise ValueError("Linux and Windows did not collect the same Windows native test nodes")
    families = lambda collection: {node.split("[", 1)[0] for node in collection}
    if families(linux_collection) != families(windows_collection):
        raise ValueError("Linux and Windows did not collect the same complete test function inventory")
    shared = set(linux_collection) & set(windows_collection)
    if any(linux_collection[node] != windows_collection[node] for node in shared):
        raise ValueError("Linux and Windows disagree on collected test platform ownership")
    variants = {
        "linux_only_portable_nodes": sorted(set(linux_collection) - set(windows_collection)),
        "windows_only_unselected_portable_nodes": sorted(set(windows_collection) - set(linux_collection)),
    }
    selected = {"linux": set(linux["selected"]), "windows": set(windows["selected"])}
    complete = set(linux_collection)
    if selected["linux"] & selected["windows"] or set.union(*selected.values()) != complete:
        raise ValueError("Full CI platform partitions overlap or omit collected tests")
    execution = {"linux": _read_execution(linux_dir, selected["linux"], "linux"),
                 "windows": _read_execution(windows_dir, selected["windows"], "windows")}
    totals = {key: sum(result[key] for result in execution.values())
              for key in ("tests", "junit_testcases", "passed", "failed", "errors", "skipped")}
    return {
        "schema_version": 1,
        "commit": linux["commit"],
        "coverage_complete": True,
        "full_run_passed": not (totals["failed"] or totals["errors"]),
        "collected_tests": len(complete),
        "windows_collected_tests": len(windows_collection),
        "unselected_portable_parameter_variants": variants,
        "execution": execution,
        "totals": totals,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linux-dir", type=Path, required=True)
    parser.add_argument("--windows-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = check_partition(args.linux_dir, args.windows_dir)
    except (OSError, ValueError, ET.ParseError) as exc:
        result = {"coverage_complete": False, "full_run_passed": False, "error": str(exc)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["coverage_complete"] and result["full_run_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
