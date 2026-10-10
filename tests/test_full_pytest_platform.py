import json
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

from scripts.check_full_pytest_partition import check_partition
from tests import full_pytest_inventory, powershell_runtime


def _write_partition(directory: Path, platform: str, collection: dict[str, str], outcomes: dict[str, str]):
    directory.mkdir()
    inventory = {
        "schema_version": 1,
        "commit": "shared-head",
        "platform": platform,
        "collection": collection,
        "selected": [node for node, owner in collection.items() if owner == platform],
    }
    (directory / "full-pytest-inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    suite = ET.Element("testsuite")
    for node, status in outcomes.items():
        case = ET.SubElement(suite, "testcase", name=node)
        properties = ET.SubElement(case, "properties")
        ET.SubElement(properties, "property", name="full_pytest_nodeid", value=node)
        if status != "passed":
            ET.SubElement(case, status)
    ET.ElementTree(suite).write(directory / "full-pytest-report.xml", encoding="utf-8")


@pytest.fixture
def platform_reports(tmp_path):
    collection = {"tests/test_portable.py::test_run": "linux",
                  "tests/test_portable.py::test_old_skip": "linux",
                  "tests/test_native.py::test_cmd[9]": "windows"}
    linux = tmp_path / "linux"
    windows = tmp_path / "windows"
    _write_partition(linux, "linux", collection, {
        "tests/test_portable.py::test_run": "passed",
        "tests/test_portable.py::test_old_skip": "skipped",
    })
    _write_partition(windows, "windows", collection, {"tests/test_native.py::test_cmd[9]": "passed"})
    return linux, windows


def test_partition_accounts_for_real_outcomes_and_keeps_existing_skips_visible(platform_reports):
    result = check_partition(*platform_reports)
    assert result["coverage_complete"] is True
    assert result["full_run_passed"] is True
    assert result["collected_tests"] == 3
    assert result["totals"] == {"tests": 3, "junit_testcases": 3, "passed": 2,
                                "failed": 0, "errors": 0, "skipped": 1}
    assert result["execution"]["windows"]["skipped"] == 0


def test_partition_records_os_specific_portable_parameters_without_dropping_native_nodes(platform_reports):
    linux, windows = platform_reports
    inventory = windows / "full-pytest-inventory.json"
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    payload["collection"].pop("tests/test_portable.py::test_run")
    payload["collection"]["tests/test_portable.py::test_run[Windows-path]"] = "linux"
    inventory.write_text(json.dumps(payload), encoding="utf-8")
    result = check_partition(linux, windows)
    assert result["coverage_complete"] is True
    assert result["totals"]["tests"] == 3
    assert result["unselected_portable_parameter_variants"] == {
        "linux_only_portable_nodes": ["tests/test_portable.py::test_run"],
        "windows_only_unselected_portable_nodes": ["tests/test_portable.py::test_run[Windows-path]"],
    }


@pytest.mark.parametrize("mutation", ["missing_execution", "unexpected_execution", "native_skip", "missing_identity"])
def test_partition_rejects_missing_or_nonexecuted_windows_contracts(platform_reports, mutation):
    linux, windows = platform_reports
    report = windows / "full-pytest-report.xml"
    suite = ET.parse(report).getroot()
    case = suite.find("testcase")
    if mutation == "missing_execution":
        suite.remove(case)
    elif mutation == "unexpected_execution":
        case.find("properties/property").set("value", "tests/test_unselected.py::test_run")
    elif mutation == "native_skip":
        ET.SubElement(case, "skipped", message="No powershell")
    else:
        case.remove(case.find("properties"))
    ET.ElementTree(suite).write(report, encoding="utf-8")
    with pytest.raises(ValueError):
        check_partition(linux, windows)


@pytest.mark.parametrize("mutation", ["different_collection", "different_native_parameters", "missing_selection", "duplicate_selection", "different_commit"])
def test_partition_rejects_incomplete_or_inconsistent_collection(platform_reports, mutation):
    linux, windows = platform_reports
    inventory = windows / "full-pytest-inventory.json"
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    if mutation == "different_collection":
        payload["collection"]["tests/test_uncovered.py::test_run"] = "linux"
    elif mutation == "different_native_parameters":
        node = payload["selected"][0]
        payload["collection"].pop(node)
        changed = node.replace("[9]", "[0]")
        payload["collection"][changed] = "windows"
        payload["selected"] = [changed]
    elif mutation == "missing_selection":
        payload["selected"] = []
    elif mutation == "duplicate_selection":
        payload["selected"] *= 2
    else:
        payload["commit"] = "other-head"
    inventory.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        check_partition(linux, windows)


def test_partition_does_not_report_green_when_an_executed_contract_failed(platform_reports):
    linux, windows = platform_reports
    report = windows / "full-pytest-report.xml"
    suite = ET.parse(report).getroot()
    ET.SubElement(suite.find("testcase"), "failure", message="exit code was swallowed")
    ET.ElementTree(suite).write(report, encoding="utf-8")
    result = check_partition(linux, windows)
    assert result["coverage_complete"] is True
    assert result["full_run_passed"] is False
    assert result["totals"]["failed"] == 1


@pytest.mark.parametrize("platform, executable", [("nt", "powershell"), ("posix", "pwsh")])
def test_powershell_runtime_selects_the_executing_platform(monkeypatch, platform, executable):
    monkeypatch.setattr(powershell_runtime, "os", SimpleNamespace(name=platform))
    requested = []
    monkeypatch.setattr(powershell_runtime.shutil, "which", lambda name: requested.append(name) or name)
    assert powershell_runtime.powershell_executable() == executable
    assert requested == [executable]


def test_missing_powershell_runtime_fails_instead_of_skipping(monkeypatch):
    monkeypatch.setattr(powershell_runtime.shutil, "which", lambda _name: None)
    with pytest.raises(RuntimeError, match="required to execute"):
        powershell_runtime.powershell_executable()


@pytest.mark.parametrize("narrowing", ["target", "marker", "keyword", "ignore", "deselect", "ignore_glob", "last_failed"])
def test_full_inventory_rejects_accidentally_narrowed_ci_collection(tmp_path, monkeypatch, narrowing):
    monkeypatch.setattr(full_pytest_inventory, "os", SimpleNamespace(name="posix"))
    options = SimpleNamespace(markexpr="not windows_native", keyword="", ignore=[], deselect=[])
    config = SimpleNamespace(rootpath=tmp_path, args=["tests", "backend/tests"], option=options,
                             invocation_params=SimpleNamespace(args=()),
                             getoption=lambda name: "linux" if name == "--full-pytest-platform" else "inventory.json")
    if narrowing == "target":
        config.args = ["tests/test_native.py"]
    elif narrowing == "marker":
        options.markexpr = "not windows_native and not excluded_surface_acceptance"
    elif narrowing in {"ignore_glob", "last_failed"}:
        config.invocation_params.args = ("--ignore-glob=test_native*",) if narrowing == "ignore_glob" else ("--lf",)
    else:
        setattr(options, narrowing, ["hidden"] if narrowing != "keyword" else "hidden")
    with pytest.raises(pytest.UsageError):
        full_pytest_inventory.pytest_configure(config)
