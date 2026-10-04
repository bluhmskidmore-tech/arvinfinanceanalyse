"""Coordinate local runtime starts, maintenance, and an explicitly accepted UI build.

Maintenance blocks cooperating launchers; it does not attest that old processes
or database writers have drained. No database connection is made by this tool.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.request import urlopen
from urllib.parse import urlsplit


class RuntimeControlError(RuntimeError):
    pass


def control_dir(root: Path) -> Path:
    return contained_path(root, "tmp-governance/runtime-clean/control")


@contextmanager
def operation_lock(root: Path, timeout: float = 30):
    directory = control_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    stream = None
    while stream is None:
        candidate = None
        try:
            candidate = (directory / "operation.lock").open("a+b")
            if sys.platform == "win32":
                import msvcrt

                candidate.seek(0)
                msvcrt.locking(candidate.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
            stream = candidate
        except OSError as exc:
            if candidate is not None:
                candidate.close()
            if time.monotonic() >= deadline:
                raise RuntimeControlError("runtime operation lock unavailable") from exc
            time.sleep(0.05)
    try:
        yield
    finally:
        stream.close()


def read_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeControlError(f"invalid runtime state: {path.name}")
    return value


def write_object(path: Path, value: dict) -> None:
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def assert_start_allowed(root: Path) -> None:
    if (control_dir(root) / "maintenance.json").exists():
        raise RuntimeControlError("maintenance blocks runtime changes; existing processes are not certified drained")


def require_owner(root: Path, token: str | None) -> dict:
    state = read_object(control_dir(root) / "maintenance.json")
    if not token or state.get("owner_token") != token or state.get("state") != "launch_blocked":
        raise RuntimeControlError("maintenance owner token does not match")
    return state


def enter_maintenance(root: Path, reason: str) -> dict:
    if not reason.strip():
        raise RuntimeControlError("a maintenance reason is required")
    with operation_lock(root):
        assert_start_allowed(root)
        state = {"state": "launch_blocked", "drained": False, "reason": reason,
                 "owner_token": uuid.uuid4().hex, "entered_at": time.time()}
        write_object(control_dir(root) / "maintenance.json", state)
        return state


def leave_maintenance(root: Path, token: str) -> None:
    with operation_lock(root):
        require_owner(root, token)
        # A selected accepted build must remain usable before automatic recovery resumes.
        frontend_plan(root, "node", verify_files=True)
        (control_dir(root) / "maintenance.json").unlink()


def contained_path(root: Path, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    lexical = Path(os.path.abspath(candidate))
    if not lexical.is_relative_to(root) or not candidate.resolve().is_relative_to(root):
        raise RuntimeControlError("runtime path escapes the repository")
    current = root
    for part in lexical.relative_to(root).parts:
        current = current / part
        attributes = current.lstat().st_file_attributes if os.name == "nt" and current.exists() else 0
        if current.is_symlink() or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise RuntimeControlError("runtime paths must not traverse links or junctions")
    return lexical


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_build(root: Path, selection: dict, *, verify_files: bool = True) -> tuple[Path, dict[str, str]]:
    if selection.get("mode") != "accepted" or selection.get("data_source") != "real":
        raise RuntimeControlError("invalid accepted frontend selection")
    build = contained_path(root, selection["build_root"])
    manifest = contained_path(root, selection["manifest_path"])
    if not build.is_dir() or sha256(manifest) != selection.get("manifest_sha256"):
        raise RuntimeControlError("accepted build or manifest identity is unavailable")
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise RuntimeControlError("accepted manifest must be a nonempty file list")
    entries = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise RuntimeControlError("invalid accepted manifest entry")
        relative = PurePosixPath(row["path"])
        digest = row.get("sha256")
        if (relative.is_absolute() or ".." in relative.parts or "\\" in row["path"]
                or ":" in row["path"] or str(relative) != row["path"] or row["path"] in entries
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise RuntimeControlError("unsafe or duplicate accepted manifest entry")
        target = contained_path(root, str(build / relative))
        if not target.is_relative_to(build) or not target.is_file():
            raise RuntimeControlError("accepted build file is missing")
        if verify_files and sha256(target) != digest:
            raise RuntimeControlError(f"accepted build file changed: {relative}")
        entries[row["path"]] = digest
    if "index.html" not in entries:
        raise RuntimeControlError("accepted build has no index.html")
    if verify_files:
        actual: set[str] = set()
        for directory, dirs, files in os.walk(build, followlinks=False):
            for name in dirs + files:
                contained_path(root, str(Path(directory) / name))
            actual.update((Path(directory) / name).relative_to(build).as_posix() for name in files)
        if actual != set(entries):
            raise RuntimeControlError("accepted build contains unlisted or missing files")
    return build, entries


class ModuleScripts(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        source = attributes.get("src")
        if tag == "script" and attributes.get("type") == "module" and source:
            self.sources.append(source)


def frontend_plan(root: Path, node: str, *, verify_files: bool = True, selection: dict | None = None) -> dict:
    if selection is None:
        state_path = control_dir(root) / "frontend.json"
        selection = read_object(state_path) if state_path.exists() else {"mode": "dev"}
    command = [node, str(root / "frontend/node_modules/vite/bin/vite.js")]
    if selection.get("mode") == "accepted":
        build, entries = verify_build(root, selection, verify_files=verify_files)
        if not shutil.which(node) or not Path(command[1]).is_file():
            raise RuntimeControlError("accepted frontend requires an available Node executable and Vite entrypoint")
        command += ["preview", "--outDir", str(build)]
        parser = ModuleScripts()
        parser.feed((build / "index.html").read_text(encoding="utf-8"))
        probes = [{"path": "index.html", "sha256": entries["index.html"]}]
        for source in dict.fromkeys(parser.sources):
            url = urlsplit(source)
            name = url.path.removeprefix("/")
            if url.scheme or url.netloc or url.query or url.fragment or name not in entries:
                raise RuntimeControlError("accepted module entrypoint is not bound to the build manifest")
            probes.append({"path": name, "sha256": entries[name]})
        if len(probes) == 1:
            raise RuntimeControlError("accepted build has no module entrypoint")
    elif selection == {"mode": "dev"}:
        probes = [{"path": ""}, {"path": "src/api/clientContext.ts"}]
    else:
        raise RuntimeControlError("invalid frontend mode; refusing development fallback")
    command += ["--host", "127.0.0.1", "--port", "5888", "--strictPort", "--clearScreen", "false"]
    return {"mode": selection["mode"], "argv": command, "cwd": str(root / "frontend"), "probes": probes}


def select_frontend(root: Path, selection: dict, token: str) -> None:
    with operation_lock(root):
        require_owner(root, token)
        frontend_plan(root, "node", selection=selection)
        write_object(control_dir(root) / "frontend.json", selection)


def run_child(root: Path, command: dict | None, *, node: str | None = None) -> int:
    with operation_lock(root):
        assert_start_allowed(root)
        if node is not None:
            command = frontend_plan(root, node)
        if (not isinstance(command, dict) or not isinstance(command.get("argv"), list)
                or not command["argv"] or any(not isinstance(a, str) or not a for a in command["argv"])):
            raise RuntimeControlError("runtime command must contain a nonempty argv list")
        cwd = contained_path(root, command.get("cwd", str(root)))
        env = os.environ.copy()
        if node is not None and command.get("mode") == "accepted":
            env.update(VITE_DATA_SOURCE="real", MOSS_VITE_API_PROXY="http://127.0.0.1:7888")
        child = subprocess.Popen(command["argv"], cwd=cwd, env=env)
    try:
        return child.wait()
    except KeyboardInterrupt:
        child.terminate()
        child.wait()
        return 130


def probe_frontend(root: Path, base_url: str = "http://127.0.0.1:5888/") -> None:
    with operation_lock(root):
        assert_start_allowed(root)
        plan = frontend_plan(root, "node", verify_files=False)
    for probe in plan["probes"]:
        with urlopen(base_url + probe["path"], timeout=3) as response:
            content = response.read()
            if response.status != 200 or (probe.get("sha256") and hashlib.sha256(content).hexdigest() != probe["sha256"]):
                raise RuntimeControlError("frontend response does not match the selected build")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("status", "check", "frontend-plan", "frontend-probe"):
        sub.add_parser(action)
    sub.add_parser("enter").add_argument("--reason", required=True)
    sub.add_parser("leave").add_argument("--owner-token", required=True)
    select = sub.add_parser("select-frontend")
    select.add_argument("--owner-token", required=True)
    select.add_argument("--build-root", required=True)
    select.add_argument("--manifest", required=True)
    select.add_argument("--manifest-sha256", required=True)
    run = sub.add_parser("run")
    run.add_argument("--command-base64", required=True)
    sub.add_parser("frontend-run").add_argument("--node", required=True)
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    try:
        if args.action == "enter":
            print(json.dumps(enter_maintenance(root, args.reason)))
        elif args.action == "leave":
            leave_maintenance(root, args.owner_token)
        elif args.action == "select-frontend":
            select_frontend(root, {"mode": "accepted", "data_source": "real", "build_root": args.build_root,
                                  "manifest_path": args.manifest, "manifest_sha256": args.manifest_sha256}, args.owner_token)
        elif args.action == "run":
            return run_child(root, json.loads(base64.b64decode(args.command_base64, validate=True)))
        elif args.action == "frontend-run":
            return run_child(root, None, node=args.node)
        elif args.action == "frontend-probe":
            probe_frontend(root)
        else:
            with operation_lock(root):
                if args.action == "status":
                    marker = control_dir(root) / "maintenance.json"
                    print(json.dumps({"maintenance": read_object(marker) if marker.exists() else None,
                                      "frontend": frontend_plan(root, "node", verify_files=False)}))
                elif args.action == "frontend-plan":
                    assert_start_allowed(root)
                    print(json.dumps(frontend_plan(root, "node")))
                else:
                    assert_start_allowed(root)
    except (RuntimeControlError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"runtime control refused: {exc}", file=sys.stderr)
        return 73
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
