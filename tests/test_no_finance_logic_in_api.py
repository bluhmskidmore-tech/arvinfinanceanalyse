from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "backend" / "app" / "api"
FORBIDDEN_TOKENS = (
    "DV01",
    "KRD",
    "CS01",
    "convexity",
    "FVTPL",
    "FVOCI",
    "债券月均金额",
    "formal PnL",
)


def test_api_layer_does_not_contain_finance_formula_tokens():
    if not API_DIR.exists():
        raise AssertionError(f"Missing API directory: {API_DIR}")

    py_files = list(API_DIR.rglob("*.py"))
    assert py_files, "Expected at least one Python file under backend/app/api"

    violations: list[str] = []
    for path in py_files:
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            if token in text:
                violations.append(f"{path}: {token}")

    assert not violations, "Finance logic leaked into API layer:\n" + "\n".join(violations)


def test_finance_token_guard_has_expected_coverage():
    """Sanity check: the denylist stays meaningful as new terms are added upstream."""
    assert len(FORBIDDEN_TOKENS) >= 6
    assert all(isinstance(t, str) and t.strip() for t in FORBIDDEN_TOKENS)
