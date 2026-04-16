from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = ROOT / "frontend" / "src"
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


# Display-only / fixture surfaces — labels & mocks, not pricing logic.
DISPLAY_ONLY_DIRS = (
    "features/bond-analytics/",
    "features/bond-dashboard/",
    "features/liability-analytics/",
    "features/pnl-attribution/",
    "features/risk-overview/",
    "features/risk-tensor/",
    "api/",
    "mocks/",
    "test/",
)


def _is_display_only(path: Path) -> bool:
    rel = path.relative_to(FRONTEND_SRC).as_posix()
    return any(rel.startswith(d) for d in DISPLAY_ONLY_DIRS)


def test_frontend_source_does_not_contain_formal_finance_logic_tokens():
    if not FRONTEND_SRC.exists():
        return

    files = sorted(
        (
            f
            for f in list(FRONTEND_SRC.rglob("*.ts")) + list(FRONTEND_SRC.rglob("*.tsx"))
            if not _is_display_only(f)
        ),
        key=lambda p: p.as_posix(),
    )
    violations: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            if token in text:
                violations.append(f"{path}: {token}")

    assert not violations, "Finance logic leaked into frontend:\n" + "\n".join(violations)
