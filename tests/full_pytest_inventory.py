"""Observe full CI collection and selection; never skip or deselect tests."""

import json
import os
from pathlib import Path

import pytest

NODE_PROPERTY = "full_pytest_nodeid"


def pytest_addoption(parser):
    group = parser.getgroup("full-pytest-inventory")
    group.addoption("--full-pytest-platform", choices=("linux", "windows"))
    group.addoption("--full-pytest-inventory")


def pytest_configure(config):
    platform = config.getoption("--full-pytest-platform")
    if platform is None or not config.getoption("--full-pytest-inventory"):
        raise pytest.UsageError("Full inventory requires a platform and an output path")
    if (platform == "windows") != (os.name == "nt"):
        raise pytest.UsageError("Full inventory platform does not match the executing host")
    expected_marker = "windows_native" if platform == "windows" else "not windows_native"
    if config.option.markexpr != expected_marker:
        raise pytest.UsageError("Full CI must select exactly one complementary platform marker")
    root = config.rootpath
    targets = {(root / value).resolve() for value in config.args}
    if targets != {root / "tests", root / "backend" / "tests"}:
        raise pytest.UsageError("Full CI must collect both complete configured test directories")
    if config.option.keyword or config.option.ignore or config.option.deselect:
        raise pytest.UsageError("Full CI cannot narrow collection with -k, --ignore, or --deselect")
    invocation = config.invocation_params.args
    if any(arg == "--ignore-glob" or arg.startswith("--ignore-glob=") or arg in {"--lf", "--last-failed"}
           for arg in invocation):
        raise pytest.UsageError("Full CI cannot narrow collection with ignore globs or last-failed selection")


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    collection = {}
    for item in items:
        if item.nodeid in collection:
            raise pytest.UsageError(f"Duplicate collected test node: {item.nodeid}")
        collection[item.nodeid] = "windows" if item.get_closest_marker("windows_native") else "linux"
        item.user_properties.append((NODE_PROPERTY, item.nodeid))
    config._full_pytest_collection = collection


def pytest_collection_finish(session):
    config = session.config
    # xdist workers collect the same suite. One worker retains the full inventory;
    # JUnit from the controller records the actual outcomes across every worker.
    if getattr(config, "workerinput", {}).get("workerid", "gw0") != "gw0":
        return
    collection = getattr(config, "_full_pytest_collection", {})
    if not collection:
        return  # The xdist controller does not collect; collection errors remain failures.
    platform = config.getoption("--full-pytest-platform")
    selected = sorted(item.nodeid for item in session.items)
    expected = sorted(node for node, owner in collection.items() if owner == platform)
    if selected != expected:
        raise pytest.UsageError("Full CI platform selection omitted or added collected test nodes")
    output = Path(config.getoption("--full-pytest-inventory"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "schema_version": 1,
        "commit": os.environ.get("GITHUB_SHA", "local"),
        "platform": platform,
        "collection": collection,
        "selected": selected,
    }, indent=2) + "\n", encoding="utf-8")
