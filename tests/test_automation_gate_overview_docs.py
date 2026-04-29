from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "automation_gate_overview.md"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _squash_ws(text: str) -> str:
    return " ".join(text.split())


def test_automation_gate_overview_is_non_authoritative_index():
    doc = DOC.read_text(encoding="utf-8")
    prose = _squash_ws(doc)

    assert "index only" in doc
    assert "non-authoritative" in doc
    assert "does not override `AGENTS.md`, `docs/DOCUMENT_AUTHORITY.md`" in prose
    assert "the executable source wins" in prose
    assert "do not prove all business metric definitions" in prose
    assert "page-level requirements" in prose


def test_automation_gate_overview_has_required_source_bound_rows():
    doc = DOC.read_text(encoding="utf-8")
    doc_lower = doc.lower()
    required_rows = {
        "Backend release suite": [
            "`python scripts/backend_release_suite.py`",
            "`scripts/backend_release_suite.py`",
            "fixed matrix",
            "does not prove",
        ],
        "CI backend job": [
            "`python scripts/backend_release_suite.py --governance-audit-output governance-lineage-audit.json`",
            "`governance-lineage-audit.json`",
            "`actions/upload-artifact@v4`",
            "execution wrapper",
            "independent business assertion",
        ],
        "Governance doc contract": [
            "`tests/test_governance_doc_contract.py`",
            "golden-sample bindings",
            "fully correct at runtime",
        ],
        "Golden sample capture-ready contract": [
            "`tests/test_golden_samples_capture_ready.py`",
            "`tests/golden_samples/`",
            "all production data combinations",
        ],
        "Frontend typecheck": [
            "`npx tsc --noEmit`",
            "`tsc --noEmit`",
            "business meaning",
        ],
        "Frontend Vitest": [
            "`npx vitest run`",
            "`vitest run`",
            "Full browser end-to-end behavior",
        ],
        "Frontend debt audit": [
            "`npm run debt:audit`",
            "`node ../scripts/audit_frontend_debt.mjs`",
            "`api/client.ts`",
            "free of existing debt",
        ],
        "Surface naming check": [
            "`node scripts/check_surface_naming.mjs`",
            "vocabulary rules",
            "unlisted surfaces",
        ],
        "ESLint": [
            "`npx eslint .`",
            "`eslint .`",
            "Business correctness",
        ],
    }

    for gate, tokens in required_rows.items():
        assert gate in doc
        for token in tokens:
            if token.startswith("`"):
                assert token in doc
            else:
                assert token.lower() in doc_lower


def test_automation_gate_overview_matches_real_gate_sources():
    workflow = _read(".github/workflows/ci.yml")
    release_suite = _read("scripts/backend_release_suite.py")
    frontend_package = json.loads(_read("frontend/package.json"))
    debt_audit = _read("scripts/audit_frontend_debt.mjs")
    surface_naming = _read("scripts/check_surface_naming.mjs")

    assert "python scripts/backend_release_suite.py --governance-audit-output governance-lineage-audit.json" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "governance-lineage-audit.json" in workflow
    assert "tests/test_governance_doc_contract.py" in release_suite
    assert "tests/test_golden_samples_capture_ready.py" in release_suite

    scripts = frontend_package["scripts"]
    assert scripts["typecheck"] == "tsc --noEmit"
    assert scripts["test"] == "vitest run"
    assert scripts["debt:audit"] == "node ../scripts/audit_frontend_debt.mjs"
    assert scripts["lint"] == "eslint ."

    assert "npx tsc --noEmit" in workflow
    assert "npx vitest run" in workflow
    assert "npm run debt:audit" in workflow
    assert "node scripts/check_surface_naming.mjs" in workflow
    assert "npx eslint ." in workflow
    assert "apiClientLines" in debt_audit
    assert "apiClientMockOccurrences" in debt_audit
    assert "totalTsxStyleProps" in debt_audit
    assert "Frontend debt audit passed (no growth over baseline)." in debt_audit
    assert "const RULES" in surface_naming
    assert "forbidden" in surface_naming
    assert "surface-naming lint: OK" in surface_naming
