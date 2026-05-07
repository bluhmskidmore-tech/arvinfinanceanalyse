from __future__ import annotations

import os
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent


def _default_output_dir() -> Path:
    for parent in (PKG_ROOT, *PKG_ROOT.parents):
        if (parent / "backend").exists() and (parent / "frontend").exists():
            return parent / "data" / "macro_toolkit" / "output"
    return PKG_ROOT / "output"


OUTPUT_DIR = Path(os.environ.get("MOSS_MACRO_TOOLKIT_OUTPUT_DIR", _default_output_dir())).resolve()
ASSET_DIR = OUTPUT_DIR / "bond_macro_report_assets"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ASSET_DIR.mkdir(parents=True, exist_ok=True)
