from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

PROTECTED_MONOLITHS = (
    "scripts/mcp/moss_project_mcp.py",
    "tests/test_project_mcp_servers.py",
    "frontend/src/api/contracts.ts",
    "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx",
    "frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx",
    "frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.ts",
    "frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts",
    "frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx",
    "frontend/src/features/workbench/module-home/moduleHomeModel.ts",
    "frontend/src/features/stock-analysis/pages/StockAnalysisPageImpl.tsx",
    "backend/app/services/pnl_service.py",
)

PROTECTED_STYLE_FILES = (
    "frontend/src/features/source-preview/pages/SourcePreviewPage.tsx",
    "frontend/src/features/bond-analytics/components/BondAnalyticsReadinessMatrix.tsx",
)


def _write_text(root: Path, relative_path: str, content: str) -> Path:
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _copy_audit(tmp_path: Path, script_name: str) -> Path:
    target = tmp_path / "scripts" / script_name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts" / script_name, target)
    return target


def _run_audit(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(script), *args],
        cwd=script.parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _run_audit_with_read_error(
    script: Path,
    target: Path,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    hook = script.parents[1] / "fail-read.cjs"
    hook.write_text(
        """
const fs = require("node:fs");
const path = require("node:path");
const { syncBuiltinESMExports } = require("node:module");
const originalReadFileSync = fs.readFileSync;
fs.readFileSync = function patchedReadFileSync(file, ...args) {
  if (path.resolve(String(file)) === path.resolve(process.env.MOSS_TEST_FAIL_READ_PATH)) {
    const error = new Error("injected read failure");
    error.code = "EACCES";
    throw error;
  }
  return originalReadFileSync.call(this, file, ...args);
};
syncBuiltinESMExports();
""".lstrip(),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["MOSS_TEST_FAIL_READ_PATH"] = str(target.resolve())
    return subprocess.run(
        ["node", "--require", str(hook), str(script), *args],
        cwd=script.parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        env=env,
    )


@pytest.mark.parametrize(
    ("script_name", "baseline_name", "argument", "baseline", "source_path", "source"),
    (
        (
            "audit_visual_tokens.mjs",
            "audit_visual_tokens.baseline.json",
            "--update-baseline",
            [],
            "frontend/src/demo.css",
            ".demo { color: inherit; }\n",
        ),
        (
            "audit_visual_tokens.mjs",
            "audit_visual_tokens.baseline.json",
            "--update-baseline",
            {
                "frontend/src/demo.css": {
                    "hex": "bad",
                    "forbidden": 0,
                    "offRadius": 0,
                    "doubleDash": 0,
                }
            },
            "frontend/src/demo.css",
            ".demo { color: inherit; }\n",
        ),
        (
            "audit_encoding_integrity.mjs",
            "audit_encoding_integrity.baseline.json",
            "--ratchet",
            [],
            "frontend/src/demo.ts",
            "export {};\n",
        ),
        (
            "audit_encoding_integrity.mjs",
            "audit_encoding_integrity.baseline.json",
            "--ratchet",
            {"frontend/src/demo.ts": "bad"},
            "frontend/src/demo.ts",
            "export {};\n",
        ),
        (
            "audit_section_numbering.mjs",
            "audit_section_numbering.baseline.json",
            "--ratchet",
            [],
            "frontend/src/features/demo/Demo.tsx",
            "export const Demo = () => <SectionHead numbered={false} />;\n",
        ),
        (
            "audit_section_numbering.mjs",
            "audit_section_numbering.baseline.json",
            "--ratchet",
            {"features/demo": None},
            "frontend/src/features/demo/Demo.tsx",
            "export const Demo = () => <SectionHead numbered={false} />;\n",
        ),
        (
            "audit_undeclared_css_vars.mjs",
            "audit_undeclared_css_vars.baseline.json",
            "--ratchet",
            [],
            "frontend/src/demo.css",
            ":root { --declared: black; }\n",
        ),
        (
            "audit_undeclared_css_vars.mjs",
            "audit_undeclared_css_vars.baseline.json",
            "--ratchet",
            {"frontend/src/demo.css": -1},
            "frontend/src/demo.css",
            ":root { --declared: black; }\n",
        ),
    ),
)
def test_audit_and_ratchet_reject_invalid_baseline_shapes_without_mutation(
    tmp_path: Path,
    script_name: str,
    baseline_name: str,
    argument: str,
    baseline: object,
    source_path: str,
    source: str,
) -> None:
    script = _copy_audit(tmp_path, script_name)
    baseline_path = tmp_path / "scripts" / baseline_name
    _write_json(baseline_path, baseline)
    _write_text(tmp_path, source_path, source)
    before = baseline_path.read_bytes()

    for arguments in ((), (argument,)):
        completed = _run_audit(script, *arguments)
        assert completed.returncode != 0, completed.stdout + completed.stderr
        assert baseline_path.read_bytes() == before
        assert "invalid" in (completed.stdout + completed.stderr).lower()


@pytest.mark.parametrize(
    ("script_name", "baseline_name", "argument", "source_path", "source"),
    (
        (
            "audit_visual_tokens.mjs",
            "audit_visual_tokens.baseline.json",
            "--update-baseline",
            "frontend/src/demo.css",
            ".demo { color: #fff; }\n",
        ),
        (
            "audit_encoding_integrity.mjs",
            "audit_encoding_integrity.baseline.json",
            "--ratchet",
            "frontend/src/demo.ts",
            'export const damaged = "\ufffd";\n',
        ),
        (
            "audit_section_numbering.mjs",
            "audit_section_numbering.baseline.json",
            "--ratchet",
            "frontend/src/features/demo/Demo.tsx",
            "export const Demo = () => <><SectionHead /><SectionHead /></>;\n",
        ),
        (
            "audit_undeclared_css_vars.mjs",
            "audit_undeclared_css_vars.baseline.json",
            "--ratchet",
            "frontend/src/demo.css",
            ".demo { color: var(--missing); }\n",
        ),
    ),
)
def test_ratchet_rejects_new_debt_without_mutating_baseline(
    tmp_path: Path,
    script_name: str,
    baseline_name: str,
    argument: str,
    source_path: str,
    source: str,
) -> None:
    script = _copy_audit(tmp_path, script_name)
    baseline_path = tmp_path / "scripts" / baseline_name
    _write_json(baseline_path, {})
    _write_text(tmp_path, source_path, source)
    before = baseline_path.read_bytes()

    completed = _run_audit(script, argument)

    assert completed.returncode != 0, completed.stdout + completed.stderr
    assert baseline_path.read_bytes() == before
    assert "refused to raise" in (completed.stdout + completed.stderr).lower()


@pytest.mark.parametrize(
    ("script_name", "baseline_name", "argument", "baseline", "source_path", "source"),
    (
        (
            "audit_visual_tokens.mjs",
            "audit_visual_tokens.baseline.json",
            "--update-baseline",
            {
                "frontend/src/demo.css": {
                    "hex": 1,
                    "forbidden": 0,
                    "offRadius": 0,
                    "doubleDash": 0,
                }
            },
            "frontend/src/demo.css",
            ".demo { color: inherit; }\n",
        ),
        (
            "audit_encoding_integrity.mjs",
            "audit_encoding_integrity.baseline.json",
            "--ratchet",
            {"frontend/src/demo.ts": 1},
            "frontend/src/demo.ts",
            'export const label = "clean";\n',
        ),
        (
            "audit_section_numbering.mjs",
            "audit_section_numbering.baseline.json",
            "--ratchet",
            {"features/demo": 2},
            "frontend/src/features/demo/Demo.tsx",
            "export const Demo = () => <SectionHead numbered={false} />;\n",
        ),
        (
            "audit_undeclared_css_vars.mjs",
            "audit_undeclared_css_vars.baseline.json",
            "--ratchet",
            {"frontend/src/demo.css": 1},
            "frontend/src/demo.css",
            ":root { --declared: black; } .demo { color: var(--declared); }\n",
        ),
    ),
)
def test_ratchet_writes_valid_decreases(
    tmp_path: Path,
    script_name: str,
    baseline_name: str,
    argument: str,
    baseline: object,
    source_path: str,
    source: str,
) -> None:
    script = _copy_audit(tmp_path, script_name)
    baseline_path = tmp_path / "scripts" / baseline_name
    _write_json(baseline_path, baseline)
    _write_text(tmp_path, source_path, source)

    completed = _run_audit(script, argument)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(baseline_path.read_text(encoding="utf-8")) == {}


def test_visual_ratchet_does_not_offset_new_debt_with_another_file_decrease(
    tmp_path: Path,
) -> None:
    script = _copy_audit(tmp_path, "audit_visual_tokens.mjs")
    baseline_path = tmp_path / "scripts" / "audit_visual_tokens.baseline.json"
    _write_json(
        baseline_path,
        {
            "frontend/src/a.css": {
                "hex": 1,
                "forbidden": 0,
                "offRadius": 0,
                "doubleDash": 0,
            }
        },
    )
    _write_text(tmp_path, "frontend/src/a.css", ".a { color: inherit; }\n")
    _write_text(tmp_path, "frontend/src/b.css", ".b { color: #fff; }\n")
    before = baseline_path.read_bytes()

    completed = _run_audit(script, "--update-baseline")

    assert completed.returncode != 0, completed.stdout + completed.stderr
    assert baseline_path.read_bytes() == before
    assert "frontend/src/b.css hex" in completed.stderr


@pytest.mark.parametrize(
    "extra_source",
    (
        "/* --ghost: documentation only; */\n",
        'const label = "--ghost";\nconst documentation = "[label]:";\n',
    ),
)
def test_undeclared_css_var_comments_and_unused_strings_do_not_declare_tokens(
    tmp_path: Path,
    extra_source: str,
) -> None:
    script = _copy_audit(tmp_path, "audit_undeclared_css_vars.mjs")
    baseline_path = tmp_path / "scripts" / "audit_undeclared_css_vars.baseline.json"
    _write_json(baseline_path, {})
    if extra_source.startswith("const"):
        _write_text(tmp_path, "frontend/src/demo.ts", extra_source)
        css_source = ".demo { color: var(--ghost); }\n"
    else:
        css_source = extra_source + ".demo { color: var(--ghost); }\n"
    _write_text(tmp_path, "frontend/src/demo.css", css_source)
    before = baseline_path.read_bytes()

    for arguments in ((), ("--ratchet",)):
        completed = _run_audit(script, *arguments)
        assert completed.returncode != 0, completed.stdout + completed.stderr
        assert baseline_path.read_bytes() == before
        assert "frontend/src/demo.css" in (completed.stdout + completed.stderr)


def test_undeclared_css_var_accepts_verified_computed_key_declaration(
    tmp_path: Path,
) -> None:
    script = _copy_audit(tmp_path, "audit_undeclared_css_vars.mjs")
    baseline_path = tmp_path / "scripts" / "audit_undeclared_css_vars.baseline.json"
    _write_json(baseline_path, {})
    _write_text(
        tmp_path,
        "frontend/src/demo.ts",
        'const url = "https://example.test";\n'
        'const GHOST_CSS_VAR = "--ghost";\n'
        "export const style = { [GHOST_CSS_VAR]: url };\n",
    )
    _write_text(tmp_path, "frontend/src/demo.css", ".demo { color: var(--ghost); }\n")

    completed = _run_audit(script)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "fallback-less uses of undeclared names 0/0" in completed.stdout


def test_section_numbering_ignores_comment_import_and_string_mentions(
    tmp_path: Path,
) -> None:
    script = _copy_audit(tmp_path, "audit_section_numbering.mjs")
    baseline_path = tmp_path / "scripts" / "audit_section_numbering.baseline.json"
    _write_json(baseline_path, {})
    _write_text(
        tmp_path,
        "frontend/src/features/demo/Demo.tsx",
        "// SECTION_HEAD_STACK_CLASSNAME mentioned only in prose\n"
        'import { SECTION_HEAD_STACK_CLASSNAME } from "./layout";\n'
        'const label = "SECTION_HEAD_STACK_CLASSNAME";\n'
        'export const Demo = () => <main className={"SECTION_HEAD_STACK_CLASSNAME"}>'
        "<SectionHead /><SectionHead /></main>;\n",
    )
    before = baseline_path.read_bytes()

    for arguments in ((), ("--ratchet",)):
        completed = _run_audit(script, *arguments)
        assert completed.returncode != 0, completed.stdout + completed.stderr
        assert baseline_path.read_bytes() == before
        assert "features/demo" in (completed.stdout + completed.stderr)


def test_section_numbering_accepts_stack_token_in_real_classname_expression(
    tmp_path: Path,
) -> None:
    script = _copy_audit(tmp_path, "audit_section_numbering.mjs")
    baseline_path = tmp_path / "scripts" / "audit_section_numbering.baseline.json"
    _write_json(baseline_path, {})
    _write_text(
        tmp_path,
        "frontend/src/features/demo/Demo.tsx",
        'const url = "https://example.test";\n'
        "export const Demo = () => (\n"
        "  <main className={`${url} ${SECTION_HEAD_STACK_CLASSNAME}`}>\n"
        "    <SectionHead /><SectionHead />\n"
        "  </main>\n"
        ");\n",
    )

    completed = _run_audit(script)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "at-risk heads 0/0" in completed.stdout


@pytest.mark.parametrize(
    ("script_name", "baseline_name", "baseline"),
    (
        (
            "audit_encoding_integrity.mjs",
            "audit_encoding_integrity.baseline.json",
            {"frontend/src/legacy.ts": 1},
        ),
        (
            "audit_section_numbering.mjs",
            "audit_section_numbering.baseline.json",
            {"features/demo": 2},
        ),
        (
            "audit_undeclared_css_vars.mjs",
            "audit_undeclared_css_vars.baseline.json",
            {"frontend/src/legacy.css": 1},
        ),
    ),
)
def test_ratchet_rejects_missing_required_scan_root_without_mutation(
    tmp_path: Path,
    script_name: str,
    baseline_name: str,
    baseline: object,
) -> None:
    script = _copy_audit(tmp_path, script_name)
    baseline_path = tmp_path / "scripts" / baseline_name
    _write_json(baseline_path, baseline)
    before = baseline_path.read_bytes()

    completed = _run_audit(script, "--ratchet")

    assert completed.returncode != 0, completed.stdout + completed.stderr
    assert baseline_path.read_bytes() == before
    assert "scan incomplete" in completed.stderr
    assert "frontend/src" in completed.stderr


@pytest.mark.parametrize(
    ("script_name", "baseline_name", "baseline", "source_path", "source"),
    (
        (
            "audit_encoding_integrity.mjs",
            "audit_encoding_integrity.baseline.json",
            {"frontend/src/demo.ts": 1},
            "frontend/src/demo.ts",
            "export {};\n",
        ),
        (
            "audit_section_numbering.mjs",
            "audit_section_numbering.baseline.json",
            {"features/demo": 2},
            "frontend/src/features/demo/Demo.tsx",
            "export const Demo = () => <><SectionHead /><SectionHead /></>;\n",
        ),
        (
            "audit_undeclared_css_vars.mjs",
            "audit_undeclared_css_vars.baseline.json",
            {"frontend/src/demo.css": 1},
            "frontend/src/demo.css",
            ".demo { color: var(--missing); }\n",
        ),
    ),
)
def test_audit_and_ratchet_reject_discovered_file_read_errors_without_mutation(
    tmp_path: Path,
    script_name: str,
    baseline_name: str,
    baseline: object,
    source_path: str,
    source: str,
) -> None:
    script = _copy_audit(tmp_path, script_name)
    baseline_path = tmp_path / "scripts" / baseline_name
    _write_json(baseline_path, baseline)
    target = _write_text(tmp_path, source_path, source)
    before = baseline_path.read_bytes()

    for arguments in ((), ("--ratchet",)):
        completed = _run_audit_with_read_error(script, target, *arguments)
        assert completed.returncode != 0, completed.stdout + completed.stderr
        assert baseline_path.read_bytes() == before
        assert "scan incomplete" in completed.stderr
        assert source_path in completed.stderr


def _frontend_baseline() -> dict[str, object]:
    return {
        "_policy": "ratchet-only test baseline",
        "frontend": {
            "apiClientLines": 1,
            "apiClientMockOccurrences": 0,
            "totalTsxStyleProps": 0,
            "totalStaticTsxStyleProps": 0,
            "featuresEmDashLiterals": 0,
            "featuresSemanticProfitLossRefs": 0,
            "featuresEchartsForReactImportFiles": 0,
            "dashboardStyleFiles": {},
            "maxPageStyleProps": {path: 0 for path in PROTECTED_STYLE_FILES},
            "maxPageStaticStyleProps": {},
            "protectedMonolithFiles": {
                path: {"maxLines": 1, "routeHint": "keep focused"}
                for path in PROTECTED_MONOLITHS
            },
        },
    }


def _prepare_frontend_audit(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    script = _copy_audit(tmp_path, "audit_frontend_debt.mjs")
    _write_text(tmp_path, "frontend/src/api/client.ts", "export {};\n")
    for relative_path in PROTECTED_MONOLITHS:
        _write_text(tmp_path, relative_path, "x\n")
    for relative_path in PROTECTED_STYLE_FILES:
        _write_text(tmp_path, relative_path, "export {};\n")
    baseline = _frontend_baseline()
    baseline_path = tmp_path / "scripts" / "debt-baselines.json"
    _write_json(baseline_path, baseline)
    return script, baseline_path, baseline


def test_frontend_ratchet_is_atomic_when_one_measurement_would_increase(
    tmp_path: Path,
) -> None:
    script, baseline_path, baseline = _prepare_frontend_audit(tmp_path)
    baseline["frontend"]["apiClientLines"] = 2  # type: ignore[index]
    _write_text(tmp_path, PROTECTED_MONOLITHS[0], "first\nsecond\n")
    _write_json(baseline_path, baseline)
    before = baseline_path.read_bytes()

    completed = _run_audit(script, "--ratchet")

    assert completed.returncode != 0, completed.stdout + completed.stderr
    assert baseline_path.read_bytes() == before
    assert "Refused to raise" in completed.stderr


@pytest.mark.parametrize("missing_path", PROTECTED_MONOLITHS)
@pytest.mark.parametrize("arguments", ((), ("--self-test",)))
def test_frontend_audit_and_self_test_reject_a_missing_monolith_guard(
    tmp_path: Path,
    arguments: tuple[str, ...],
    missing_path: str,
) -> None:
    script, baseline_path, baseline = _prepare_frontend_audit(tmp_path)
    del baseline["frontend"]["protectedMonolithFiles"][missing_path]  # type: ignore[index]
    _write_json(baseline_path, baseline)

    completed = _run_audit(script, *arguments)

    assert completed.returncode != 0, completed.stdout + completed.stderr
    assert missing_path in completed.stderr


@pytest.mark.parametrize("missing_path", PROTECTED_STYLE_FILES)
@pytest.mark.parametrize("arguments", ((), ("--self-test",)))
def test_frontend_audit_and_self_test_reject_a_missing_style_guard(
    tmp_path: Path,
    arguments: tuple[str, ...],
    missing_path: str,
) -> None:
    script, baseline_path, baseline = _prepare_frontend_audit(tmp_path)
    del baseline["frontend"]["maxPageStyleProps"][missing_path]  # type: ignore[index]
    _write_json(baseline_path, baseline)

    completed = _run_audit(script, *arguments)

    assert completed.returncode != 0, completed.stdout + completed.stderr
    assert missing_path in completed.stderr


@pytest.mark.parametrize(
    ("field", "value"),
    (("maxLines", 0), ("routeHint", "")),
)
def test_frontend_audit_rejects_invalid_monolith_policy(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    script, baseline_path, baseline = _prepare_frontend_audit(tmp_path)
    policy = baseline["frontend"]["protectedMonolithFiles"][PROTECTED_MONOLITHS[0]]  # type: ignore[index]
    policy[field] = value
    _write_json(baseline_path, baseline)

    completed = _run_audit(script)

    assert completed.returncode != 0, completed.stdout + completed.stderr
    assert field in completed.stderr
    assert PROTECTED_MONOLITHS[0] in completed.stderr


@pytest.mark.parametrize("baseline", ([], {"_policy": "test", "frontend": []}))
def test_frontend_audit_rejects_invalid_document_shapes(
    tmp_path: Path,
    baseline: object,
) -> None:
    script = _copy_audit(tmp_path, "audit_frontend_debt.mjs")
    baseline_path = tmp_path / "scripts" / "debt-baselines.json"
    _write_json(baseline_path, baseline)
    before = baseline_path.read_bytes()

    for arguments in ((), ("--ratchet",)):
        completed = _run_audit(script, *arguments)
        assert completed.returncode != 0, completed.stdout + completed.stderr
        assert baseline_path.read_bytes() == before


def test_frontend_audit_rejects_invalid_style_counter(tmp_path: Path) -> None:
    script, baseline_path, baseline = _prepare_frontend_audit(tmp_path)
    baseline["frontend"]["maxPageStyleProps"][PROTECTED_STYLE_FILES[0]] = "bad"  # type: ignore[index]
    _write_json(baseline_path, baseline)
    before = baseline_path.read_bytes()

    for arguments in ((), ("--ratchet",)):
        completed = _run_audit(script, *arguments)
        assert completed.returncode != 0, completed.stdout + completed.stderr
        assert baseline_path.read_bytes() == before
        assert "invalid maxPageStyleProps" in completed.stderr


def test_frontend_style_guard_does_not_offset_growth_between_files(tmp_path: Path) -> None:
    script, baseline_path, baseline = _prepare_frontend_audit(tmp_path)
    baseline["frontend"]["totalTsxStyleProps"] = 1  # type: ignore[index]
    baseline["frontend"]["totalStaticTsxStyleProps"] = 1  # type: ignore[index]
    baseline["frontend"]["maxPageStyleProps"][PROTECTED_STYLE_FILES[0]] = 1  # type: ignore[index]
    _write_text(
        tmp_path,
        PROTECTED_STYLE_FILES[1],
        'export const Demo = () => <div style={{ color: "red" }} />;\n',
    )
    _write_json(baseline_path, baseline)

    completed = _run_audit(script)

    assert completed.returncode != 0, completed.stdout + completed.stderr
    assert f"{PROTECTED_STYLE_FILES[1]} style props: 1 > baseline 0" in completed.stderr


def test_frontend_ratchet_writes_valid_decreases(tmp_path: Path) -> None:
    script, baseline_path, baseline = _prepare_frontend_audit(tmp_path)
    baseline["frontend"]["apiClientLines"] = 2  # type: ignore[index]
    for policy in baseline["frontend"]["protectedMonolithFiles"].values():  # type: ignore[index]
        policy["maxLines"] = 2
    for path in PROTECTED_STYLE_FILES:
        baseline["frontend"]["maxPageStyleProps"][path] = 1  # type: ignore[index]
    _write_json(baseline_path, baseline)

    completed = _run_audit(script, "--ratchet")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    updated = json.loads(baseline_path.read_text(encoding="utf-8"))["frontend"]
    assert updated["apiClientLines"] == 1
    assert all(policy["maxLines"] == 1 for policy in updated["protectedMonolithFiles"].values())
    assert all(updated["maxPageStyleProps"][path] == 0 for path in PROTECTED_STYLE_FILES)


def test_frontend_scope_excludes_backend_growth_but_default_audit_still_fails(
    tmp_path: Path,
) -> None:
    script, baseline_path, _ = _prepare_frontend_audit(tmp_path)
    backend_path = "backend/app/services/pnl_service.py"
    _write_text(tmp_path, backend_path, "first\nsecond\n")
    before = baseline_path.read_bytes()

    full = _run_audit(script)
    focused = _run_audit(script, "--scope", "frontend")

    assert full.returncode == 1, full.stdout + full.stderr
    assert f"{backend_path} lines: 2 > baseline 1" in full.stderr
    assert focused.returncode == 0, focused.stdout + focused.stderr
    assert "[repository]" in full.stderr
    assert "scope=frontend" in focused.stdout
    assert "not a full repository audit" in focused.stdout
    assert backend_path in focused.stdout
    assert "2 > baseline 1" not in focused.stdout + focused.stderr
    assert baseline_path.read_bytes() == before


def test_frontend_scope_still_rejects_frontend_growth_without_mutating_baseline(
    tmp_path: Path,
) -> None:
    script, baseline_path, _ = _prepare_frontend_audit(tmp_path)
    frontend_path = "frontend/src/api/contracts.ts"
    _write_text(tmp_path, frontend_path, "first\nsecond\n")
    before = baseline_path.read_bytes()

    completed = _run_audit(script, "--scope", "frontend")

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert f"{frontend_path} lines: 2 > baseline 1" in completed.stderr
    assert "[frontend]" in completed.stderr
    assert baseline_path.read_bytes() == before


@pytest.mark.parametrize(
    "arguments",
    (("--scope", "frontend", "--ratchet"), ("--scope", "unknown"), ("--scope",)),
)
def test_frontend_scope_rejects_unsafe_or_invalid_arguments_without_mutation(
    tmp_path: Path,
    arguments: tuple[str, ...],
) -> None:
    script, baseline_path, baseline = _prepare_frontend_audit(tmp_path)
    baseline["frontend"]["apiClientLines"] = 2  # type: ignore[index]
    _write_json(baseline_path, baseline)
    before = baseline_path.read_bytes()

    completed = _run_audit(script, *arguments)

    assert completed.returncode != 0, completed.stdout + completed.stderr
    assert "scope" in completed.stderr
    assert baseline_path.read_bytes() == before


def _prepare_scoped_debt_runner(tmp_path: Path) -> tuple[Path, Path]:
    _, baseline_path, _ = _prepare_frontend_audit(tmp_path)
    runner = _copy_audit(tmp_path, "run_frontend_debt_audits.mjs")
    for script_name in (
        "audit_visual_tokens.mjs",
        "audit_font_size_floor.mjs",
        "audit_encoding_integrity.mjs",
        "audit_section_numbering.mjs",
        "audit_undeclared_css_vars.mjs",
    ):
        # The real debt audit above verifies scope forwarding; these stubs
        # isolate runner selection, failure attribution, and no-short-circuit.
        _write_text(
            tmp_path,
            f"scripts/{script_name}",
            f'console.log("EXECUTED {script_name}");\n'
            + ("process.exit(7);\n" if script_name == "audit_encoding_integrity.mjs" else ""),
        )
    return runner, baseline_path


def test_debt_runner_scopes_frontend_feedback_and_keeps_full_gate_failures(
    tmp_path: Path,
) -> None:
    runner, baseline_path = _prepare_scoped_debt_runner(tmp_path)
    _write_text(tmp_path, "backend/app/services/pnl_service.py", "first\nsecond\n")
    before = baseline_path.read_bytes()

    full = _run_audit(runner)
    focused = _run_audit(runner, "--scope", "frontend")

    assert full.returncode == 1, full.stdout + full.stderr
    assert "2/6 audit(s) failed" in full.stdout
    assert "audit_encoding_integrity.mjs [repository]: FAIL (exit 7)" in full.stdout
    assert "EXECUTED audit_undeclared_css_vars.mjs" in full.stdout
    assert focused.returncode == 0, focused.stdout + focused.stderr
    assert "All 5 selected audits passed (scope=frontend)" in focused.stdout
    assert "not a full repository audit" in focused.stdout
    assert "repository encoding is not covered" in focused.stdout
    assert "EXECUTED audit_encoding_integrity.mjs" not in focused.stdout
    assert "EXECUTED audit_undeclared_css_vars.mjs" in focused.stdout
    assert baseline_path.read_bytes() == before


def test_debt_runner_frontend_growth_fails_without_short_circuit(tmp_path: Path) -> None:
    runner, baseline_path = _prepare_scoped_debt_runner(tmp_path)
    _write_text(tmp_path, "frontend/src/api/contracts.ts", "first\nsecond\n")
    before = baseline_path.read_bytes()

    completed = _run_audit(runner, "--scope", "frontend")

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "1/5 audit(s) failed" in completed.stdout
    assert "audit_frontend_debt.mjs [frontend]: FAIL (exit 1)" in completed.stdout
    assert "EXECUTED audit_undeclared_css_vars.mjs" in completed.stdout
    assert baseline_path.read_bytes() == before


@pytest.mark.parametrize("arguments", (("--scope", "unknown"), ("--scope",), ("--scop", "frontend")))
def test_debt_runner_rejects_invalid_scope_before_running_audits(
    tmp_path: Path,
    arguments: tuple[str, ...],
) -> None:
    runner, baseline_path = _prepare_scoped_debt_runner(tmp_path)
    before = baseline_path.read_bytes()

    completed = _run_audit(runner, *arguments)

    assert completed.returncode != 0, completed.stdout + completed.stderr
    assert "scop" in completed.stderr
    assert "EXECUTED" not in completed.stdout
    assert baseline_path.read_bytes() == before
