"""Read-only handoff checks for source, recorded tests, a build, and port 5888.

The test and build receipts are supplied evidence, not execution performed here.
This command never starts a service, selects a build, or declares business acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev_runtime_control import (  # noqa: E402
    RuntimeControlError,
    contained_path,
    control_dir,
    frontend_plan,
    verify_build,
)
from scripts.verify_home_runtime_contract import HOME_GET_PATHS  # noqa: E402

HEX_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
SELECTION_FIELDS = ("mode", "data_source", "build_root", "manifest_path", "manifest_sha256")
EXCLUDED_ROOT_PARTS = {"data", "data_input", "node_modules", ".venv", "dist", "build",
                       ".git", ".codex-tmp", "__pycache__", ".pytest_cache"}
EXCLUDED_FILE_PARTS = {"data", "data_input", "node_modules", ".venv", "dist", "build", ".git"}
HOME_SECTIONS = {"holdings", "risk", "market", "support", "evidence"}
HOME_REQUIRED_PATHS = set(HOME_GET_PATHS) - {"/ui/balance-analysis/decision-items"}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> tuple[object, str]:
    data = path.read_bytes()
    return json.loads(data), _digest(data)


def _relative_name(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("invalid relative source path")
    name = PurePosixPath(value)
    if name.is_absolute() or ".." in name.parts or str(name) != value or value == ".":
        raise ValueError("invalid relative source path")
    return value


def _source_snapshot(root: Path, manifest_path: Path) -> tuple[str, str, str, str, list[str]]:
    manifest, manifest_digest = _read_json(manifest_path)
    if isinstance(manifest, list):
        rows, roots, coverage = manifest, [], "listed_files_only"
    elif isinstance(manifest, dict):
        rows, roots, coverage = manifest.get("files"), manifest.get("roots"), "root_closed"
    else:
        raise ValueError("source manifest must be a list or files/roots object")
    if not isinstance(rows, list) or not rows:
        raise ValueError("source manifest must be a nonempty file list")
    if not isinstance(roots, list) or (coverage == "root_closed" and not roots):
        raise ValueError("closed source manifest requires roots")
    seen: set[str] = set()
    observed: dict[str, str] = {}
    issues: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise ValueError("invalid source manifest row")
        name, expected = _relative_name(row["path"]), row.get("sha256")
        if (name in seen or not isinstance(expected, str)
                or not HEX_DIGEST.fullmatch(expected)):
            raise ValueError("duplicate source path or invalid digest")
        if set(name.split("/")) & EXCLUDED_FILE_PARTS:
            raise ValueError("source file includes data, dependency, or build directory")
        seen.add(name)
        path = contained_path(root, name)
        actual = _digest(path.read_bytes()) if path.is_file() else "missing"
        observed[name] = actual
        if actual != expected:
            issues.append(f"{name}: {'missing' if actual == 'missing' else 'changed'}")
    root_names = [_relative_name(value) for value in roots]
    if len(set(root_names)) != len(root_names):
        raise ValueError("duplicate source root")
    for name in root_names:
        if set(name.split("/")) & EXCLUDED_ROOT_PARTS:
            raise ValueError("source root includes generated, dependency, or data files")
        directory = contained_path(root, name)
        if not directory.is_dir():
            raise ValueError(f"source root missing: {name}")
        def _walk_error(exc: OSError) -> None:
            raise exc

        for current, dirs, files in os.walk(directory, followlinks=False, onerror=_walk_error):
            for child in dirs + files:
                contained_path(root, str(Path(current) / child))
            if set(dirs) & EXCLUDED_ROOT_PARTS:
                raise ValueError("source root contains generated, dependency, or data directory")
            for child in files:
                relative = (Path(current) / child).relative_to(root).as_posix()
                if relative not in seen:
                    observed[relative] = _digest((Path(current) / child).read_bytes())
                    issues.append(f"{relative}: unlisted")
    observed_digest = _digest(json.dumps(observed, sort_keys=True, separators=(",", ":")).encode())
    return (manifest_digest,
            _digest(json.dumps(sorted(seen), separators=(",", ":")).encode()),
            coverage, observed_digest, issues)


def _selection_snapshot(root: Path, selection_path: Path) -> tuple[dict, str]:
    selection, digest = _read_json(selection_path)
    if not isinstance(selection, dict) or any(key not in selection for key in SELECTION_FIELDS):
        raise ValueError("invalid candidate selection")
    verify_build(root, selection)
    return selection, digest


def _registered_snapshot(root: Path) -> tuple[dict | None, str | None]:
    path = control_dir(root) / "frontend.json"
    if not path.is_file():
        return None, None
    value, digest = _read_json(path)
    if not isinstance(value, dict):
        raise ValueError("invalid runtime frontend selection")
    return value, digest


def _local_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or not parsed.port or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment or parsed.username or parsed.password):
        raise ValueError("base URL must be a local HTTP origin")
    return base_url.rstrip("/") + "/"


def _http_snapshot(root: Path, selection: dict, base_url: str) -> list[dict[str, str]]:
    plan = frontend_plan(root, "node", verify_files=False, selection=selection)
    observed = []
    for probe in plan["probes"]:
        requested_url = base_url + probe["path"]
        with urlopen(requested_url, timeout=3) as response:
            content = response.read()
            digest = _digest(content)
            if (response.status != 200 or response.geturl() != requested_url
                    or digest != probe["sha256"]):
                raise RuntimeControlError(
                    f"HTTP response does not match candidate: {probe['path']} "
                    f"(status={response.status}, final_url={response.geturl()}, observed_sha256={digest})"
                )
            observed.append({"path": probe["path"], "sha256": digest})
    return observed


def _home_check_receipt(path: Path | None, kind: str) -> tuple[dict, str]:
    if path is None:
        raise ValueError(f"{kind} receipt absent")
    value, digest = _read_json(path)
    if (not isinstance(value, dict) or value.get("receipt_kind") != kind
            or type(value.get("schema_version")) is not int or value["schema_version"] != 1
            or value.get("scope") != "dashboard-home-desktop"):
        raise ValueError(f"invalid {kind} receipt")
    if value.get("status") != "passed" or value.get("failures") != []:
        raise ValueError(f"{kind} check failed: {value.get('failures', [])}")
    try:
        started = datetime.fromisoformat(value["started_at"].replace("Z", "+00:00"))
        finished = datetime.fromisoformat(value["finished_at"].replace("Z", "+00:00"))
        now = datetime.now(UTC)
        if (started.tzinfo is None or finished.tzinfo is None or finished < started
                or started > now + timedelta(seconds=5)
                or finished > now + timedelta(seconds=5)
                or now - started > timedelta(minutes=15)):
            raise ValueError("stale or invalid check interval")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("check interval absent or invalid") from exc
    return value, digest


def _home_runtime_layer(path: Path | None, url: str, probes: list[dict]) -> tuple[dict, str]:
    value, digest = _home_check_receipt(path, "dashboard_home_runtime")
    if _local_url(value.get("base_url", "")) != url:
        raise ValueError("homepage check used a different URL")
    if value.get("frontend_probes") != probes or not probes:
        raise ValueError("homepage check does not match the observed frontend build")
    full_page = value.get("home", {}).get("fullPage")
    if not isinstance(full_page, dict):
        raise ValueError("homepage full-page results absent")
    sections = full_page.get("sections")
    if (not isinstance(sections, list) or len(sections) != len(HOME_SECTIONS)
            or any(not isinstance(row, dict) or row.get("seen") is not True for row in sections)
            or {row.get("id") for row in sections} != HOME_SECTIONS):
        raise ValueError("homepage section coverage incomplete")
    requests = full_page.get("requests")
    if not isinstance(requests, list) or not requests:
        raise ValueError("homepage completed requests absent")
    for request in requests:
        if (not isinstance(request, dict) or type(request.get("status")) is not int
                or not 200 <= request["status"] < 300 or request.get("finished") is not True
                or request.get("failed")):
            raise ValueError("homepage contains failed or unfinished requests")
    if not HOME_REQUIRED_PATHS <= {row.get("path") for row in requests}:
        raise ValueError("homepage mandatory data requests absent")
    if type(full_page.get("required_decision_items")) is not bool:
        raise ValueError("homepage conditional request coverage absent")
    if (full_page.get("required_decision_items") is True
            and not any(row.get("path") == "/ui/balance-analysis/decision-items" for row in requests)):
        raise ValueError("homepage required decision-items request absent")
    if full_page.get("failures") != []:
        raise ValueError("homepage terminal-state check failed or absent")
    states = full_page.get("states")
    if (full_page.get("research_tab") is not True or not isinstance(states, dict)
            or any(type(states.get(key)) is not int or states[key] != 0 for key in ("loading", "errors"))):
        raise ValueError("homepage tab coverage or terminal states incomplete")
    return {"status": "passed", "url": url, "evidence": "reported_live_page_results",
            "section_count": len(sections), "request_count": len(requests)}, digest


def _home_backend_layer(root: Path, path: Path | None, base_url: str) -> tuple[dict, str]:
    value, digest = _home_check_receipt(path, "dashboard_home_backend_contract")
    if _local_url(value.get("base_url", "")) != _local_url(base_url):
        raise ValueError("backend contract check used a different URL")
    expected, observed = value.get("expected_contract_sha256"), value.get("observed_contract_sha256")
    if not isinstance(expected, str) or not HEX_DIGEST.fullmatch(expected) or expected != observed:
        raise ValueError("runtime backend response contract differs from expected contract")
    paths = value.get("checked_paths")
    if not isinstance(paths, list) or not set(HOME_GET_PATHS) <= set(paths):
        raise ValueError("backend homepage contract coverage incomplete")
    coverage_gaps = value.get("coverage_gaps")
    if coverage_gaps != []:
        raise ValueError("backend homepage response field coverage incomplete or absent")
    source_files = value.get("source_files")
    if value.get("source_stable") is not True or not isinstance(source_files, list) or not source_files:
        raise ValueError("expected backend contract source binding absent")
    seen = set()
    for row in source_files:
        if not isinstance(row, dict):
            raise ValueError("invalid backend contract source row")
        name = _relative_name(row.get("path"))
        if (name in seen or not (name.startswith("backend/app/") or name in {
                "scripts/api_contract_check.py", "scripts/api_surface.py"})
                or set(name.split("/")) & EXCLUDED_FILE_PARTS):
            raise ValueError("invalid backend contract source path")
        seen.add(name)
        if _digest(contained_path(root, name).read_bytes()) != row.get("sha256"):
            raise ValueError(f"backend contract source changed after check: {name}")
    return {"status": "passed", "url": _local_url(base_url),
            "contract_sha256": expected, "checked_paths": paths,
            "coverage_gaps": coverage_gaps,
            "coverage": "response_contract_only"}, digest


def build_handoff_receipt(
    *, root: Path, source_manifest: Path, test_receipt: Path | None = None,
    build_receipt: Path | None = None,
    selection_path: Path, base_url: str = "http://127.0.0.1:5888/",
    source_root: Path | None = None, page: str | None = None,
    runtime_receipt: Path | None = None, backend_contract_receipt: Path | None = None,
) -> dict:
    """Return independently named layer checks without changing runtime state."""
    root = root.resolve()
    source_root = root if source_root is None else source_root.resolve()
    layers: dict[str, dict] = {}
    identities: dict[str, object] = {}
    try:
        source_snapshot = _source_snapshot(source_root, source_manifest)
        source_digest, path_set_digest, coverage, observed_digest, issues = source_snapshot
        layers["source"] = {"status": "failed" if issues else "passed",
                            "directory": str(source_root),
                            "expected_manifest_sha256": source_digest,
                            "observed_files_sha256": observed_digest, "coverage": coverage,
                            "mismatch_count": len(issues), "mismatches": issues[:20]}
        identities["source_manifest_sha256"] = source_digest
        identities["source_path_set_sha256"] = path_set_digest
        identities["observed_source_files_sha256"] = observed_digest
    except (OSError, ValueError, TypeError, RuntimeControlError) as exc:
        layers["source"] = {"status": "failed", "reason": str(exc)}
        source_digest = None

    try:
        if test_receipt is None:
            raise FileNotFoundError("test receipt absent")
        test, test_digest = _read_json(test_receipt)
        identities["test_receipt_sha256"] = test_digest
        reported = ({key: test.get(key) for key in ("command", "exit_code", "results")}
                    if isinstance(test, dict) else {})
        if not isinstance(test, dict) or not test.get("source_manifest_sha256"):
            layers["tests"] = {"status": "unknown", "reason": "source-to-test binding absent", **reported}
        elif source_digest is None:
            layers["tests"] = {"status": "unknown", "reason": "source snapshot unavailable", **reported}
        elif test["source_manifest_sha256"] != source_digest:
            layers["tests"] = {"status": "failed", "reason": "source-to-test binding mismatch", **reported}
        elif (not isinstance(test.get("command"), list) or not test["command"]
              or any(not isinstance(value, str) or not value for value in test["command"])
              or not isinstance(test.get("results"), list) or not test["results"]
              or any(not isinstance(item, dict) or not isinstance(item.get("name"), str)
                     or not item["name"] for item in test["results"])
              or len({item["name"] for item in test["results"]}) != len(test["results"])
              or type(test.get("exit_code")) is not int):
            layers["tests"] = {"status": "unknown", "reason": "test execution details absent", **reported}
        elif test["exit_code"] != 0 or any(
            not isinstance(item, dict) or item.get("status") != "passed"
            for item in test["results"]
        ):
            layers["tests"] = {"status": "failed", "reason": "recorded test execution failed or incomplete",
                               **reported}
        else:
            layers["tests"] = {"status": "passed", "evidence": "reported_test_results",
                               **reported}
    except (OSError, ValueError, TypeError) as exc:
        layers["tests"] = {"status": "unknown", "reason": str(exc)}

    try:
        selection, selection_digest = _selection_snapshot(root, selection_path)
        identities["candidate_selection_sha256"] = selection_digest
        identities["candidate_manifest_sha256"] = selection["manifest_sha256"]
        layers["candidate"] = {"status": "passed", "manifest_sha256": selection["manifest_sha256"]}
    except (OSError, ValueError, KeyError, TypeError, RuntimeControlError) as exc:
        layers["candidate"] = {"status": "failed", "reason": str(exc)}
        selection = None

    try:
        if build_receipt is None:
            raise FileNotFoundError("build receipt absent")
        build, build_digest = _read_json(build_receipt)
        identities["build_receipt_sha256"] = build_digest
        if (not isinstance(build, dict) or not build.get("source_manifest_sha256")
                or not build.get("build_manifest_sha256")):
            layers["build_binding"] = {"status": "unknown", "reason": "source-to-build binding absent"}
        elif source_digest is None or selection is None:
            layers["build_binding"] = {"status": "unknown", "reason": "source or candidate unavailable"}
        elif (build["source_manifest_sha256"] != source_digest
              or build["build_manifest_sha256"] != selection["manifest_sha256"]):
            layers["build_binding"] = {"status": "failed", "reason": "source-to-build binding mismatch"}
        else:
            layers["build_binding"] = {"status": "passed", "evidence": "recorded binding"}
    except (OSError, ValueError, TypeError) as exc:
        layers["build_binding"] = {"status": "unknown", "reason": str(exc)}

    try:
        registered, registered_digest = _registered_snapshot(root)
        identities["registered_selection_sha256"] = registered_digest
        if registered is None:
            layers["registration"] = {"status": "failed", "reason": "no frontend build registered"}
        elif selection is None:
            layers["registration"] = {"status": "unknown", "reason": "candidate unavailable"}
        elif any(registered.get(key) != selection.get(key) for key in SELECTION_FIELDS):
            layers["registration"] = {"status": "failed", "reason": "candidate differs from registered build"}
        else:
            layers["registration"] = {"status": "passed"}
    except (OSError, ValueError, TypeError, RuntimeControlError) as exc:
        layers["registration"] = {"status": "failed", "reason": str(exc)}
        registered_digest = None

    url = base_url
    try:
        url = _local_url(base_url)
        identities["http_url"] = url
        if selection is None:
            layers["http"] = {"status": "unknown", "reason": "candidate unavailable"}
        else:
            observed = _http_snapshot(root, selection, url)
            layers["http"] = {"status": "passed", "url": url,
                              "matches_candidate": True, "probes": observed}
            identities["http_probes"] = observed
    except (OSError, ValueError, RuntimeControlError) as exc:
        layers["http"] = {"status": "failed", "url": url,
                          "matches_candidate": False, "reason": str(exc)}
        identities["http_url"] = url
        identities["http_observation"] = str(exc)

    if page == "dashboard-home":
        try:
            layer, digest = _home_runtime_layer(runtime_receipt, url, layers["http"].get("probes", []))
            layers["home_runtime"] = layer
            identities["home_runtime_receipt_sha256"] = digest
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            layers["home_runtime"] = {"status": "failed", "reason": str(exc)}
        try:
            layer, digest = _home_backend_layer(root, backend_contract_receipt, url)
            layers["backend_contract"] = layer
            identities["backend_contract_receipt_sha256"] = digest
        except (OSError, ValueError, TypeError, KeyError) as exc:
            layers["backend_contract"] = {"status": "failed", "reason": str(exc)}
    elif page is not None:
        layers["page"] = {"status": "failed", "reason": "unsupported page acceptance scope"}

    # Recheck mutable inputs after HTTP I/O. This is a consistency check, not an atomic snapshot.
    try:
        if source_digest is not None and _source_snapshot(source_root, source_manifest) != source_snapshot:
            layers["source"] = {"status": "failed", "reason": "source changed during handoff check"}
    except (OSError, ValueError, KeyError, TypeError, RuntimeControlError) as exc:
        layers["source"] = {"status": "failed", "reason": f"source changed during handoff check: {exc}"}
    try:
        if selection is not None and _selection_snapshot(root, selection_path)[1] != selection_digest:
            layers["candidate"] = {"status": "failed", "reason": "candidate changed during handoff check"}
    except (OSError, ValueError, KeyError, TypeError, RuntimeControlError) as exc:
        layers["candidate"] = {"status": "failed", "reason": f"candidate changed during handoff check: {exc}"}
    try:
        if _registered_snapshot(root)[1] != registered_digest:
            layers["registration"] = {"status": "failed", "reason": "registration changed during handoff check"}
    except (OSError, ValueError, KeyError, TypeError, RuntimeControlError) as exc:
        layers["registration"] = {"status": "failed", "reason": f"registration changed during handoff check: {exc}"}

    for path, key, layer in ((test_receipt, "test_receipt_sha256", "tests"),
                             (build_receipt, "build_receipt_sha256", "build_binding"),
                             (runtime_receipt, "home_runtime_receipt_sha256", "home_runtime"),
                             (backend_contract_receipt, "backend_contract_receipt_sha256", "backend_contract")):
        if path is not None and key in identities:
            try:
                if _digest(path.read_bytes()) != identities[key]:
                    layers[layer] = {"status": "failed", "reason": "receipt changed during handoff check"}
            except OSError as exc:
                layers[layer] = {"status": "failed", "reason": str(exc)}

    states = {value["status"] for value in layers.values()}
    status = "failed" if "failed" in states else "unknown" if "unknown" in states else "passed"
    identity = _digest(json.dumps(identities, sort_keys=True, separators=(",", ":")).encode())
    return {"status": status, "identity_sha256": identity, "layers": layers,
            "business_acceptance": "not assessed",
            "evidence_authority": "supplied_records_not_independently_attested",
            "scope": "dashboard-home-desktop" if page == "dashboard-home" else "declared_inputs_only",
            "snapshot": "non-atomic, checked before and after HTTP"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--test-receipt", type=Path)
    parser.add_argument("--build-receipt", type=Path)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:5888/")
    parser.add_argument("--source-root", type=Path, help="Immutable source directory associated with the selected build")
    parser.add_argument("--page", choices=["dashboard-home"], help="Execute mandatory real full-page and backend-contract checks")
    parser.add_argument("--output", type=Path, help="Write the handoff and fresh page check receipts beside this file")
    args = parser.parse_args(argv)
    runtime_receipt = backend_contract_receipt = None
    checks = []
    if args.page == "dashboard-home":
        if args.output is None:
            parser.error("--page dashboard-home requires --output to retain the check receipts")
        _local_url(args.base_url)
        backend_url = _local_url(args.base_url)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        runtime_receipt = args.output.with_name(args.output.stem + ".home-runtime.json")
        backend_contract_receipt = args.output.with_name(args.output.stem + ".backend-contract.json")
        env = dict(os.environ, PYTHONUTF8="1", MOSS_HOME_STARTUP_BASE_URL=_local_url(args.base_url),
                   MOSS_HOME_STARTUP_READY_URL=backend_url + "health/ready")
        commands = [
            ([sys.executable, str(ROOT / "scripts/verify_home_runtime_contract.py"),
              "--base-url", backend_url, "--output", str(backend_contract_receipt)], backend_contract_receipt),
            (["node", str(ROOT / "frontend/scripts/sampleHomeStartupLive.mjs"),
              "--output", str(runtime_receipt)], runtime_receipt),
        ]
        for command, receipt_path in commands:
            check_started = datetime.now(UTC)
            error_kind = None
            stderr = b""
            try:
                completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                           timeout=150, check=False)
                code = completed.returncode
                stderr = completed.stderr
            except (OSError, subprocess.TimeoutExpired) as exc:
                code = -1
                error_kind = type(exc).__name__
                if isinstance(exc, subprocess.TimeoutExpired):
                    stderr = exc.stderr or b""
            stderr_path = receipt_path.with_suffix(".stderr.log")
            stderr_path.write_bytes(stderr or b"")
            if code != 0:
                # A failed invocation cannot reuse a prior passing receipt at the same path.
                failure = {"status": "failed", "failures": [f"check execution failed: {error_kind or 'nonzero_exit'}"],
                           "execution_exit_code": code, "stderr_path": str(stderr_path)}
                if receipt_path.is_file() and receipt_path.stat().st_mtime >= check_started.timestamp():
                    try:
                        reported, _ = _read_json(receipt_path)
                        if isinstance(reported, dict) and reported.get("status") == "failed":
                            failure = reported
                    except (OSError, ValueError):
                        pass
                receipt_path.write_text(json.dumps(failure, ensure_ascii=False), encoding="utf-8")
            else:
                try:
                    reported, _ = _read_json(receipt_path)
                    interval_start = datetime.fromisoformat(reported["started_at"].replace("Z", "+00:00"))
                    if interval_start.tzinfo is None or interval_start < check_started:
                        raise ValueError("receipt predates check invocation")
                except (OSError, ValueError, KeyError, TypeError, AttributeError):
                    code = -1
                    receipt_path.write_text(json.dumps({"status": "failed", "failures": ["fresh check receipt absent"]}), encoding="utf-8")
            checks.append({"command": command, "exit_code": code, "error_kind": error_kind,
                           "stderr_path": str(stderr_path)})
    result = build_handoff_receipt(
        root=args.repo_root, source_manifest=args.source_manifest,
        test_receipt=args.test_receipt, build_receipt=args.build_receipt,
        selection_path=args.selection, base_url=args.base_url,
        source_root=args.source_root, page=args.page,
        runtime_receipt=runtime_receipt, backend_contract_receipt=backend_contract_receipt,
    )
    if checks:
        result["executed_checks"] = checks
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
