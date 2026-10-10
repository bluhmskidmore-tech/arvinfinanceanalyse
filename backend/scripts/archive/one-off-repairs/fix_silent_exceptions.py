#!/usr/bin/env python3
"""
fix_silent_exceptions.py — 一次性自动修复后端静默异常吞没

扫描 backend/app/ 下所有 .py 文件:
1. 找到 `except Exception:` + `pass` (无日志) 的模式
2. 将 `pass` 替换为 `logger.warning("...", exc_info=True)`
3. 在文件顶部补充 `import logging` 和 `logger = ...` (如缺失)

用法:
    cd f:\\MOSS-V3
    python backend/scripts/fix_silent_exceptions.py --dry-run   # 先预览
    python backend/scripts/fix_silent_exceptions.py             # 执行修复

修复后用 git diff 检查所有变更。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BACKEND_APP = Path(__file__).resolve().parent.parent / "app"

# ---------- patterns ----------

# Matches: `except Exception:` or `except Exception as ...:` where next meaningful line is `pass`
SILENT_PASS_RE = re.compile(
    r"^(?P<indent>\s*)except\s+Exception(?:\s+as\s+\w+)?\s*:\s*\n"
    r"(?P<pass_indent>\s*)pass\s*$",
    re.MULTILINE,
)

# For detecting existing logger
HAS_LOGGER_RE = re.compile(r"^logger\s*=\s*logging\.getLogger", re.MULTILINE)
HAS_IMPORT_LOGGING = re.compile(r"^import\s+logging\b", re.MULTILINE)

# For inserting logger after last top-level import block
IMPORT_LINE_RE = re.compile(r"^(?:import |from )\S+", re.MULTILINE)


def _infer_context(source: str, match_start: int) -> str:
    """Try to find the enclosing function/method name for a better log message."""
    preceding = source[:match_start]
    # Find the last `def xxx(` before this match
    func_match = None
    for m in re.finditer(r"def\s+(\w+)\s*\(", preceding):
        func_match = m
    if func_match:
        return func_match.group(1)
    return "unknown"


def fix_file(filepath: Path, dry_run: bool) -> list[str]:
    """Fix silent exceptions in a single file. Returns list of change descriptions."""
    source = filepath.read_text(encoding="utf-8")
    changes: list[str] = []

    # Find all silent pass patterns
    matches = list(SILENT_PASS_RE.finditer(source))
    if not matches:
        return changes

    # --- Phase 1: ensure logger exists ---
    needs_import = not HAS_IMPORT_LOGGING.search(source)
    needs_logger = not HAS_LOGGER_RE.search(source)

    if needs_import or needs_logger:
        lines = source.split("\n")
        # Find insertion point: after last import line before first class/def
        last_import_idx = -1
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                last_import_idx = i
            # Stop at first class or def (not indented)
            if (stripped.startswith("class ") or stripped.startswith("def ")) and not line.startswith(" "):
                break

        insert_lines: list[str] = []
        if needs_import:
            insert_lines.append("import logging")
        if needs_logger:
            insert_lines.append("")
            insert_lines.append("logger = logging.getLogger(__name__)")

        if last_import_idx >= 0 and insert_lines:
            # Check if the line after last import is blank
            after = last_import_idx + 1
            # Insert after last import
            for j, new_line in enumerate(insert_lines):
                lines.insert(after + j, new_line)
            source = "\n".join(lines)
            if needs_import:
                changes.append("  + import logging")
            if needs_logger:
                changes.append("  + logger = logging.getLogger(__name__)")

    # --- Phase 2: replace pass with logger.warning ---
    # Re-find matches since source may have shifted
    def replacer(m: re.Match) -> str:
        indent = m.group("indent")
        # Infer context
        func_name = _infer_context(source_for_context, m.start())
        module_name = filepath.stem

        log_msg = f'{indent}logger.warning("{module_name}.{func_name}: suppressed exception", exc_info=True)'
        changes.append(f"  L~{source_for_context[:m.start()].count(chr(10))+1}: pass -> logger.warning")
        return f"{indent}except Exception:\n{log_msg}"

    source_for_context = source
    new_source = SILENT_PASS_RE.sub(replacer, source)

    if new_source != filepath.read_text(encoding="utf-8"):
        if not dry_run:
            filepath.write_text(new_source, encoding="utf-8")
        return changes
    return changes


def main():
    parser = argparse.ArgumentParser(description="Fix silent except Exception: pass patterns")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files")
    args = parser.parse_args()

    scan_dirs = [
        BACKEND_APP / "tasks",
        BACKEND_APP / "services",
        BACKEND_APP / "repositories",
        BACKEND_APP / "core_finance",
    ]

    total_files = 0
    total_fixes = 0

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for py_file in sorted(scan_dir.rglob("*.py")):
            if "__pycache__" in str(py_file):
                continue
            changes = fix_file(py_file, dry_run=args.dry_run)
            if changes:
                total_files += 1
                total_fixes += len([c for c in changes if "pass -> logger" in c])
                rel = py_file.relative_to(BACKEND_APP)
                print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Fixed: {rel}")
                for c in changes:
                    print(c)

    print(f"\n{'='*60}")
    mode = "DRY RUN" if args.dry_run else "APPLIED"
    print(f"[{mode}] {total_fixes} silent pass blocks fixed across {total_files} files")
    if args.dry_run:
        print("\nRe-run without --dry-run to apply changes.")
        print("After applying, use `git diff` to review all changes.")


if __name__ == "__main__":
    main()
