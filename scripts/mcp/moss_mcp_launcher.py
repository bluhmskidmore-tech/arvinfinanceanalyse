"""
Load moss_project_mcp without relying on process cwd — fixes Cursor MCP when workspace cwd is wrong.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "usage: moss_mcp_launcher.py <metric-contracts|lineage-evidence|data-catalog|data-quality>",
            file=sys.stderr,
        )
        return 2

    mode = sys.argv[1]
    script = ROOT / "scripts" / "mcp" / "moss_project_mcp.py"

    os.chdir(ROOT)
    if mode == "lineage-evidence":
        os.environ.setdefault("MOSS_GOVERNANCE_PATH", str(ROOT / "data" / "governance"))
    if mode in {"data-catalog", "data-quality"}:
        os.environ.setdefault("MOSS_DUCKDB_PATH", str(ROOT / "data" / "moss.duckdb"))

    sys.argv = [str(script), mode]
    spec = importlib.util.spec_from_file_location("moss_project_mcp_impl", script)
    if spec is None or spec.loader is None:
        print(f"[moss MCP] Cannot load {script}", file=sys.stderr)
        return 1

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    return int(mod.main())


if __name__ == "__main__":
    raise SystemExit(main())
